# tests/test_inv_p4_intent_idempotente.py  # [RECEITA:R5 v1]
# Nome do arquivo = código do invariante. Um arquivo por invariante.
import json
from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client

from pagamentos.core.models import Intent
from pagamentos.providers.mercadopago.client import MercadoPagoClient

pytestmark = pytest.mark.django_db

_RESPOSTA_PIX_MP = {
    "id": 123456789,
    "status": "pending",
    "date_of_expiration": "2026-08-19T00:00:00.000-03:00",
    "point_of_interaction": {
        "transaction_data": {
            "qr_code": "copia-e-cola-pix",
            "qr_code_base64": "aGVsbG8=",
        }
    },
}


@pytest.fixture
def token_valido(settings: Any) -> str:
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "site_id": "site-opaco-abc123",
        "order_id": "pedido-1",
        "amount_cents": 1990,
        "currency": "BRL",
        "method": "pix",
        "customer": {"email": "cliente@exemplo.com", "name": "Cliente Teste"},
    }
    base.update(overrides)
    return base


@pytest.mark.smoke_pix
@pytest.mark.smoke_card
@patch.object(MercadoPagoClient, "criar_pagamento_pix", return_value=_RESPOSTA_PIX_MP)
def test_mesma_chave_devolve_mesma_intent_uma_so_chamada_ao_provider(
    mock_criar: Any, client: Client, token_valido: str
) -> None:
    """[INV-P4] POST /intents com a mesma X-Idempotency-Key devolve a MESMA
    intent (200 na 2ª vez), sem nova tentativa de cobrança — refresh na página
    de pagamento, retry de rede e double-click são comportamento normal de
    usuário e nenhum deles pode virar dupla cobrança."""
    chave = "44444444-4444-4444-4444-444444444444"

    resp1 = client.post(
        "/api/pagamentos/intents",
        data=json.dumps(_payload()),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
        HTTP_X_IDEMPOTENCY_KEY=chave,
    )
    resp2 = client.post(
        "/api/pagamentos/intents",
        data=json.dumps(_payload()),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
        HTTP_X_IDEMPOTENCY_KEY=chave,
    )

    assert resp1.status_code == 201
    assert resp2.status_code == 200
    assert resp1.json()["id"] == resp2.json()["id"]
    assert Intent.objects.filter(idempotency_key=chave).count() == 1
    assert (
        mock_criar.call_count == 1
    )  # nenhuma segunda tentativa de cobrança ao provider
