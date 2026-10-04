"""Quiz e respostas de cada contato: captura parcial, quiz completo e consulta.

O quiz manda as respostas já legíveis (texto da pergunta e das opções). Esta
célula guarda o que a ficha e o agente precisam ler, uma linha por tentativa:
a captura parcial abre a linha e o quiz completo a conclui, sem duplicar a
linha nem a oportunidade da oferta.
"""

import logging
import re
import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Func, Value
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError
from django.http import JsonResponse

from .models import (
    Lead, Oportunidade, QuizDoLead, RegistroHistoricoOportunidade, TimelineEvent,
)
from .oferta import PASSO_DA_CAPTURA

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


def _captura_id(data: dict) -> str:
    return _texto(data.get("captura_parcial_id") or data.get("captura_id"), 100)


def _site(data: dict) -> str:
    return _texto(data.get("site_id") or data.get("site"), 100)


def _digitos(telefone) -> str:
    return re.sub(r"\D", "", telefone or "")


def _variantes_do_telefone(telefone) -> set:
    """O mesmo número com e sem o 55 do Brasil; número curto não identifica ninguém."""
    digitos = _digitos(telefone)
    if not 8 <= len(digitos) <= 15:
        return set()
    variantes = {digitos}
    if digitos.startswith("55") and len(digitos) >= 12:
        variantes.add(digitos[2:])
    elif len(digitos) in (10, 11):
        variantes.add("55" + digitos)
    return variantes


def _leads_do_telefone(site_id, telefone):
    variantes = _variantes_do_telefone(telefone)
    if not variantes:
        return Lead.objects.none()
    return (
        Lead.objects.filter(site_id=site_id)
        .exclude(phone="")
        .annotate(_digitos=Func(F("phone"), Value(r"\D"), Value(""), Value("g"),
                                function="regexp_replace"))
        .filter(_digitos__in=variantes)
    )


def _tentativa_da_sessao(site_id, slug, sessao, captura_id):
    """A tentativa já registrada desta sessão do quiz, em qualquer contato do site.

    A captura e o completo da mesma sessão são a mesma tentativa, mesmo quando
    o e-mail mudou entre uma e outro.
    """
    if not (sessao or captura_id):
        return None
    base = (QuizDoLead.objects.select_for_update(of=("self",))
            .filter(lead__site_id=site_id, quiz_slug=slug))
    if captura_id:
        achada = base.filter(captura_id=captura_id).first()
        if achada is not None:
            return achada
    if sessao:
        return base.filter(sessao=sessao).order_by("criado_em", "id").first()
    return None


def _tentativa(lead, slug, sessao, *, completo: bool, captura_id: str = ""):
    """A linha da tentativa que este evento continua, ou None para criar outra.

    Com sessão, a tentativa é a da mesma sessão. Sem sessão (quiz completo de
    versões antigas do quiz), o completo conclui a captura parcial mais recente
    ainda aberta do mesmo quiz.
    """
    base = QuizDoLead.objects.select_for_update().filter(lead=lead, quiz_slug=slug)
    if captura_id:
        achada = base.filter(captura_id=captura_id).first()
        if achada is not None:
            return achada
    if sessao:
        achada = base.filter(sessao=sessao).first()
        if achada is not None or not completo:
            return achada
        return base.filter(situacao="parcial", sessao="").order_by("-criado_em").first()
    if completo:
        return base.filter(situacao="parcial").order_by("-criado_em").first()
    return None


def _so_desta_captura(lead, tentativa) -> bool:
    """O contato nasceu desta captura e não tem mais nada: pode receber o e-mail certo."""
    if not lead.email:
        return True
    if lead.timeline.exclude(event="quiz.captura_parcial").exists():
        return False
    if lead.quizzes.exclude(pk=tentativa.pk).exists():
        return False
    return not lead.oportunidades.exclude(pk=tentativa.oportunidade_id).exists()


