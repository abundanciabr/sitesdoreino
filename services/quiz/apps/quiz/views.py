import json
import uuid
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from datetime import datetime, timezone as datetime_timezone
from types import SimpleNamespace

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core import signing
from django.core.validators import validate_email
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from redis.exceptions import RedisError

from .models import (
    CapturaParcial,
    OutboxEvent,
    Quiz,
    QuizVersion,
    Submission,
    TelemetryEvent,
)
from .respostas import emitir_quiz_completado, lead_do_contato, respostas_legiveis
from .comprador import gravar_cookie
from .direcionadas import (
    destino_com_parametros,
    entrada_da_tentativa,
    resolver_direcionada,
    url_da_experiencia,
)
from .experiencias import resolver_experiencia, calcular as calcular_experiencia
from .tasks import TIPOS_DE_EVENTO, publicar_telemetria, relay_apos_commit

COOKIE_SESSAO = "quiz_session"
SALT_SESSAO = "quiz-session"
MAX_AGE_SESSAO = 7 * 24 * 60 * 60
LIMITE_CORPO = 4096
LIMITE_ELEMENTO = 120
# Lidos do modelo: contato maior que a coluna seria erro do banco (500) e a
# pessoa perderia as respostas.
LIMITES_DO_CONTATO = {
    campo: Submission._meta.get_field(coluna).max_length
    for campo, coluna in (
        ("email", "lead_email"),
        ("nome", "lead_name"),
        ("telefone", "lead_phone"),
    )
}


def _quiz_do_site(request, slug):
    # `getattr` porque o atributo é LEGITIMAMENTE ausente nos caminhos que o
    # SiteResolutionMiddleware isenta (`/healthz`, `/static/`). Desde que as
    # páginas foram para a raiz do urlconf, a rota do formulário é um curinga de
    # um segmento e `/healthz/` e `/static/` casam com ela: sem esta guarda a
    # view leria o atributo inexistente e as duas formas virariam 500 no lugar
    # do 404 que sempre foram. Não existe quiz chamado "healthz".
    site = getattr(request, "site", None)
    if site is None:
        raise Http404("caminho isento de resolução de site")
    return get_object_or_404(Quiz, site_id=site["id"], slug=slug, active=True)


def escolher_versao(quiz, session_id: uuid.UUID) -> QuizVersion:
    """Corte estável: o mesmo session_id cai sempre na mesma versão ativa."""
    elegiveis = [
        versao
        for versao in quiz.versions.filter(active=True).order_by("id")
        if versao.weight > 0
    ]
    if not elegiveis:
        raise Http404("nenhuma versão ativa")
    total = sum(versao.weight for versao in elegiveis)
    ponto = session_id.int % total
    acumulado = 0
    for versao in elegiveis:
        acumulado += versao.weight
        if ponto < acumulado:
            return versao
    return elegiveis[-1]


def _utm_da_query(request) -> dict:
    saida = {}
    for chave, valor in request.GET.items():
        if not chave.startswith("utm_") or not valor:
            continue
        saida[chave[4:100]] = str(valor)[:200]
        if len(saida) >= 8:
            break
    return saida


def _ler_quizzes(request) -> dict:
    cru = request.COOKIES.get(COOKIE_SESSAO)
    if not cru:
        return {}
    try:
        dados = signing.loads(cru, salt=SALT_SESSAO, max_age=MAX_AGE_SESSAO)
    except signing.BadSignature:
        return {}
    quizzes = dados.get("quizzes") if isinstance(dados, dict) else None
    if not isinstance(quizzes, dict):
        return {}
    return quizzes


def _entrada_usavel(entrada) -> bool:
    if not isinstance(entrada, dict):
        return False
    try:
        uuid.UUID(str(entrada.get("session_id")))
    except (ValueError, TypeError):
        return False
    return (
        isinstance(entrada.get("version_key"), str)
        and entrada.get("version_id")
        and isinstance(entrada.get("site_id"), str)
    )


