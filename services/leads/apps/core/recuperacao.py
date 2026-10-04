"""Sincroniza tentativas de pagamento com a oportunidade da mesma compra."""

import os

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import RegistroHistoricoOportunidade, ReversaoDePagamento, TimelineEvent


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


def _ganhar(oportunidade, evidencia, descricao="Compra recuperada: pagamento aprovado."):
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
        descricao=descricao, evidencia=evidencia,
    )
    return True


def _aplicar_reversao(reversao):
    """Estorno ou contestação confirmados zeram a receita líquida da compra.

    Sem aprovação ainda, a reversão fica guardada e é aplicada quando ela
    chegar (fora de ordem). A oportunidade afetada é a da compra e a
    recuperação do mesmo pedido, nunca as outras ofertas da pessoa.
    """
    from .compras import compra_do_evento, reverter_compra

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
    compra = compra_do_evento(aprovado.lead, {"order_id": reversao.order_id})
    if compra.aprovado_em is None:
        compra.aprovado_em = aprovado.occurred_at
        valor = (aprovado.payload or {}).get("amount_cents")
        compra.valor_aprovado_centavos = (
            int(valor) if isinstance(valor, int) else compra.valor_pedido_centavos
        )
        compra.aprovacao_evidencia = str(aprovado.event_id or aprovado.id)
        compra.save(update_fields=[
            "aprovado_em", "valor_aprovado_centavos", "aprovacao_evidencia",
            "atualizada_em",
        ])
    reverter_compra(
        compra, motivo=(reversao.payload or {}).get("motivo", ""),
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
def sincronizar_pagamento(lead, evento, data, event_id, evento_timeline=None, chave=""):
    """Leva o fato de pagamento à compra do pedido e à oportunidade dela.

    Aprovação fecha só a oportunidade da compra; recusa e Pix vencido abrem
    ou atualizam a recuperação da mesma compra. Ver `compras.py`.
    """
    from .compras import registrar_aprovacao, registrar_falha

    if not data.get("order_id"):
        return None
    if evento == "pagamento.aprovado":
        compra = registrar_aprovacao(lead, data, event_id, evento_timeline, chave)
        return compra.oportunidade if compra is not None else None
    if evento in EVENTOS_DE_FALHA:
        return registrar_falha(lead, evento, data, event_id, evento_timeline)
    return None
