"""Quiz e respostas de cada contato: captura parcial, quiz completo e consulta.

O quiz manda as respostas já legíveis (texto da pergunta e das opções). Esta
célula guarda o que a ficha e o agente precisam ler, uma linha por tentativa:
a captura parcial abre a linha e o quiz completo a conclui, sem duplicar a
linha nem a oportunidade da oferta.
"""

import logging
import uuid

from django.db import transaction
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError
from django.http import JsonResponse

from .models import Lead, QuizDoLead, TimelineEvent

log = logging.getLogger("leads.quiz_do_lead")

router = Router()

LIMITE_DE_RESPOSTAS = 200
LIMITE_DE_TEXTO = 2000


# ---------------------------------------------------------------------------
# Leitura tolerante dos eventos do quiz
# ---------------------------------------------------------------------------


def _texto(valor, limite=LIMITE_DE_TEXTO) -> str:
    if valor is None:
        return ""
    if not isinstance(valor, str):
        valor = str(valor)
    return valor.strip()[:limite]


def respostas_legiveis(bruto) -> list:
    """Normaliza a lista do quiz para {pergunta_id, pergunta, respostas, valor_livre}."""
    if not isinstance(bruto, list):
        return []
    saida = []
    for item in bruto[:LIMITE_DE_RESPOSTAS]:
        if not isinstance(item, dict):
            continue
        opcoes = item.get("respostas")
        if not isinstance(opcoes, list):
            opcoes = []
        escolhidas = []
        for opcao in opcoes[:LIMITE_DE_RESPOSTAS]:
            if isinstance(opcao, dict):
                escolhidas.append({
                    "id": _texto(opcao.get("id"), 100),
                    "texto": _texto(opcao.get("texto")),
                })
            elif isinstance(opcao, str):
                escolhidas.append({"id": "", "texto": _texto(opcao)})
        livre = item.get("valor_livre")
        saida.append({
            "pergunta_id": _texto(item.get("pergunta_id"), 100),
            "pergunta": _texto(item.get("pergunta")),
            "respostas": escolhidas,
            "valor_livre": _texto(livre) if livre not in (None, "") else None,
        })
    return saida


def _slug(data: dict) -> str:
    quiz = data.get("quiz_slug") or data.get("quiz")
    if isinstance(quiz, dict):
        quiz = quiz.get("slug")
    return _texto(quiz, 100) or "quiz"


def _sessao(data: dict) -> str:
    return _texto(data.get("session_id") or data.get("sessao"), 100)


def _submissao(data: dict) -> str:
    return _texto(data.get("submission_id") or data.get("submissao_id"), 100)


def _versao(data: dict) -> str:
    return _texto(data.get("version_key") or data.get("versao"), 100)


def _utm(data: dict) -> dict:
    for chave in ("utm", "origem"):
        valor = data.get(chave)
        if isinstance(valor, dict):
            return {str(k): _texto(v, 500) for k, v in valor.items()}
    return {}


def _campanha(data: dict, utm: dict) -> str:
    return _texto(data.get("campanha") or utm.get("utm_campaign"), 200)


def _pontuacao(data: dict):
    valor = data.get("score")
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _contato(data: dict) -> dict:
    bruto = data.get("contato") or data.get("lead") or {}
    if not isinstance(bruto, dict):
        bruto = {}
    return {
        "email": _texto(bruto.get("email"), 254),
        "nome": _texto(bruto.get("nome") or bruto.get("name"), 200),
        "telefone": _texto(bruto.get("telefone") or bruto.get("phone"), 50),
    }


# ---------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------


def _tentativa(lead, slug, sessao, *, completo: bool):
    """A linha da tentativa que este evento continua, ou None para criar outra.

    Com sessão, a tentativa é a da mesma sessão. Sem sessão (quiz completo de
    versões antigas do quiz), o completo conclui a captura parcial mais recente
    ainda aberta do mesmo quiz.
    """
    base = QuizDoLead.objects.select_for_update().filter(lead=lead, quiz_slug=slug)
    if sessao:
        achada = base.filter(sessao=sessao).first()
        if achada is not None or not completo:
            return achada
        return base.filter(situacao="parcial", sessao="").order_by("-criado_em").first()
    if completo:
        return base.filter(situacao="parcial").order_by("-criado_em").first()
    return None


def registrar_quiz_completo(lead, event_id, data: dict, momento=None) -> QuizDoLead:
    slug = _slug(data)
    sessao = _sessao(data)
    utm = _utm(data)
    tentativa = _tentativa(lead, slug, sessao, completo=True)
    if tentativa is None:
        tentativa = QuizDoLead(lead=lead, quiz_slug=slug, sessao=sessao)
    respostas = respostas_legiveis(data.get("respostas"))
    if respostas or not tentativa.respostas:
        tentativa.respostas = respostas
    if sessao and not tentativa.sessao:
        tentativa.sessao = sessao
    tentativa.situacao = "completo"
    tentativa.submissao_id = _submissao(data) or tentativa.submissao_id
    tentativa.versao = _versao(data) or tentativa.versao
    tentativa.resultado = _texto(data.get("result_key"), 100)
    tentativa.pontuacao = _pontuacao(data)
    tentativa.utm = utm or tentativa.utm
    tentativa.campanha = _campanha(data, utm) or tentativa.campanha
    tentativa.ultimo_event_id = event_id
    tentativa.completado_em = tentativa.completado_em or momento or timezone.now()
    tentativa.save()
    return tentativa


