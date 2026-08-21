# tests/test_inv_p4_intent_idempotente.py  # [RECEITA:R5 v1]
# Nome do arquivo = código do invariante. Um arquivo por invariante.
#
# O mock desceu de `patch.object(MercadoPagoClient, "criar_pagamento_pix", ...)`
# para o HTTP (respx). O invariante afirmado é o MESMO, mas passou a ser medido
# onde ele de fato acontece: "1 chamada ao provider" agora conta REQUESTS HTTP,
# não chamadas a um método substituído — e a segunda metade do INV-P4 ("toda
# escrita ao MP leva X-Idempotency-Key própria") deixou de ser invisível, porque
# só dá para afirmá-la olhando o request que saiu.
import json
from typing import Any

import httpx
import pytest
import respx
from django.test import Client

from pagamentos.core.models import Intent

pytestmark = pytest.mark.django_db

_URL_PAGAMENTOS = "https://api.mercadopago.com/v1/payments"

_RESPOSTA_PIX_MP: dict[str, Any] = {
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


def _post_intent(client: Client, token: str, chave: str) -> Any:
    return client.post(
        "/api/pagamentos/intents",
        data=json.dumps(_payload()),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_IDEMPOTENCY_KEY=chave,
    )


@pytest.mark.smoke_pix
@pytest.mark.smoke_card
def test_mesma_chave_devolve_mesma_intent_uma_so_chamada_ao_provider(
    client: Client, token_valido: str
) -> None:
    """[INV-P4] POST /intents com a mesma X-Idempotency-Key devolve a MESMA
    intent (200 na 2ª vez), sem nova tentativa de cobrança — refresh na página
    de pagamento, retry de rede e double-click são comportamento normal de
    usuário e nenhum deles pode virar dupla cobrança."""
    chave = "44444444-4444-4444-4444-444444444444"

    with respx.mock(assert_all_called=True) as mp:
        rota = mp.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(201, json=_RESPOSTA_PIX_MP)
        )
        resp1 = _post_intent(client, token_valido, chave)
        resp2 = _post_intent(client, token_valido, chave)

    assert resp1.status_code == 201
    assert resp2.status_code == 200
    assert resp1.json()["id"] == resp2.json()["id"]
    assert Intent.objects.filter(idempotency_key=chave).count() == 1
    # Nenhuma segunda tentativa de cobrança ao provider — contado no HTTP, não
    # num MagicMock: se o replay voltasse a falar com o MP, isto acusaria.
    assert rota.call_count == 1


@pytest.mark.smoke_pix
@pytest.mark.smoke_card
def test_escrita_ao_mp_leva_idempotency_key_propria(
    client: Client, token_valido: str
) -> None:
    """[INV-P4] A segunda metade do invariante — a que o mock de método escondia.
    Não basta a API ser idempotente para o checkout: a ESCRITA ao Mercado Pago
    precisa levar chave própria, senão a deduplicação do lado do MP não acontece
    e um retry de rede vira cobrança dupla lá fora, onde não há conserto."""
    chave = "55555555-4444-4444-4444-444444444444"

    with respx.mock(assert_all_called=True) as mp:
        rota = mp.post(_URL_PAGAMENTOS).mock(
            return_value=httpx.Response(201, json=_RESPOSTA_PIX_MP)
        )
        resp = _post_intent(client, token_valido, chave)

    assert resp.status_code == 201
    assert rota.calls.last.request.headers["X-Idempotency-Key"] == chave