def _encerrar_duplicada(oportunidade, slug, event_id):
    motivo = (f"Mesma pessoa e mesma oferta: corrigiu o contato ao concluir o quiz {slug} "
              "e segue no outro contato.")
    oportunidade.etapa = "desqualificada"
    oportunidade.desfecho_resultado = "desqualificada"
    oportunidade.desfecho_motivo = motivo
    oportunidade.desfecho_evidencia = str(event_id)
    oportunidade.desfecho_encerrada_em = timezone.now()
    oportunidade.save(update_fields=[
        "etapa", "desfecho_resultado", "desfecho_motivo", "desfecho_evidencia",
        "desfecho_encerrada_em", "atualizada_em",
    ])
    RegistroHistoricoOportunidade.objects.create(
        oportunidade=oportunidade, autor_id="sistema", tipo="encerramento",
        descricao=f"Encerrada como desqualificada: {motivo}", evidencia=str(event_id),
    )


def _juntar_contato_corrigido(tentativa, data: dict, event_id):
    """O completo chegou com outro e-mail que o da captura da mesma sessão.

    Se o contato da captura só existe por causa dela (ou só tinha telefone) e
    o e-mail novo ainda não é de ninguém, ele recebe o e-mail certo: continua
    um contato só. Senão a tentativa e a oferta aberta pela captura passam para
    o contato do e-mail novo, sem abrir outra oferta.
    """
    from .handlers import _upsert_lead

    pessoa = data["lead"]
    site_id = _site(data)
    email = pessoa["email"]
    slug = _slug(data)
    antigo = Lead.objects.select_for_update().get(pk=tentativa.lead_id)
    destino = Lead.objects.filter(site_id=site_id, email=email).first()
    if destino is None and _so_desta_captura(antigo, tentativa):
        anterior = antigo.email
        antigo.email = email
        campos = ["email", "updated_at"]
        if pessoa.get("name"):
            antigo.name = pessoa["name"]
            campos.append("name")
        if pessoa.get("phone"):
            antigo.phone = pessoa["phone"]
            campos.append("phone")
        antigo.save(update_fields=campos)
        TimelineEvent.objects.create(
            lead=antigo, event="lead.contato_corrigido", event_id=None,
            payload={"email_anterior": anterior, "email": email,
                     "origem": f"quiz:{slug}", "sessao": tentativa.sessao},
        )
        return antigo

    destino = _upsert_lead(
        site_id=site_id, email=email, name=pessoa.get("name", ""),
        phone=pessoa.get("phone", ""), source=f"quiz:{slug}", utm=data.get("utm"),
    )
    destino = Lead.objects.select_for_update().get(pk=destino.pk)
    if destino.pk == antigo.pk:
        return destino
    if not destino.quizzes.filter(quiz_slug=tentativa.quiz_slug, sessao=tentativa.sessao).exists():
        tentativa.lead = destino
        tentativa.save(update_fields=["lead", "atualizado_em"])
    TimelineEvent.objects.create(
        lead=antigo, event="quiz.continuou_em_outro_contato", event_id=None,
        payload={"lead_id": str(destino.pk), "quiz_slug": slug, "sessao": tentativa.sessao},
    )
    oportunidade = None
    if tentativa.oportunidade_id:
        oportunidade = (Oportunidade.objects.select_for_update()
                        .filter(pk=tentativa.oportunidade_id, lead=antigo,
                                desfecho_encerrada_em__isnull=True).first())
    if oportunidade is None:
        return destino
    if Oportunidade.objects.filter(
        lead=destino, fonte_tipo=oportunidade.fonte_tipo,
        fonte_referencia_id=oportunidade.fonte_referencia_id,
    ).exists():
        _encerrar_duplicada(oportunidade, slug, event_id)
        return destino
    oportunidade.lead = destino
    oportunidade.save(update_fields=["lead", "atualizada_em"])
    RegistroHistoricoOportunidade.objects.create(
        oportunidade=oportunidade, autor_id="sistema", tipo="nota",
        descricao=f"A pessoa corrigiu o contato ao concluir o quiz {slug}; "
                  "a oferta segue no contato corrigido.",
        evidencia=str(event_id),
    )
    return destino