def resolver_sessao(request, quiz):
    """Devolve a entrada do cookie e a versão que esta visita vai ver.

    A UTM é a da chegada. Uma visita seguinte não troca o anúncio de origem
    só porque a query sumiu.
    """
    if quiz.directed:
        return resolver_direcionada(request, quiz, _ler_quizzes(request))
    atual = _ler_quizzes(request).get(quiz.slug)
    versao = None
    if _entrada_usavel(atual):
        versao = quiz.versions.filter(pk=atual["version_id"]).first()
    if versao is None:
        session_id = uuid.uuid4()
        if isinstance(atual, dict):
            try:
                session_id = uuid.UUID(str(atual.get("session_id")))
            except (ValueError, TypeError):
                session_id = uuid.uuid4()
        versao = escolher_versao(quiz, session_id)
        utm = _utm_da_query(request)
        if (
            isinstance(atual, dict)
            and isinstance(atual.get("utm"), dict)
            and atual.get("utm")
        ):
            utm = atual["utm"]
        atual = {
            "session_id": str(session_id),
            "version_id": versao.id,
            "version_key": versao.key,
            "site_id": quiz.site_id,
            "utm": utm,
        }
    else:
        atual = {
            "session_id": str(atual["session_id"]),
            "version_id": versao.id,
            "version_key": versao.key,
            "site_id": quiz.site_id,
            "utm": atual.get("utm") if isinstance(atual.get("utm"), dict) else {},
        }
    return atual, versao


def _escrever_cookie(response, request, slug, entrada):
    quizzes = _ler_quizzes(request)
    quizzes[slug] = {
        "session_id": entrada["session_id"],
        "version_id": entrada["version_id"],
        "version_key": entrada["version_key"],
        "site_id": entrada["site_id"],
        "utm": entrada.get("utm") or {},
    }
    if "context" in entrada:
        quizzes[slug]["context"] = entrada["context"]
        quizzes[f"{slug}:{entrada['session_id']}"] = quizzes[slug]
        anteriores = [chave for chave in quizzes if chave.startswith(f"{slug}:")]
        for chave in anteriores[:-8]:
            quizzes.pop(chave)

    def assinado():
        return signing.dumps({"quizzes": quizzes}, salt=SALT_SESSAO, compress=True)

    valor = assinado()
    # O navegador rejeita cookies grandes. Retire só tentativas antigas;
    # uma aba retirada recebe indisponibilidade e nunca herda outra campanha.
    protegidas = {slug, f"{slug}:{entrada['session_id']}"}
    for chave in list(quizzes):
        if len(valor) <= 3800:
            break
        if chave not in protegidas:
            quizzes.pop(chave)
            valor = assinado()
    response.set_cookie(
        COOKIE_SESSAO,
        valor,
        max_age=MAX_AGE_SESSAO,
        httponly=True,
        secure=request.is_secure(),
        samesite="Lax",
        path=settings.FORCE_SCRIPT_NAME or "/",
    )
    return response


def _render_formulario(
    request,
    quiz,
    versao,
    questions,
    entrada,
    erro=None,
    status=200,
    etapa_inicial=0,
    campo_com_erro=None,
):
    valores = {
        "email": request.POST.get("email", ""),
        "nome": request.POST.get("nome", ""),
        "telefone": request.POST.get("telefone", ""),
    }
    opcoes_selecionadas = set()
    for question in questions:
        valor = request.POST.get(f"pergunta_{question.id}")
        if valor and any(str(option.id) == valor for option in question.options.all()):
            opcoes_selecionadas.add(int(valor))
    experiencia = None
    if quiz.directed:
        contexto = entrada.get("context") or {}
        experiencia = resolver_experiencia(
            versao, contexto.get("fmt"), contexto.get("seg")
        )
    endereco_canonico = reverse("quiz-formulario", args=[quiz.slug])
    if quiz.directed:
        endereco_canonico = url_da_experiencia(
            quiz,
            {"context": {chave: contexto.get(chave) for chave in ("v", "fmt", "seg")}},
        )
    resposta = render(
        request,
        "quiz/formulario.html",
        {
            "quiz": quiz,
            "versao": versao,
            "questions": questions,
            "erro": erro,
            "valores": valores,
            "opcoes_selecionadas": opcoes_selecionadas,
            "etapa_inicial": etapa_inicial,
            "etapa_lead_ativa": etapa_inicial >= questions.count(),
            "campo_com_erro": campo_com_erro,
            "entrada": entrada,
            "experiencia": experiencia,
            "calculadora_url": reverse("quiz-calcular", args=[quiz.slug]),
            "canonical": request.build_absolute_uri(endereco_canonico),
        },
        status=503 if experiencia and experiencia["fmt"] == "ai" else status,
    )
    return _escrever_cookie(resposta, request, quiz.slug, entrada)


