# tests/test_inv_p10_assinatura.py  # [RECEITA:R5 v1]
# Nome do arquivo = código do invariante. Um arquivo por invariante.
import json
import uuid
from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client

from pagamentos.core.models import Intent, OutboxEvent
from pagamentos.core.webhook_signature import assinar
from pagamentos.providers.mercadopago.client import MercadoPagoClient

pytestmark = pytest.mark.django_db

_MP_PAYMENT_ID = "555666777"
_RESPOSTA_PIX_MP = {
    "id": int(_MP_PAYMENT_ID),
    "status": "pending",
    "date_of_expiration": "2026-08-19T00:00:00.000-03:00",
    "point_of_interaction": {
        "transaction_data": {"qr_code": "copia-e-cola", "qr_code_base64": "aGVsbG8="}
    },
}


@pytest.fixture
def token_valido(settings: Any) -> str:
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def _criar_intent_pix(client: Client, token: str) -> Intent:
    with patch.object(
        MercadoPagoClient, "criar_pagamento_pix", return_value=_RESPOSTA_PIX_MP
    ):
        resp = client.post(
            "/api/pagamentos/intents",
            data=json.dumps(
                {
                    "site_id": "site-opaco-abc123",
                    "order_id": "pedido-inv-p10",
                    "amount_cents": 1990,
                    "currency": "BRL",
                    "method": "pix",
                    "customer": {
                        "email": "cliente@exemplo.com",
                        "name": "Cliente Teste",
                    },
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
    assert resp.status_code == 201
    return Intent.objects.get(id=resp.json()["id"])


def _corpo() -> str:
    return json.dumps({"data": {"id": _MP_PAYMENT_ID, "status": "approved"}})


def test_webhook_sem_assinatura_e_403_banco_intacto_outbox_vazia(
    client: Client, token_valido: str
) -> None:
    """[INV-P10] Sem x-signature ⇒ 403, ZERO efeito colateral."""
    intent = _criar_intent_pix(client, token_valido)

    resp = client.post(
        f"/api/pagamentos/webhooks/mp/pix?data.id={_MP_PAYMENT_ID}",
        data=_corpo(),
        content_type="application/json",
    )

    assert resp.status_code == 403
    intent.refresh_from_db()
    assert intent.status == "pending"  # estado anterior ao webhook, intocado
    assert OutboxEvent.objects.count() == 0


def test_webhook_com_assinatura_errada_e_403_banco_intacto_outbox_vazia(
    client: Client, token_valido: str
) -> None:
    """[INV-P10] v1 que não bate com o HMAC esperado ⇒ 403, ZERO efeito
    colateral — um webhook forjado que aprovasse pedidos seria matrícula
    grátis em escala."""
    intent = _criar_intent_pix(client, token_valido)

    resp = client.post(
        f"/api/pagamentos/webhooks/mp/pix?data.id={_MP_PAYMENT_ID}",
        data=_corpo(),
        content_type="application/json",
        HTTP_X_SIGNATURE="ts=1700000000,v1=0000000000000000000000000000000000000000000000000000000000000000",
        HTTP_X_REQUEST_ID=str(uuid.uuid4()),
    )

    assert resp.status_code == 403
    intent.refresh_from_db()
    assert intent.status == "pending"
    assert OutboxEvent.objects.count() == 0


def test_webhook_com_assinatura_valida_e_200(client: Client, token_valido: str) -> None:
    """Controle positivo: a MESMA construção de assinatura usada pelo endpoint
    de debug (`assinar`) é aceita pelo handler — prova que o 403 acima é sobre
    a assinatura estar errada, não sobre o endpoint estar quebrado."""
    _criar_intent_pix(client, token_valido)
    request_id = str(uuid.uuid4())
    headers = assinar(data_id=_MP_PAYMENT_ID, request_id=request_id)

    resp = client.post(
        f"/api/pagamentos/webhooks/mp/pix?data.id={_MP_PAYMENT_ID}",
        data=_corpo(),
        content_type="application/json",
        HTTP_X_SIGNATURE=headers["x-signature"],
        HTTP_X_REQUEST_ID=headers["x-request-id"],
    )

    assert resp.status_code == 200
