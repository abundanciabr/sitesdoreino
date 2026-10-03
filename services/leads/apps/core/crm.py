"""Porta do painel admin para acompanhar recuperações e demais oportunidades."""

import os
import re
import uuid

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError

from .models import Oportunidade, RegistroHistoricoOportunidade, TimelineEvent
from .contatos import contatos_dos_quizzes
from .oportunidades import _como_oportunidade, _corpo, _escolha, _proximo_passo, _texto

router = Router()

_PALAVRA_DE_TESTE = r"(^|[^a-z0-9])(teste|test|sandbox)([^a-z0-9]|$)"
_PALAVRA_DE_TESTE_PY = re.compile(_PALAVRA_DE_TESTE, re.IGNORECASE)
_INDICADOR_DE_TESTE = (
    Q(lead__name__iregex=_PALAVRA_DE_TESTE)
    | Q(lead__source__icontains="sandbox")
    | Q(lead__email__iendswith="@example.com")
)


def _registro_de_teste(lead):
    return bool(
        _PALAVRA_DE_TESTE_PY.search(lead.name or "")
        or "sandbox" in (lead.source or "").lower()
        or (lead.email or "").lower().endswith("@example.com")
    )


def _admin(request):
    token = os.environ.get("TOKENS_ACEITOS_ADMIN", "")
    if not token or request.auth != token:
        raise HttpError(403, "Acesso exclusivo do painel admin")


def _item(oportunidade, historico=False):
    item = _como_oportunidade(oportunidade, com_historico=historico)
    lead = oportunidade.lead
    item["contato"] = {
        "id": str(lead.id), "nome": lead.name, "email": lead.email,
        "telefone": lead.phone, "site_id": lead.site_id,
    }
    item["registro_de_teste"] = _registro_de_teste(lead)
    return item


def _oportunidade(chave):
    try:
        identificador = uuid.UUID(str(chave))
    except (ValueError, TypeError, AttributeError):
        raise HttpError(404, "Oportunidade inexistente")
    item = Oportunidade.objects.select_related("lead").filter(
        pk=identificador, lead__in=contatos_dos_quizzes()
    ).first()
    if item is None:
        raise HttpError(404, "Oportunidade inexistente")
    return item


@router.get("/crm")
def listar_crm(request, q: str = "", lead_id: str = "", etapa: str = "",
               situacao: str = "", pagina: int = 1, por_pagina: int = 30,
               site_id: str = "", testes: str = "ocultar"):
    _admin(request)
    if pagina < 1 or por_pagina < 1 or por_pagina > 100:
        raise HttpError(422, "Paginação inválida")
    if testes not in {"ocultar", "mostrar", "somente"}:
        raise HttpError(422, "testes deve ser ocultar, mostrar ou somente")
    leads = contatos_dos_quizzes()
    base = Oportunidade.objects.select_related("lead").filter(lead__in=leads)
    eventos = TimelineEvent.objects.filter(lead__in=leads)
    if site_id:
        base = base.filter(lead__site_id=site_id)
        leads = leads.filter(site_id=site_id)
        eventos = eventos.filter(lead__site_id=site_id)
    quantidade_de_testes = base.filter(_INDICADOR_DE_TESTE).count()
    if testes == "ocultar":
        base = base.exclude(_INDICADOR_DE_TESTE)
    elif testes == "somente":
        base = base.filter(_INDICADOR_DE_TESTE)
    agora = timezone.now()
    resumo = {
        "contatos": leads.count(), "eventos": eventos.count(),
        "testes": quantidade_de_testes,
        "abertas": base.filter(desfecho_encerrada_em__isnull=True).count(),
        "atrasadas": base.filter(desfecho_encerrada_em__isnull=True,
                                passo_executar_ate__lt=agora).count(),
        "ganhas": base.filter(etapa="ganha").count(),
        "recuperadas": base.filter(etapa="ganha", fonte_tipo="pagamento",
                                    fonte_referencia_id__startswith="recuperar:").count(),
        "perdidas": base.filter(etapa="perdida").count(),
    }
    consulta = base
    if q:
        consulta = consulta.filter(Q(lead__name__icontains=q) |
                                   Q(lead__email__icontains=q) |
                                   Q(lead__phone__icontains=q) |
                                   Q(fonte_referencia_id__icontains=q))
    if lead_id:
        try:
            consulta = consulta.filter(lead_id=uuid.UUID(lead_id))
        except (ValueError, TypeError):
            raise HttpError(422, "lead_id inválido")
    if etapa:
        consulta = consulta.filter(etapa=etapa)
    if situacao == "aberta":
        consulta = consulta.filter(desfecho_encerrada_em__isnull=True)
    elif situacao == "encerrada":
        consulta = consulta.filter(desfecho_encerrada_em__isnull=False)
    elif situacao:
        raise HttpError(422, "situacao inválida")
    total = consulta.count()
    inicio = (pagina - 1) * por_pagina
    itens = consulta.order_by("-criada_em", "-id")[inicio:inicio + por_pagina]
    return JsonResponse({
        "itens": [_item(item) for item in itens], "resumo": resumo,
        "pagina": pagina, "total": total, "tem_mais": inicio + por_pagina < total,
    })