def ao_quiz_captura_parcial(event_id: str, data: dict) -> None:
    """A pessoa deixou contato e ainda não terminou o quiz.

    Cria ou atualiza o contato com origem no quiz e abre a oportunidade da
    oferta do quiz, a mesma que o quiz completo usa depois. Capturas seguintes
    da mesma sessão só atualizam as respostas.
    """
    from .handlers import _upsert_lead
    from .oferta import abrir_oferta_do_quiz

    site_id = _texto(data.get("site_id") or data.get("site"), 100)
    contato = _contato(data)
    if not site_id or not (contato["email"] or contato["telefone"]):
        log.warning("captura parcial sem site ou contato; evento %s ignorado", event_id)
        return
    slug = _slug(data)
    sessao = _sessao(data)
    utm = _utm(data)
    with transaction.atomic():
        if contato["email"]:
            lead = _upsert_lead(
                site_id=site_id, email=contato["email"], name=contato["nome"],
                phone=contato["telefone"], source=f"quiz:{slug}", utm=utm,
            )
        else:
            lead = (Lead.objects.filter(site_id=site_id, phone=contato["telefone"])
                    .order_by("created_at").first())
            if lead is None:
                log.warning("captura parcial só com telefone desconhecido; evento %s ignorado",
                            event_id)
                return
        lead = Lead.objects.select_for_update().get(pk=lead.pk)
        tentativa = _tentativa(lead, slug, sessao, completo=False)
        nova = tentativa is None
        if nova:
            tentativa = QuizDoLead(lead=lead, quiz_slug=slug, sessao=sessao)
        if tentativa.situacao != "completo":
            respostas = respostas_legiveis(data.get("respostas"))
            if len(respostas) >= len(tentativa.respostas or []):
                tentativa.respostas = respostas
            tentativa.versao = _versao(data) or tentativa.versao
            tentativa.utm = utm or tentativa.utm
            tentativa.campanha = _campanha(data, utm) or tentativa.campanha
            tentativa.ultimo_event_id = event_id
            tentativa.save()
        if not nova:
            return
        evento = TimelineEvent.objects.create(
            lead=lead, event="quiz.captura_parcial", event_id=event_id, payload=data
        )
        abrir_oferta_do_quiz(lead, {"quiz_slug": slug}, event_id, evento)


# ---------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------


def _data(valor):
    return valor.isoformat() if valor else None


def como_quiz(tentativa: QuizDoLead) -> dict:
    return {
        "id": str(tentativa.id),
        "quiz_slug": tentativa.quiz_slug,
        "situacao": tentativa.situacao,
        "sessao": tentativa.sessao,
        "submissao_id": tentativa.submissao_id,
        "versao": tentativa.versao,
        "resultado": tentativa.resultado,
        "pontuacao": tentativa.pontuacao,
        "respostas": tentativa.respostas,
        "utm": tentativa.utm,
        "campanha": tentativa.campanha,
        "criado_em": _data(tentativa.criado_em),
        "atualizado_em": _data(tentativa.atualizado_em),
        "completado_em": _data(tentativa.completado_em),
    }


def quizzes_do_lead(lead, quiz_slug: str = "") -> list:
    consulta = lead.quizzes.all()
    if quiz_slug:
        consulta = consulta.filter(quiz_slug=quiz_slug)
    return [como_quiz(item) for item in consulta.order_by("-atualizado_em", "-id")[:50]]


def lead_ou_404(lead_id) -> Lead:
    try:
        chave = uuid.UUID(str(lead_id))
    except (ValueError, TypeError, AttributeError):
        raise HttpError(404, "Lead inexistente")
    lead = Lead.objects.filter(pk=chave).first()
    if lead is None:
        raise HttpError(404, "Lead inexistente")
    return lead


@router.get(
    "/leads/{lead_id}/respostas",
    operation_id="getRespostasDoLead",
    summary="Quizzes do contato com perguntas e respostas legíveis, do mais recente ao mais antigo",
)
def respostas_do_lead(request, lead_id: str, quiz_slug: str = ""):
    from .crm import _admin

    _admin(request)
    lead = lead_ou_404(lead_id)
    return JsonResponse({
        "lead_id": str(lead.id),
        "site_id": lead.site_id,
        "quizzes": quizzes_do_lead(lead, quiz_slug),
    })
