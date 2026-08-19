# tests/test_inv_p3_webhook_idempotente.py  # [RECEITA:R5 v1]
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

_MP_PAYMENT_ID = "123456789"
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


def _criar_intent_pix(client: Client, token: str) -> str:
    with patch.object(
        MercadoPagoClient, "criar_pagamento_pix", return_value=_RESPOSTA_PIX_MP
    ):
        resp = client.post(
            "/api/pagamentos/intents",
            data=json.dumps(
                {
                    "site_id": "site-opaco-abc123",
                    "order_id": "pedido-inv-p3",
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
    return str(resp.json()["id"])


def _postar_webhook_assinado(client: Client, *, status: str) -> Any:
    request_id = str(uuid.uuid4())
    headers = assinar(data_id=_MP_PAYMENT_ID, request_id=request_id)
    return client.post(
        f"/api/pagamentos/webhooks/mp/pix?data.id={_MP_PAYMENT_ID}",
        data=json.dumps({"data": {"id": _MP_PAYMENT_ID, "status": status}}),
        content_type="application/json",
        HTTP_X_SIGNATURE=headers["x-signature"],
        HTTP_X_REQUEST_ID=headers["x-request-id"],
    )


def test_webhook_reentregue_3x_gera_uma_transicao_e_um_evento(
    client: Client, token_valido: str
) -> None:
    """[INV-P3] O mesmo webhook (mesmo mp_payment_id + status alvo) entregue 3x
    produz UMA transição de estado e UMA linha na outbox — o Mercado Pago
    reentrega webhooks por design (retry, timeout); sem dedup cada reentrega
    duplicaria matrícula, e-mail e linha de ledger."""
    _criar_intent_pix(client, token_valido)

    respostas = [_postar_webhook_assinado(client, status="approved") for _ in range(3)]

    for resp in respostas:
        assert resp.status_code == 200

    assert (
        Intent.objects.filter(
            provider_payment_id=_MP_PAYMENT_ID, status="approved"
        ).count()
        == 1
    )
    assert (
        OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 1
    )  # [INV-P3] uma reentrega não gera evento duplicado