def lead_do_quiz_completo(event_id, data: dict):
    """O contato do quiz completo: o da captura da mesma sessão, se houver."""
    from .handlers import _upsert_lead

    pessoa = data["lead"]
    tentativa = _tentativa_da_sessao(_site(data), _slug(data), _sessao(data), _captura_id(data))
    if (tentativa is not None and tentativa.situacao == "parcial"
            and tentativa.lead.email != pessoa["email"]):
        return _juntar_contato_corrigido(tentativa, data, event_id)
    return _upsert_lead(
        site_id=data["site_id"],
        email=pessoa["email"],
        name=pessoa.get("name", ""),
        phone=pessoa.get("phone", ""),
        source=f"quiz:{data['quiz_slug']}",
        utm=data.get("utm"),
    )


def _oferta_concluida(tentativa, lead, slug, resultado, event_id):
    """A oferta aberta pela captura passa a valer pelo quiz concluído."""
    oportunidade = (Oportunidade.objects.select_for_update()
                    .filter(pk=tentativa.oportunidade_id, lead=lead,
                            desfecho_encerrada_em__isnull=True).first())
    if oportunidade is None:
        return
    if oportunidade.passo_descricao == PASSO_DA_CAPTURA.format(slug=slug):
        descricao = f"Oferecer o produto indicado pelo quiz {slug}"
        if resultado:
            descricao += f" (resultado: {resultado})"
        oportunidade.passo_descricao = descricao
        oportunidade.passo_evidencia_esperada = "Conversa com a pessoa e link de compra enviado"
        oportunidade.save(update_fields=[
            "passo_descricao", "passo_evidencia_esperada", "atualizada_em",
        ])
    texto = f"Concluiu o quiz {slug}"
    if resultado:
        texto += f" (resultado: {resultado})"
    RegistroHistoricoOportunidade.objects.create(
        oportunidade=oportunidade, autor_id="sistema", tipo="nota",
        descricao=texto + ".", evidencia=str(event_id),
    )


def registrar_quiz_completo(lead, event_id, data: dict, momento=None) -> QuizDoLead:
    slug = _slug(data)
    sessao = _sessao(data)
    captura_id = _captura_id(data)
    utm = _utm(data)
    tentativa = _tentativa(lead, slug, sessao, completo=True, captura_id=captura_id)
    if tentativa is None:
        tentativa = QuizDoLead(lead=lead, quiz_slug=slug, sessao=sessao)
    estava_parcial = not tentativa._state.adding and tentativa.situacao == "parcial"
    respostas = respostas_legiveis(data.get("respostas"))
    if respostas or not tentativa.respostas:
        tentativa.respostas = respostas
    if sessao and not tentativa.sessao:
        tentativa.sessao = sessao
    tentativa.captura_id = captura_id or tentativa.captura_id
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
    if estava_parcial and tentativa.oportunidade_id:
        _oferta_concluida(tentativa, lead, slug, tentativa.resultado, event_id)
    return tentativa


def _lead_so_com_telefone(site_id, contato, slug, utm):
    """Quem deixou só o telefone: o contato conhecido com esse número, ou um novo.

    O número é comparado pelos dígitos (com e sem o 55). Mais de um contato
    com o mesmo número (família que divide o telefone) é ambíguo: a captura
    não entra na ficha de nenhum deles e ganha contato próprio.
    """
    conhecidos = list(_leads_do_telefone(site_id, contato["telefone"])
                      .order_by("created_at", "id")[:10])
    sem_email = [lead for lead in conhecidos if not lead.email]
    if sem_email:
        return sem_email[0]
    if len(conhecidos) == 1:
        return conhecidos[0]
    return Lead.objects.create(
        site_id=site_id, email="", name=contato["nome"], phone=contato["telefone"],
        source=f"quiz:{slug}", utm=utm,
    )


