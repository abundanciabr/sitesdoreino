"""Estorno da cobrança identificada por uma tentativa, sem reenviar pedidos incertos."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from pagamentos.core import gateway
from pagamentos.core.models import Intent, PaymentAttempt, PaymentOperation
from pagamentos.core.tentativas import hash_da_tentativa

logger = logging.getLogger(__name__)


def estornar(tentativa: PaymentAttempt, motivo: str) -> PaymentAttempt:
    """Persiste a solicitação antes do POST e devolve o estado local atualizado.

    Uma falha de qualquer natureza depois do commit é incerta para o nosso
    processo: ela só pode ser resolvida por consulta. Nem um 4xx autoriza um
    segundo POST, pois a Appmax não fornece chave de idempotência no estorno.
    """
    with transaction.atomic(durable=True):
        intent = Intent.objects.select_for_update().get(pk=tentativa.intent_id)
        travada = PaymentAttempt.objects.select_for_update().get(pk=tentativa.pk)
        if travada.estorno_estado in {"solicitado", "ambiguo", "confirmado"}:
            return travada
        if travada.estorno_estado:
            raise ValueError("estado de estorno desconhecido; confira a tentativa")
        if travada.state not in {"approved", "approved_duplicate"}:
            raise ValueError("somente uma cobrança aprovada pode ser estornada")
        if travada.state == "approved" and intent.status != "approved":
            raise ValueError("a intent da cobrança aprovada não está aprovada")
        if travada.platform_site_id != intent.site_id:
            raise ValueError("site da tentativa não confere com a intent")
        referencia = travada.provider_reference_id
        if not referencia or travada.provider not in {"appmax", "mercadopago"}:
            raise ValueError("tentativa sem provedor ou referência para estorno")
        if travada.provider == "appmax":
            if (not referencia.isdecimal() or int(referencia) <= 0 or
                    travada.external_order_id != referencia):
                raise ValueError("pedido Appmax da tentativa não confere")
        if PaymentOperation.objects.filter(attempt=travada, operation_type="refund").exists():
            raise ValueError("operação de estorno existente sem estado na tentativa")
        operacao = PaymentOperation.objects.create(
            attempt=travada,
            platform_site_id=travada.platform_site_id,
            operation_type="refund",
            request_hash=hash_da_tentativa({
                "provider_reference_id": referencia,
                "motivo": motivo,
                "operation": "refund_total",
            }, provider=travada.provider),
        )
        travada.estorno_estado = "solicitado"
        travada.estorno_solicitado_em = timezone.now()
        travada.save(update_fields=["estorno_estado", "estorno_solicitado_em", "updated_at"])

    # O bloco durable já commitou. Nenhuma chamada externa pode ser colocada
    # dentro dele, nem por um chamador com atomic aberto.
    try:
        if travada.provider == "appmax":
            sessao = gateway.nova_sessao_appmax()
            sessao.preparar()
            sessao.solicitar_estorno(order_id=int(referencia), tipo="total")
        else:
            gateway.estornar_pagamento(
                payment_id=referencia,
                idempotency_key=f"estorno:{travada.operation_id}",
            )
    except Exception as exc:
        logger.error(
            "estorno_ambiguo tentativa=%s provider=%s erro=%s",
            travada.pk, travada.provider, type(exc).__name__,
        )
        with transaction.atomic():
            atual = PaymentAttempt.objects.select_for_update().get(pk=travada.pk)
            if atual.estorno_estado == "solicitado":
                atual.estorno_estado = "ambiguo"
                atual.save(update_fields=["estorno_estado", "updated_at"])
            PaymentOperation.objects.filter(pk=operacao.pk, state="sending").update(
                state="reconciliation_required", updated_at=timezone.now()
            )
            return atual
    with transaction.atomic():
        PaymentOperation.objects.filter(pk=operacao.pk, state="sending").update(
            state="completed", updated_at=timezone.now()
        )
    return PaymentAttempt.objects.get(pk=travada.pk)
