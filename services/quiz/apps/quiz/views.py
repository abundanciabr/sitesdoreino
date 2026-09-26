import json
import uuid
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core import signing
from django.core.validators import validate_email
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from redis.exceptions import RedisError

from .models import OutboxEvent, Quiz, QuizVersion, Submission
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
    response.set_cookie(
        COOKIE_SESSAO,
        signing.dumps({"quizzes": quizzes}, salt=SALT_SESSAO),
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
        },
        status=status,
    )
    return _escrever_cookie(resposta, request, quiz.slug, entrada)


def _ir_ao_resultado(request, quiz, entrada, submissao):
    destino = reverse("quiz-resultado", args=[quiz.slug])
    resposta = redirect(f"{destino}?lead={submissao.id}")
    return _escrever_cookie(resposta, request, quiz.slug, entrada)


def formulario(request, slug):
    quiz = _quiz_do_site(request, slug)
    entrada, versao = resolver_sessao(request, quiz)
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
            },
        )
        if criada:
            lead = {"email": submissao.lead_email}
            if submissao.lead_name:
                lead["name"] = submissao.lead_name
            if submissao.lead_phone:
                lead["phone"] = submissao.lead_phone
            OutboxEvent.objects.create(  # [RECEITA:R3 v1] [INV-P6] mesma transação do resultado
                event="quiz.completado",
                payload={
                    "site_id": submissao.site_id,
                    "quiz_slug": quiz.slug,
                    "result_key": submissao.result_key,
                    "score": submissao.score,
                    "version_key": submissao.version.key,
                    "lead": lead,
                    "utm": submissao.utm,
                },
            )
            transaction.on_commit(relay_apos_commit)

    return _ir_ao_resultado(request, quiz, entrada, submissao)


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
    return render(
        request,
        "quiz/resultado.html",
        {"quiz": quiz, "submissao": submissao, "banda": banda},
    )


def _quando(valor):
    if not isinstance(valor, str) or not valor:
        return timezone.now()
    try:
        instante = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return timezone.now()
    if timezone.is_naive(instante):
        instante = timezone.make_aware(instante, timezone.utc)
    return instante


@csrf_exempt
@require_POST
def telemetria(request):
    """Valida o cookie assinado e empurra o evento para o Redis. Sem banco."""
    if len(request.body) > LIMITE_CORPO:
        return HttpResponse(status=413)
    try:
        corpo = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)
    if not isinstance(corpo, dict):
        return HttpResponse(status=400)
    slug = corpo.get("quiz_slug")
    entrada = _ler_quizzes(request).get(slug)
    if not isinstance(slug, str) or not _entrada_usavel(entrada):
        return HttpResponse(status=401)
    tipo = corpo.get("event_type")
    if tipo not in TIPOS_DE_EVENTO:
        return HttpResponse(status=400)
    element_id = corpo.get("element_id") or ""
    if not isinstance(element_id, str) or len(element_id) > LIMITE_ELEMENTO:
        return HttpResponse(status=400)
    metadata = corpo.get("metadata") or {}
    if not isinstance(metadata, dict):
        return HttpResponse(status=400)
    metadata = {chave: valor for chave, valor in metadata.items() if chave != "utm"}
    metadata["utm"] = entrada.get("utm") or {}
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