def _abrir_oferta_da_captura(lead, slug, event_id):
    """A oferta do quiz para quem deixou o contato sem concluir.

    Mesma oportunidade que o quiz completo usa depois (mesma referência), mas o
    histórico diz o que aconteceu: deixou o contato, ainda sem resultado.
    Devolve a oportunidade criada, ou None se a pessoa já tinha essa oferta.
    """
    from .oferta import FONTE, PREFIXO
    from .recuperacao import _responsavel

    referencia = f"{PREFIXO}{slug}"
    if Oportunidade.objects.filter(lead=lead, fonte_tipo=FONTE,
                                   fonte_referencia_id=referencia).exists():
        return None
    oportunidade = Oportunidade.objects.create(
        lead=lead, etapa="nova", titular_id=_responsavel(lead.site_id),
        fonte_tipo=FONTE, fonte_referencia_id=referencia,
        passo_descricao=PASSO_DA_CAPTURA.format(slug=slug),
        passo_executar_ate=timezone.now() + timedelta(days=1),
        passo_evidencia_esperada="Conversa com a pessoa: quiz concluído ou link de compra enviado",
    )
    RegistroHistoricoOportunidade.objects.create(
        oportunidade=oportunidade, autor_id="sistema", tipo="etapa_alterada",
        descricao=f"Deixou o contato no quiz {slug} sem concluir; oferta aberta.",
        evidencia=str(event_id),
    )
    return oportunidade


def ao_quiz_captura_parcial(event_id: str, data: dict) -> None:
    """A pessoa deixou contato e ainda não terminou o quiz.

    Cria ou atualiza o contato com origem no quiz e abre a oportunidade da
    oferta do quiz, a mesma que o quiz completo usa depois. Capturas seguintes
    da mesma sessão só atualizam as respostas; a que chega depois do quiz
    completo da mesma sessão é ignorada, seja qual for o contato que ela traz.
    """
    from .handlers import _upsert_lead

    site_id = _site(data)
    contato = _contato(data)
    if not site_id or not (contato["email"] or _variantes_do_telefone(contato["telefone"])):
        log.warning("captura parcial sem site ou contato; evento %s ignorado", event_id)
        return
    slug = _slug(data)
    sessao = _sessao(data)
    captura_id = _captura_id(data)
    utm = _utm(data)
    with transaction.atomic():
        tentativa = _tentativa_da_sessao(site_id, slug, sessao, captura_id)
        nova = tentativa is None
        if nova:
            if contato["email"]:
                lead = _upsert_lead(
                    site_id=site_id, email=contato["email"], name=contato["nome"],
                    phone=contato["telefone"], source=f"quiz:{slug}", utm=utm,
                )
            else:
                lead = _lead_so_com_telefone(site_id, contato, slug, utm)
            lead = Lead.objects.select_for_update().get(pk=lead.pk)
            tentativa = QuizDoLead(lead=lead, quiz_slug=slug, sessao=sessao)
        if tentativa.situacao == "completo":
            return
        respostas = respostas_legiveis(data.get("respostas"))
        if len(respostas) >= len(tentativa.respostas or []):
            tentativa.respostas = respostas
        tentativa.captura_id = captura_id or tentativa.captura_id
        tentativa.versao = _versao(data) or tentativa.versao
        tentativa.utm = utm or tentativa.utm
        tentativa.campanha = _campanha(data, utm) or tentativa.campanha
        tentativa.ultimo_event_id = event_id
        tentativa.save()
        if not nova:
            return
        TimelineEvent.objects.create(
            lead=lead, event="quiz.captura_parcial", event_id=event_id, payload=data
        )
        tentativa.oportunidade = _abrir_oferta_da_captura(lead, slug, event_id)
        if tentativa.oportunidade is not None:
            tentativa.save(update_fields=["oportunidade", "atualizado_em"])


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
