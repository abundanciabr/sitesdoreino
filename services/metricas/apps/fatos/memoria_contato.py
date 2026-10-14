"""Fatos com referência explícita ao contato, sem expandir por navegador."""
import os
import uuid

from django.db.models import Q
from django.http import JsonResponse
from ninja import Router
from ninja.errors import HttpError

from .models import Evento

router = Router()
TIPOS = ("funil.lead-capturado", "quiz.completado", "quiz.captura_parcial",
         "crm.oportunidade-atualizada", "mensagem.recebida")
ROTULOS = dict(zip(TIPOS, ("Contato capturado na página", "Quiz concluído",
                          "Contato parcial do quiz", "Oportunidade atualizada", "Mensagem recebida")))


def memoria(site_id, lead_id):
    consulta = Evento.objects.filter(site_id=site_id, tipo__in=TIPOS).filter(
        Q(dados__lead_id=lead_id) | Q(dados__lead=lead_id)
    ).order_by("-ocorrido_em", "-event_id")
    total = consulta.count()
    eventos, vinculos = [], []
    for e in consulta[:200]:
        fonte = "metricas:" + str(e.event_id)
        eventos.append(dict(tipo=e.tipo, descricao=ROTULOS[e.tipo], fonte=fonte,
                            event_id=str(e.event_id), registrado_em=e.recebido_em.isoformat(),
                            ocorrido_em=e.ocorrido_em.isoformat()))
        visitante = e.dados.get("visitor_id")
        if e.tipo == "funil.lead-capturado" and isinstance(visitante, str) and visitante:
            vinculos.append(dict(tipo="Visitante", valor=visitante[:200], fonte=fonte,
                                 registrado_em=e.ocorrido_em.isoformat(), escopo="",
                                 observacao="Captura relaciona visitante e contato neste evento; outras visitas não foram atribuídas."))
    return dict(lead_id=lead_id, site_id=site_id, eventos=eventos, vinculos=vinculos,
                total=total, exibidos=len(eventos))


@router.get("/contatos/{lead_id}/memoria", operation_id="getContactMemoryFacts")
def consultar(request, lead_id: str, site_id: str):
    token = os.environ.get("TOKENS_ACEITOS_ADMIN", "")
    if not token or request.auth != token:
        raise HttpError(403, "Consulta exclusiva do painel administrativo")
    try:
        lead_id = str(uuid.UUID(lead_id))
    except ValueError:
        raise HttpError(422, "Contato inválido")
    if not site_id.strip():
        raise HttpError(422, "Site obrigatório")
    r = JsonResponse(memoria(site_id, lead_id))
    r["Cache-Control"] = "private, no-store"
    return r