def _ir_ao_resultado(request, quiz, entrada, submissao):
    destino = reverse("quiz-resultado", args=[quiz.slug])
    resposta = redirect(f"{destino}?lead={submissao.id}")
    return gravar_cookie(_escrever_cookie(resposta, request, quiz.slug, entrada), request, submissao)


def formulario(request, slug):
    quiz = _quiz_do_site(request, slug)
    if quiz.directed and request.method == "GET" and not request.GET.get("v"):
        return render(request, "quiz/campanha.html", {"quiz": quiz})
    entrada, versao = resolver_sessao(request, quiz)
    if quiz.directed and (entrada.get("context") or {}).get("fmt") in ("ai", "ai_agent"):
        # Importado aqui: conversa.py importa este módulo.
        from .conversa import formulario_ai

        return formulario_ai(request, quiz, versao, entrada)
    questions = versao.questions.prefetch_related("options")

    if request.method != "POST":
        # Retomar uma sessão já concluída é voltar ao resultado dela. O
        # formulário em branco pediria respostas que o reenvio idempotente
        # (quiz + session_id) descartaria sem avisar.
        concluida = Submission.objects.filter(
            quiz=quiz, session_id=entrada["session_id"]
        ).first()
        if concluida is not None:
            return _ir_ao_resultado(request, quiz, entrada, concluida)
        return _render_formulario(request, quiz, versao, questions, entrada)

    email = request.POST.get("email", "").strip()
    if not email:
        return _render_formulario(
            request,
            quiz,
            versao,
            questions,
            entrada,
            erro="Informe seu e-mail para ver o resultado.",
            status=422,
            etapa_inicial=questions.count(),
            campo_com_erro="email",
        )
    try:
        if len(email) > LIMITES_DO_CONTATO["email"]:
            raise ValidationError("e-mail maior que a coluna")
        validate_email(email)
    except ValidationError:
        return _render_formulario(
            request,
            quiz,
            versao,
            questions,
            entrada,
            erro="Informe um e-mail válido para continuar.",
            status=422,
            etapa_inicial=questions.count(),
            campo_com_erro="email",
        )
    for campo in ("nome", "telefone"):
        limite = LIMITES_DO_CONTATO[campo]
        if len(request.POST.get(campo, "").strip()) > limite:
            return _render_formulario(
                request,
                quiz,
                versao,
                questions,
                entrada,
                erro=f"Use até {limite} caracteres no {campo}.",
                status=422,
                etapa_inicial=questions.count(),
                campo_com_erro=campo,
            )

    score = 0
    respostas: dict[int, int] = {}
    for indice, question in enumerate(questions):
        valor = request.POST.get(f"pergunta_{question.id}")
        if valor is None:
            return _render_formulario(
                request,
                quiz,
                versao,
                questions,
                entrada,
                erro="Responda todas as perguntas para ver o resultado.",
                status=422,
                etapa_inicial=indice,
            )
        if not valor.isdecimal():
            raise Http404("opção inválida para esta pergunta")
        # [pontuação só no servidor] a opção é buscada no banco pela pergunta;
        # um id de opção que não pertence a esta pergunta é resposta adulterada.
        opcao = question.options.filter(id=valor).first()
        if opcao is None:
            raise Http404("opção inválida para esta pergunta")
        respostas[question.id] = opcao.id
        score += opcao.points

    banda = versao.bands.filter(min_score__lte=score, max_score__gte=score).first()
    result_key = banda.key if banda is not None else "sem_faixa"
    utm = entrada.get("utm") or {}

    with transaction.atomic():
        submissao, criada = Submission.objects.get_or_create(
            quiz=quiz,
            session_id=entrada["session_id"],
            defaults={
                "version": versao,
                "site_id": quiz.site_id,
                "score": score,
                "result_key": result_key,
                "answers": respostas,
                "lead_email": email,
                "lead_name": request.POST.get("nome", "").strip(),
                "lead_phone": request.POST.get("telefone", "").strip(),
                "utm": utm,
                "context": entrada.get("context") or {},
            },
        )
        if criada:
            # [RECEITA:R3 v1] mesma transação do resultado
            emitir_quiz_completado(quiz, submissao)
            transaction.on_commit(relay_apos_commit)

    return _ir_ao_resultado(request, quiz, entrada, submissao)


