# pagamentos/methods/card/service.py  # [RECEITA:R1 v1]
# [INV-P9] Não importa methods.pix nem providers.* — só core (modelo Intent +
# core.gateway). Guardado em check-time por .importlinter.
from __future__ import annotations

from typing import Any

from django.db import transaction

from pagamentos.core import gateway
from pagamentos.core.models import Intent

_STATUS_CONFIRMAVEL = "created"

_MP_PARA_STATUS = {
    "approved": "approved",
    "rejected": "rejected",
}


class IntentNaoConfirmavel(Exception):
    """A intent não está em estado que aceite confirmação de cartão (409)."""


def criar_intent_card(
    *,
    idempotency_key: str,
    site_id: str,
    order_id: str,
    amount_cents: int,
    currency: str,
    customer: dict[str, Any],
    metadata: dict[str, Any],
) -> Intent:
    """Sem card_token ainda (só chega em confirmar_intent_card) — não fala com o
    provider aqui, só reserva a intent no estado 'created'. [INV-P4] `.create()`
    dentro de `transaction.atomic()` pelo mesmo motivo do Pix: numa corrida, a 2ª
    tentativa recebe IntegrityError isolada num savepoint."""
    with transaction.atomic():
        return Intent.objects.create(
            idempotency_key=idempotency_key,
            site_id=site_id,
            order_id=order_id,
            method="card",
            status=_STATUS_CONFIRMAVEL,
            amount_cents=amount_cents,
            currency=currency,
            customer=customer,
            metadata=metadata,
        )


def confirmar_intent_card(
    intent: Intent,
    *,
    card_token: str,
    installments: int,
    payer_email: str,
    payer_identification: dict[str, str] | None,
) -> Intent:
    if intent.status != _STATUS_CONFIRMAVEL:
        raise IntentNaoConfirmavel(intent.status)
    # [INV-P4] escrita própria ao MP: chave derivada da chave de criação da
    # intent (que já foi consumida pela criação) — nunca reaproveitada crua.
    resultado = gateway.criar_pagamento_card(
        idempotency_key=f"{intent.idempotency_key}:card-confirm",
        amount_cents=intent.amount_cents,
        order_id=intent.order_id,
        card_token=card_token,
        installments=installments,
        payer_email=payer_email,
        payer_identification=payer_identification,
    )
    intent.status = _MP_PARA_STATUS.get(resultado.status, "pending")
    intent.provider_payment_id = resultado.payment_id
    intent.card_reason_code = resultado.reason_code
    intent.save(
        update_fields=[
            "status",
            "provider_payment_id",
            "card_reason_code",
            "updated_at",
        ]
    )
    return intent
