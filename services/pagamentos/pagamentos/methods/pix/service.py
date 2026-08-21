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

    return completar_intent_pix(intent)


def completar_intent_pix(intent: Intent) -> Intent:
    """Pede o Pix ao provedor e grava o resultado na linha que JÁ existe.

    Separada de `criar_intent_pix` porque é também o caminho de REPARO. Quando a
    chamada ao provedor falha, a linha continua no banco de propósito — ela é o
    registro de que uma cobrança PODE ter sido iniciada lá fora (um timeout não
    diz se chegou) e é o que impede a mesma chave de idempotência de ser
    reaproveitada para outro payload. Só que fica INCOMPLETA; o replay de INV-P4
    em `api/intents.py` chama esta função para terminar o serviço, em vez de
    reentregar o vazio.

    Repetir é seguro: o request ao MP leva a MESMA `X-Idempotency-Key` da intent,
    e o MP deduplica por ela — retentativa não vira segunda cobrança, que é
    exatamente o que INV-P4 protege.

    Levanta `gateway.FalhaNoProvedor` se o provedor não devolver um Pix pagável.
    O `save()` só acontece depois de um resultado válido: numa falha, a linha
    permanece como estava, nunca meio preenchida."""
    resultado = gateway.criar_pagamento_pix(
        idempotency_key=intent.idempotency_key,
        amount_cents=intent.amount_cents,
        order_id=intent.order_id,
        payer_email=str(intent.customer.get("email", "")),
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


def intent_pix_incompleta(intent: Intent) -> bool:
    """Sem `provider_payment_id` a cobrança é órfã (nenhum webhook a alcança);
    sem `pix_qr_code` o cliente não tem como pagar. Nos dois casos a intent NÃO
    pode ser apresentada como criada — nem no 201, nem no 200 do replay, nem no
    GET de status. É a definição única de "incompleta" da célula: quem precisa
    decidir isso pergunta aqui, em vez de reescrever a regra."""
    return not intent.provider_payment_id or not intent.pix_qr_code