@require_POST
def refazer(request, slug):
    """Refazer é começar uma sessão nova do quiz.

    O envio antigo fica gravado; só o cookie deixa de apontar para ele, e a
    volta ao formulário abre em branco. POST com token porque um pré-carregamento
    de link por GET desfaria a volta ao resultado de quem nem clicou.
    """
    quiz = _quiz_do_site(request, slug)
    if quiz.directed:
        quizzes = _ler_quizzes(request)
        tentativa = request.POST.get("quiz_attempt")
        if not tentativa:
            raise Http404("tentativa indisponível")
        anterior = entrada_da_tentativa(quizzes, quiz.slug, tentativa)
        if not _entrada_usavel(anterior) or anterior["site_id"] != quiz.site_id:
            raise Http404("tentativa indisponível")
        versao = quiz.versions.filter(pk=anterior["version_id"], active=True).first()
        if not versao:
            raise Http404("versão indisponível")
        entrada = {**anterior, "session_id": str(uuid.uuid4())}
        return _escrever_cookie(
            redirect(url_da_experiencia(quiz, entrada)), request, quiz.slug, entrada
        )
    anterior, _ = resolver_sessao(request, quiz)
    session_id = uuid.uuid4()
    versao = escolher_versao(quiz, session_id)
    entrada = {
        "session_id": str(session_id),
        "version_id": versao.id,
        "version_key": versao.key,
        "site_id": quiz.site_id,
        "utm": anterior["utm"],
    }
    resposta = redirect("quiz-formulario", slug=quiz.slug)
    return _escrever_cookie(resposta, request, quiz.slug, entrada)


