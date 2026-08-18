# pagamentos/methods/pix/service.py  # [RECEITA:R1 v1]
# [INV-P9] Não importa methods.card nem providers.* — só core (modelo Intent +
# core.gateway). Guardado em check-time por .importlinter.
from __future__ import annotations

from typing import Any

from django.db import transaction

from pagamentos.core import gateway
from pagamentos.core.models import Intent


def criar_intent_pix(
    *,
    idempotency_key: str,
    site_id: str,
    order_id: str,
    amount_cents: int,
    currency: str,
    customer: dict[str, Any],
    metadata: dict[str, Any],
) -> Intent:
    """[INV-P4] A linha nasce (com `idempotency_key` unique) ANTES da chamada ao
    provider — numa corrida, a 2ª tentativa recebe IntegrityError no `.create()`
    e NUNCA chega a chamar o Mercado Pago. `transaction.atomic()` isola essa
    tentativa num savepoint: se falhar, quem chamou (api/intents.py) ainda
    consegue consultar o banco normalmente para devolver a intent vencedora."""
    with transaction.atomic():
        intent = Intent.objects.create(
            idempotency_key=idempotency_key,
            site_id=site_id,
            order_id=order_id,
            method="pix",
            status="pending",
            amount_cents=amount_cents,
            currency=currency,
            customer=customer,
            metadata=metadata,
        )

    resultado = gateway.criar_pagamento_pix(
        idempotency_key=idempotency_key,
        amount_cents=amount_cents,
        order_id=order_id,
        payer_email=str(customer.get("email", "")),
    )
    intent.provider_payment_id = resultado.payment_id
    intent.pix_qr_code = resultado.qr_code
    intent.pix_qr_code_base64 = resultado.qr_code_base64
    intent.pix_expires_at = resultado.expires_at
    intent.save(
        update_fields=[
            "provider_payment_id",
            "pix_qr_code",
            "pix_qr_code_base64",
            "pix_expires_at",
            "updated_at",
        ]
    )
    return intent
