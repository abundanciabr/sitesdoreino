# tests/test_intents_golden_path.py  # [RECEITA:R10 v1]
# Caminho feliz de cada método — cross-smoke (ci/cross-smoke.sh) roda smoke_card
# quando methods/pix é tocado, e vice-versa (INV-P9).
import json
from datetime import datetime
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
            "qr_code": "00020126giribatuba-copia-e-cola",
            "qr_code_base64": "aGVsbG8tcWlyLWNvZGU=",
        }
    },
}

_RESPOSTA_CARD_APROVADO_MP = {
    "id": 987654321,
    "status": "approved",
    "status_detail": "accredited",
}
_RESPOSTA_CARD_RECUSADO_MP = {
    "id": 987654322,
    "status": "rejected",
    "status_detail": "cc_rejected_insufficient_amount",
}


@pytest.fixture
def token_valido(settings: Any) -> str:
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def _payload_intent(**overrides: Any) -> dict[str, Any]:
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


def _post_intent(client: Client, token: str, chave: str, **overrides: Any) -> Any:
    return client.post(
        "/api/pagamentos/intents",
        data=json.dumps(_payload_intent(**overrides)),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_IDEMPOTENCY_KEY=chave,
    )


@pytest.mark.smoke_pix
@patch.object(MercadoPagoClient, "criar_pagamento_pix", return_value=_RESPOSTA_PIX_MP)
def test_caminho_feliz_pix_gera_qr_e_expiracao(
    mock_criar: Any, client: Client, token_valido: str
) -> None:
    resp = _post_intent(
        client, token_valido, "11111111-1111-1111-1111-111111111111", method="pix"
    )

    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["status"] == "pending"
    assert corpo["method"] == "pix"
    assert corpo["site_id"] == "site-opaco-abc123"  # ecoado, nunca interpretado
    assert corpo["pix"]["qr_code"] == "00020126giribatuba-copia-e-cola"
    assert corpo["pix"]["qr_code_base64"]
    assert corpo["pix"]["expires_at"]
    assert "card" not in corpo
    mock_criar.assert_called_once()
    _, kwargs = mock_criar.call_args
    assert kwargs["idempotency_key"] == "11111111-1111-1111-1111-111111111111"

    resp_get = client.get(
        f"/api/pagamentos/intents/{corpo['id']}",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp_get.status_code == 200
    corpo_get = resp_get.json()
    # expires_at: mesmo instante, mas o Postgres normaliza o offset para UTC ao
    # persistir (USE_TZ=True) — comparar como datetime, não como string crua.
    assert datetime.fromisoformat(
        corpo_get["pix"].pop("expires_at")
    ) == datetime.fromisoformat(corpo["pix"].pop("expires_at"))
    assert corpo_get == corpo


@pytest.mark.smoke_card
def test_caminho_feliz_card_cria_pendente_e_confirma_aprovado(
    client: Client, token_valido: str
) -> None:
    resp = _post_intent(
        client, token_valido, "22222222-2222-2222-2222-222222222222", method="card"
    )
    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["status"] == "created"  # aguardando card_token do Brick
    assert corpo["card"] == {"reason_code": ""}
    assert (
        Intent.objects.get(id=corpo["id"]).provider_payment_id == ""
    )  # [INV-P9] sem chamada ao MP ainda

    with patch.object(
        MercadoPagoClient,
        "criar_pagamento_card",
        return_value=_RESPOSTA_CARD_APROVADO_MP,
    ) as mock_confirmar:
        resp_confirm = client.post(
            f"/api/pagamentos/intents/{corpo['id']}/card",
            data=json.dumps(
                {
                    "card_token": "brick-token-abc",
                    "installments": 1,
                    "payer_email": "cliente@exemplo.com",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_valido}",
        )
    assert resp_confirm.status_code == 200
    corpo_confirmado = resp_confirm.json()
    assert corpo_confirmado["status"] == "approved"
    mock_confirmar.assert_called_once()
    _, kwargs = mock_confirmar.call_args
    assert (
        kwargs["idempotency_key"] != ""
    )  # [INV-P4] escrita própria ao MP, nunca vazia


@pytest.mark.smoke_card
def test_card_recusado_expõe_reason_code_e_confirmar_de_novo_e_409(
    client: Client, token_valido: str
) -> None:
    resp = _post_intent(
        client, token_valido, "33333333-3333-3333-3333-333333333333", method="card"
    )
    intent_id = resp.json()["id"]

    with patch.object(
        MercadoPagoClient,
        "criar_pagamento_card",
        return_value=_RESPOSTA_CARD_RECUSADO_MP,
    ):
        resp_confirm = client.post(
            f"/api/pagamentos/intents/{intent_id}/card",
            data=json.dumps(
                {
                    "card_token": "brick-token-xyz",
                    "installments": 1,
                    "payer_email": "cliente@exemplo.com",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_valido}",
        )
    assert resp_confirm.status_code == 200
    assert resp_confirm.json()["status"] == "rejected"
    assert (
        resp_confirm.json()["card"]["reason_code"] == "cc_rejected_insufficient_amount"
    )

    resp_segunda_tentativa = client.post(
        f"/api/pagamentos/intents/{intent_id}/card",
        data=json.dumps(
            {
                "card_token": "brick-token-outro",
                "installments": 1,
                "payer_email": "cliente@exemplo.com",
            }
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert (
        resp_segunda_tentativa.status_code == 409
    )  # já resolvida — nunca cobra de novo