@router.get("/crm/{opportunity_id}")
def detalhe_crm(request, opportunity_id: str):
    _admin(request)
    return JsonResponse(_item(_oportunidade(opportunity_id), historico=True))


@router.patch("/crm/{opportunity_id}")
def atualizar_crm(request, opportunity_id: str):
    _admin(request)
    corpo = _corpo(request, {"autor_id", "etapa", "proximo_passo", "titular_id"}, set())
    if not ({"etapa", "proximo_passo", "titular_id"} & corpo.keys()):
        raise HttpError(422, "Informe etapa, proximo_passo ou titular_id")
    with transaction.atomic():
        item = Oportunidade.objects.select_for_update().select_related("lead").filter(
            pk=_oportunidade(opportunity_id).pk).get()
        if item.encerrada:
            raise HttpError(409, "Oportunidade encerrada")
        if "etapa" in corpo:
            item.etapa = _escolha(corpo, "etapa", Oportunidade.ETAPAS_ABERTAS)
        if "proximo_passo" in corpo:
            passo = _proximo_passo(corpo)
            item.passo_descricao = passo["descricao"]
            item.passo_executar_ate = passo["executar_ate"]
            item.passo_evidencia_esperada = passo["evidencia_esperada"]
        if "titular_id" in corpo:
            item.titular_id = _texto(corpo, "titular_id")
        item.save()
        RegistroHistoricoOportunidade.objects.create(
            oportunidade=item, autor_id=corpo.get("autor_id") or "admin", tipo="etapa_alterada",
            descricao=f"Acompanhamento atualizado; etapa {item.etapa}; responsável {item.titular_id}.",
        )
    return JsonResponse(_item(item, historico=True))


@router.post("/crm/{opportunity_id}/history")
def registrar_crm(request, opportunity_id: str):
    _admin(request)
    corpo = _corpo(request, {"autor_id", "descricao", "evidencia"}, {"descricao"})
    item = _oportunidade(opportunity_id)
    RegistroHistoricoOportunidade.objects.create(
        oportunidade=item, autor_id=corpo.get("autor_id") or "admin", tipo="nota",
        descricao=_texto(corpo, "descricao"), evidencia=corpo.get("evidencia", ""),
    )
    return JsonResponse(_item(item, historico=True))


@router.post("/crm/{opportunity_id}/close")
def encerrar_crm(request, opportunity_id: str):
    _admin(request)
    corpo = _corpo(request, {"autor_id", "resultado", "motivo", "evidencia"},
                   {"resultado", "motivo", "evidencia"})
    resultado = _escolha(corpo, "resultado", {"perdida", "desqualificada"})
    motivo = _texto(corpo, "motivo")
    evidencia = _texto(corpo, "evidencia")
    with transaction.atomic():
        item = Oportunidade.objects.select_for_update().select_related("lead").filter(
            pk=_oportunidade(opportunity_id).pk).get()
        if item.encerrada:
            raise HttpError(409, "Oportunidade encerrada")
        item.etapa = resultado
        item.desfecho_resultado = resultado
        item.desfecho_motivo = motivo
        item.desfecho_evidencia = evidencia
        item.desfecho_encerrada_em = timezone.now()
        item.save()
        RegistroHistoricoOportunidade.objects.create(
            oportunidade=item, autor_id=corpo.get("autor_id") or "admin", tipo="encerramento",
            descricao=f"Encerrada como {resultado}: {motivo}", evidencia=evidencia,
        )
    return JsonResponse(_item(item, historico=True))
