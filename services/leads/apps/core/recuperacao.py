"""Sincroniza tentativas de pagamento com a oportunidade da mesma compra."""

import os
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import (
    Oportunidade, RegistroHistoricoOportunidade, ReversaoDePagamento, TimelineEvent,
)


EVENTOS_DE_FALHA = {"pagamento.recusado", "pix.expirado"}
FONTE = "pagamento"
PREFIXO = "recuperar:"


def _referencia(data):
    pedido = data.get("order_id")
    return f"{PREFIXO}{pedido}" if pedido else None


def _responsavel(site_id):
    configurado = os.environ.get("CRM_RECUPERACAO_TITULAR_ID", "").strip()
    if configurado:
        return configurado
    contas = getattr(settings, "COMERCIAIS_DO_CRM", {})
    titulares = sorted({
        conta["titular_id"] for conta in contas.values()
        if conta.get("site_id") == site_id and conta.get("titular_id")
    })
    return titulares[0] if titulares else "recuperacao"


def _aprovado_no_site(site_id, pedido):
    return TimelineEvent.objects.filter(
        lead__site_id=site_id,
        event="pagamento.aprovado",
        payload__order_id=pedido,
    ).order_by("occurred_at", "id").first()


def _ganhar(oportunidade, evidencia):
    if oportunidade.etapa == "ganha" and oportunidade.encerrada:
        return False
    oportunidade.etapa = "ganha"
    oportunidade.desfecho_resultado = "ganha"
    oportunidade.desfecho_motivo = "Pagamento aprovado"
    oportunidade.desfecho_evidencia = evidencia
    oportunidade.desfecho_encerrada_em = timezone.now()
    oportunidade.save(update_fields=[
        "etapa", "desfecho_resultado", "desfecho_motivo",
        "desfecho_evidencia", "desfecho_encerrada_em", "atualizada_em",
    ])
    RegistroHistoricoOportunidade.objects.create(
        oportunidade=oportunidade, autor_id="sistema", tipo="encerramento",
        descricao="Compra recuperada: pagamento aprovado.", evidencia=evidencia,
    )
    return True


def _aplicar_reversao(reversao, oportunidade=None):
    aprovado = _aprovado_no_site(reversao.site_id, reversao.order_id)
    if aprovado is None:
        return
    if not reversao.registrada_na_timeline:
        existente = TimelineEvent.objects.filter(
            lead__site_id=reversao.site_id,
            event="pagamento.reversao_confirmada",
            payload__order_id=reversao.order_id,
        ).first()
        if existente is None:
            TimelineEvent.objects.create(
                lead=aprovado.lead, event="pagamento.reversao_confirmada",
                event_id=reversao.event_id, payload=reversao.payload,
            )
        reversao.registrada_na_timeline = True
        reversao.save(update_fields=["registrada_na_timeline"])
    if oportunidade is None:
        oportunidade = Oportunidade.objects.select_for_update().filter(
            lead__site_id=reversao.site_id, fonte_tipo=FONTE,
            fonte_referencia_id=f"{PREFIXO}{reversao.order_id}",
        ).first()
    if oportunidade is None or (
        oportunidade.etapa == "desqualificada" and oportunidade.encerrada
        and oportunidade.desfecho_motivo == "Pagamento revertido"
    ):
        return
    oportunidade.etapa = "desqualificada"
    oportunidade.desfecho_resultado = "desqualificada"
    oportunidade.desfecho_motivo = "Pagamento revertido"
    oportunidade.desfecho_evidencia = str(reversao.event_id)
    oportunidade.desfecho_encerrada_em = timezone.now()
    oportunidade.save(update_fields=[
        "etapa", "desfecho_resultado", "desfecho_motivo",
        "desfecho_evidencia", "desfecho_encerrada_em", "atualizada_em",
    ])
    RegistroHistoricoOportunidade.objects.create(
        oportunidade=oportunidade, autor_id="sistema", tipo="encerramento",
        descricao="Pagamento revertido; compra retirada das recuperadas.",
        evidencia=str(reversao.event_id),
    )


@transaction.atomic
def sincronizar_reversao(event_id, data):
    site_id = data.get("platform_site_id", data.get("site_id"))
    order_id = data.get("order_id")
    if not site_id or not order_id:
        raise ValueError("Reversão sem site_id ou order_id")
    reversao, _ = ReversaoDePagamento.objects.get_or_create(
        site_id=site_id, order_id=order_id,
        defaults={"event_id": event_id, "payload": data},
    )
    _aplicar_reversao(reversao)
    return reversao


@transaction.atomic
def sincronizar_pagamento(lead, evento, data, event_id, evento_timeline=None):
    """Uma compra gera uma oportunidade; pagamento confirmado sempre vence falha.

    Chamado após gravar a timeline e também pelo backfill. A transação do
    consumer engloba ambas as gravações. O bloqueio do lead serializa eventos
    concorrentes da mesma pessoa, e a unicidade da fonte protege reentregas.
    """
    referencia = _referencia(data)
    if not referencia or evento not in EVENTOS_DE_FALHA | {"pagamento.aprovado"}:
        return None
    type(lead).objects.select_for_update().get(pk=lead.pk)
    consulta = Oportunidade.objects.select_for_update().filter(
        lead__site_id=lead.site_id, fonte_tipo=FONTE,
        fonte_referencia_id=referencia,
    )
    oportunidade = consulta.first()
    aprovado = _aprovado_no_site(lead.site_id, data["order_id"])
    if (
        oportunidade is None and evento in EVENTOS_DE_FALHA and aprovado
        and evento_timeline is not None
        and aprovado.occurred_at <= evento_timeline.occurred_at
    ):
        return None
    if oportunidade is None and evento in EVENTOS_DE_FALHA:
        descricao = (
            "Recuperar pagamento recusado" if evento == "pagamento.recusado"
            else "Recuperar Pix vencido"
        )
        oportunidade = Oportunidade.objects.create(
            lead=lead, etapa="nova", titular_id=_responsavel(lead.site_id),
            fonte_tipo=FONTE, fonte_referencia_id=referencia,
            passo_descricao=descricao,
            passo_executar_ate=timezone.now() + timedelta(days=1),
            passo_evidencia_esperada="Contato com o cliente e nova tentativa de pagamento",
        )
        RegistroHistoricoOportunidade.objects.create(
            oportunidade=oportunidade, autor_id="sistema", tipo="etapa_alterada",
            descricao=f"{descricao}; pedido {data['order_id']}.",
            evidencia=str(event_id),
        )
    reversao = ReversaoDePagamento.objects.filter(
        site_id=lead.site_id, order_id=data["order_id"]
    ).first()
    if oportunidade is not None and aprovado and reversao is None:
        _ganhar(oportunidade, str(aprovado.event_id or aprovado.id))
    if reversao is not None:
        _aplicar_reversao(reversao, oportunidade)
    return oportunidade