def resultado(request, slug):
    quiz = _quiz_do_site(request, slug)
    try:
        submissao_id = uuid.UUID(request.GET.get("lead", ""))
    except ValueError:
        raise Http404("lead inválido")
    submissao = get_object_or_404(
        Submission, id=submissao_id, quiz=quiz, site_id=quiz.site_id
    )
    banda = None
    if submissao.version_id:
        banda = submissao.version.bands.filter(key=submissao.result_key).first()
    entrada = (
        entrada_da_tentativa(
            _ler_quizzes(request), quiz.slug, str(submissao.session_id)
        )
        if quiz.directed
        else _ler_quizzes(request).get(quiz.slug)
    )
    propria = (
        _entrada_usavel(entrada)
        and entrada["site_id"] == quiz.site_id
        and str(entrada["session_id"]) == str(submissao.session_id)
    )
    oferta = None
    demonstracao = False
    if quiz.directed:
        contexto = submissao.context
        experiencia = resolver_experiencia(
            submissao.version, contexto.get("fmt"), contexto.get("seg")
        )
        dados = submissao.version.experience
        oferta_id = dados.get("band_offers", {}).get(submissao.result_key)
        oferta = dados.get("ofertas", {}).get(oferta_id)
        demonstracao = bool(oferta and not oferta.get("checkout_url"))
        if banda:
            substituicoes = experiencia.get("results", {}).get(banda.key, {})
            banda = SimpleNamespace(
                **{
                    chave: substituicoes.get(chave, getattr(banda, chave))
                    for chave in (
                        "title",
                        "description",
                        "botao_rotulo",
                        "botao_destino",
                    )
                }
            )
            if demonstracao:
                banda.botao_rotulo = substituicoes.get("botao_rotulo") or next(
                    (
                        faixa["botao_rotulo"]
                        for faixa in dados["documento"]["versao"]["faixas"]
                        if faixa["key"] == submissao.result_key
                    ),
                    "Conhecer a oferta",
                )
    return render(
        request,
        "quiz/resultado.html",
        {
            "quiz": quiz,
            "submissao": submissao,
            "banda": banda,
            "entrada": entrada if propria else None,
            "saida_rastreavel": propria,
            "saida_com_formulario": bool(
                propria and banda and (
                    banda.botao_destino.startswith("https://")
                    or banda.botao_destino.startswith("/checkout/")
                )
            ),
            "demonstracao": demonstracao,
            "oferta": oferta,
            "recomecar_url": url_da_experiencia(
                quiz, {"context": submissao.context, "utm": submissao.utm}
            ),
            "canonical": request.build_absolute_uri(
                reverse("quiz-resultado", args=[quiz.slug]) + f"?lead={submissao.id}"
            ),
        },
    )


def _submissao_da_sessao(request, quiz):
    tentativa = request.POST.get("quiz_attempt")
    if quiz.directed and not tentativa:
        raise Http404("tentativa indisponível")
    entrada = (
        entrada_da_tentativa(_ler_quizzes(request), quiz.slug, tentativa)
        if quiz.directed
        else _ler_quizzes(request).get(quiz.slug)
    )
    if not _entrada_usavel(entrada) or entrada["site_id"] != quiz.site_id:
        raise Http404("tentativa indisponível")
    submissao = get_object_or_404(
        Submission, quiz=quiz, site_id=quiz.site_id, session_id=entrada["session_id"]
    )
    if request.POST.get("resposta") and request.POST["resposta"] != str(submissao.id):
        raise Http404("resposta indisponível")
    return submissao, entrada


@require_POST
def sair(request, slug):
    quiz = _quiz_do_site(request, slug)
    submissao, entrada = _submissao_da_sessao(request, quiz)
    banda = get_object_or_404(submissao.version.bands, key=submissao.result_key)
    destino = banda.botao_destino
    if destino.startswith("/checkout/"):
        destino = f"https://{request.site['host']}{destino}"
    try:
        endereco = destino_com_parametros(
            destino,
            submissao.utm,
            submissao.context,
            tentativa=submissao.session_id,
            quiz_slug=quiz.slug,
        )
    except ValueError:
        raise Http404("destino indisponível")
    partes = urlsplit(endereco)
    if partes.hostname == request.site["host"] and partes.path.startswith("/checkout/"):
        parametros = dict(parse_qsl(partes.query, keep_blank_values=True))
        parametros["lead"] = str(submissao.id)
        endereco = urlunsplit(partes._replace(query=urlencode(parametros)))
    metadados = {"utm": submissao.utm}
    if submissao.context:
        metadados["context"] = submissao.context
    TelemetryEvent.objects.get_or_create(
        session_id=submissao.session_id,
        site_id=quiz.site_id,
        quiz_slug=quiz.slug,
        version_key=submissao.version.key,
        event_type="checkout_exit",
        defaults={
            "element_id": banda.key,
            "metadata": metadados,
            "occurred_at": timezone.now(),
        },
    )
    resposta = redirect(endereco)
    resposta["Referrer-Policy"] = "no-referrer"
    resposta["Cache-Control"] = "no-store"
    return resposta


