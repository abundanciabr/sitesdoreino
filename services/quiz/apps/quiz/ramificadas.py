"""Formulário ramificado, uma pergunta por vez, inclusive sem JavaScript."""
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from . import consentimento
from .direcionadas import url_da_experiencia
from .experiencias import resolver_experiencia
from .models import Submission
from .ramificacao import preparar, percurso

SALT = "quiz-ramificado-v1"


def formulario_ramificado(request, quiz, versao, entrada):
    from .views import _escrever_cookie, _ir_ao_resultado, _concluir_formulario, LIMITES_DO_CONTATO
    from .conversa import _registrar

    concluida = Submission.objects.filter(quiz=quiz, session_id=entrada["session_id"]).first()
    if concluida:
        return _ir_ao_resultado(request, quiz, entrada, concluida)
    perguntas = preparar(versao)
    estado = {"sessao": entrada["session_id"], "versao": versao.id, "r": {}}
    erro, status = None, 200
    if request.method == "POST":
        try:
            recebido = signing.loads(request.POST.get("estado_ramo", ""), salt=SALT, max_age=7 * 86400)
            if recebido["sessao"] != estado["sessao"] or recebido["versao"] != versao.id or not isinstance(recebido["r"], dict):
                raise signing.BadSignature()
            estado = recebido
        except (signing.BadSignature, KeyError, TypeError):
            erro, status = "Esta etapa expirou. Recomece pelas opções abaixo.", 422
        if not erro:
            caminho, atual = percurso(perguntas, estado["r"])
            acao = request.POST.get("acao")
            if acao == "voltar":
                respondidas = [q for q in caminho if str(q.id) in estado["r"]]
                if respondidas:
                    estado["r"].pop(str(respondidas[-1].id))
            elif atual is not None:
                valor = request.POST.get("opcao", "")
                if not any(str(o.id) == valor for o in atual.options.all()):
                    erro, status = "Escolha uma resposta para continuar.", 422
                else:
                    estado["r"][str(atual.id)] = int(valor)
                    _registrar(quiz, entrada, "click_option", valor, {"question_id": str(atual.id)})
            elif acao == "concluir":
                email = request.POST.get("email", "").strip()
                try:
                    validate_email(email)
                    if len(email) > LIMITES_DO_CONTATO["email"]:
                        raise ValidationError("")
                except ValidationError:
                    erro, status = "Informe um e-mail válido para ver o resultado.", 422
                for campo in ("nome", "telefone"):
                    if len(request.POST.get(campo, "").strip()) > LIMITES_DO_CONTATO[campo]:
                        erro, status = f"O campo {campo} está longo demais.", 422
                if not erro:
                    # As respostas chegam do estado assinado, não de campos ocultos editáveis.
                    corpo = request.POST.copy()
                    for q in caminho:
                        corpo[f"pergunta_{q.id}"] = str(estado["r"][str(q.id)])
                    request.POST = corpo
                    ids = [q.id for q in caminho]
                    return _concluir_formulario(request, quiz, versao, versao.questions.filter(id__in=ids).prefetch_related("options"), entrada)
    caminho, atual = percurso(perguntas, estado["r"])
    # Ao voltar ou trocar uma resposta, nenhuma resposta fora do caminho sobrevive.
    ids = {str(q.id) for q in caminho}
    estado["r"] = {k: v for k, v in estado["r"].items() if k in ids}
    contexto = entrada.get("context") or {}
    experiencia = resolver_experiencia(versao, contexto.get("fmt"), contexto.get("seg"))
    _registrar(quiz, entrada, "view_quiz")
    if atual:
        _registrar(quiz, entrada, "view_question", atual.id)
    resposta = render(request, "quiz/ramificado.html", {
        "quiz": quiz, "versao": versao, "entrada": entrada, "experiencia": experiencia,
        "calculadora_url": reverse("quiz-calcular", args=[quiz.slug]),
        "atual": atual, "etapa": len(estado["r"]) + 1,
        "pode_voltar": bool(estado["r"]), "estado_ramo": signing.dumps(estado, salt=SALT, compress=True),
        "erro": erro, "valores": request.POST,
        "texto_consentimento_whatsapp": consentimento.TEXTO_WHATSAPP,
        "aceita_whatsapp_marcada": consentimento.marcou(request.POST),
        "canonical": request.build_absolute_uri(url_da_experiencia(quiz, {"context": {k: contexto.get(k) for k in ("v", "fmt", "seg")}})),
    }, status=status)
    resposta["Cache-Control"] = "no-store"
    return _escrever_cookie(resposta, request, quiz.slug, entrada)