@require_POST
def demonstracao(request, slug):
    quiz = _quiz_do_site(request, slug)
    submissao, entrada = _submissao_da_sessao(request, quiz)
    dados = submissao.version.experience
    oferta = dados.get("ofertas", {}).get(
        dados.get("band_offers", {}).get(submissao.result_key)
    )
    if not quiz.directed or not oferta or oferta.get("checkout_url"):
        raise Http404("demonstração indisponível")
    # A demonstração é a saída enquanto o checkout não chega: conta como
    # clique de saída, marcado para não se confundir com o checkout real.
    metadados = {"utm": submissao.utm, "demonstracao": True, "oferta_id": oferta["id"]}
    if submissao.context:
        metadados["context"] = submissao.context
    TelemetryEvent.objects.get_or_create(
        session_id=submissao.session_id,
        site_id=quiz.site_id,
        quiz_slug=quiz.slug,
        version_key=submissao.version.key,
        event_type="checkout_exit",
        defaults={
            "element_id": submissao.result_key,
            "metadata": metadados,
            "occurred_at": timezone.now(),
        },
    )
    return render(
        request,
        "quiz/demonstracao.html",
        {"quiz": quiz, "oferta": oferta, "submissao": submissao},
    )


@require_POST
def calcular(request, slug):
    quiz = _quiz_do_site(request, slug)
    if not quiz.directed:
        raise Http404("calculadora indisponível")
    entrada, versao = resolver_sessao(request, quiz)
    contexto = entrada.get("context") or {}
    experiencia = resolver_experiencia(versao, contexto.get("fmt"), contexto.get("seg"))
    if experiencia["fmt"] != "calc":
        raise Http404("calculadora indisponível")
    try:
        valor = calcular_experiencia(experiencia["calculator"], request.POST)
    except ValueError as erro:
        return JsonResponse({"erro": str(erro)}, status=422)
    return JsonResponse({"resultado": valor})


def _quando(valor):
    if not isinstance(valor, str) or not valor:
        return timezone.now()
    try:
        instante = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return timezone.now()
    if timezone.is_naive(instante):
        instante = timezone.make_aware(instante, datetime_timezone.utc)
    return instante


@csrf_exempt
@require_POST
def telemetria(request):
    """Valida o cookie assinado e empurra o evento para o Redis. Sem banco."""
    if len(request.body) > LIMITE_CORPO:
        return HttpResponse(status=413)
    try:
        corpo = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponse(status=400)
    if not isinstance(corpo, dict):
        return HttpResponse(status=400)
    slug = corpo.get("quiz_slug")
    entrada = entrada_da_tentativa(_ler_quizzes(request), slug, corpo.get("session_id"))
    if not isinstance(slug, str) or not _entrada_usavel(entrada):
        return HttpResponse(status=401)
    tipo = corpo.get("event_type")
    if not isinstance(tipo, str) or tipo not in TIPOS_DE_EVENTO:
        return HttpResponse(status=400)
    element_id = corpo.get("element_id") or ""
    if not isinstance(element_id, str) or len(element_id) > LIMITE_ELEMENTO:
        return HttpResponse(status=400)
    metadata = corpo.get("metadata") or {}
    if not isinstance(metadata, dict):
        return HttpResponse(status=400)
    metadata = {
        chave: valor
        for chave, valor in metadata.items()
        if chave not in {"utm", "context"}
    }
    metadata["utm"] = entrada.get("utm") or {}
    if entrada.get("context"):
        metadata["context"] = entrada["context"]
    envelope = {
        "session_id": entrada["session_id"],
        "site_id": entrada["site_id"],
        "quiz_slug": slug,
        "version_key": entrada["version_key"],
        "event_type": tipo,
        "element_id": element_id,
        "occurred_at": _quando(corpo.get("occurred_at")).isoformat(),
        "metadata": metadata,
    }
    try:
        publicar_telemetria(envelope)
    except (RedisError, KeyError, OSError):
        return HttpResponse(status=503)
    return HttpResponse(status=204)


def digitos_do_telefone(telefone: str) -> str:
    return "".join(c for c in telefone if c.isdigit())


def _email_da_captura(valor: str) -> str:
    """E-mail utilizável ou vazio. Captura é melhor esforço: não reclama."""
    if not valor or len(valor) > LIMITES_DO_CONTATO["email"]:
        return ""
    try:
        validate_email(valor)
    except ValidationError:
        return ""
    return valor


def _telefone_da_captura(valor: str) -> str:
    if not valor or len(valor) > LIMITES_DO_CONTATO["telefone"]:
        return ""
    return valor if 8 <= len(digitos_do_telefone(valor)) <= 15 else ""


@require_POST
def captura(request, slug):
    """Contato informado antes de concluir: grava e avisa o CRM uma vez.

    A página chama esta rota quando a pessoa preenche e-mail ou telefone (e ao
    sair da página sem concluir). Corpo = os mesmos campos do formulário,
    com o token CSRF. A sessão vem do cookie assinado; sem ela não há o que
    registrar. Uma captura por (quiz, sessão): reenviar só completa a linha e
    nunca publica outro `quiz.captura_parcial`.
    """
    quiz = _quiz_do_site(request, slug)
    quizzes = _ler_quizzes(request)
    entrada = (
        entrada_da_tentativa(quizzes, quiz.slug, request.POST.get("quiz_attempt"))
        if quiz.directed
        else quizzes.get(quiz.slug)
    )
    if not _entrada_usavel(entrada) or entrada["site_id"] != quiz.site_id:
        return JsonResponse({"estado": "sem_sessao"}, status=404)
    versao = quiz.versions.filter(pk=entrada["version_id"]).first()
    if versao is None:
        return JsonResponse({"estado": "sem_sessao"}, status=404)
    session_id = entrada["session_id"]
    if Submission.objects.filter(quiz=quiz, session_id=session_id).exists():
        return JsonResponse({"estado": "concluida"})

    email = _email_da_captura(request.POST.get("email", "").strip())
    telefone = _telefone_da_captura(request.POST.get("telefone", "").strip())
    nome = request.POST.get("nome", "").strip()[: LIMITES_DO_CONTATO["nome"]]
    if not email and not telefone:
        return JsonResponse({"estado": "sem_contato"}, status=422)

    respostas = {}
    for question in versao.questions.prefetch_related("options"):
        valor = request.POST.get(f"pergunta_{question.id}", "")
        if not valor.isdecimal():
            continue
        if any(option.id == int(valor) for option in question.options.all()):
            respostas[str(question.id)] = int(valor)

    with transaction.atomic():
        registro, criada = CapturaParcial.objects.select_for_update().get_or_create(
            quiz=quiz,
            session_id=session_id,
            defaults={
                "version": versao,
                "site_id": quiz.site_id,
                "lead_email": email,
                "lead_name": nome,
                "lead_phone": telefone,
                "answers": respostas,
                "utm": entrada.get("utm") or {},
                "context": entrada.get("context") or {},
            },
        )
        if not criada:
            # Completa, nunca apaga: um campo vazio agora não desfaz o anterior.
            if email:
                registro.lead_email = email
            if nome:
                registro.lead_name = nome
            if telefone:
                registro.lead_phone = telefone
            registro.answers = {**(registro.answers or {}), **respostas}
            registro.save()
        else:
            payload = {
                "captura_id": str(registro.id),
                "site_id": registro.site_id,
                "sessao": str(registro.session_id),
                "quiz_slug": quiz.slug,
                "version_key": versao.key,
                "lead": lead_do_contato(email, nome, telefone),
                "respostas": respostas_legiveis(versao, respostas),
                "utm": registro.utm,
            }
            if registro.context:
                payload["context"] = registro.context
            OutboxEvent.objects.create(event="quiz.captura_parcial", payload=payload)
            transaction.on_commit(relay_apos_commit)
    resposta = JsonResponse(
        {"estado": "registrada" if criada else "atualizada"},
        status=201 if criada else 200,
    )
    resposta["Cache-Control"] = "no-store"
    return resposta
