import json
from typing import Any
from django.test import Client

import pytest
import respx
from django.core.cache import cache

from pagamentos.core.models import Intent

pytestmark = pytest.mark.django_db
AUTH = "https://auth.sandboxappmax.com.br/oauth2/token"
API = "https://api.sandboxappmax.com.br/v1/payments/installments"


@pytest.fixture
def pedido(settings: Any) -> Intent:
    settings.TOKENS_ACEITOS = {"token-teste"}
    settings.APPMAX_AUTH_URL = AUTH
    settings.APPMAX_API_URL = "https://api.sandboxappmax.com.br"
    settings.APPMAX_MERCHANT_CLIENT_ID = "merchant-falso"
    settings.APPMAX_MERCHANT_CLIENT_SECRET = "secret-falso"
    cache.clear()
    return Intent.objects.create(
        idempotency_key="parcelas-api",
        site_id="site-teste",
        order_id="pedido-teste",
        method="card",
        amount_cents=20000,
        customer={},
        metadata={},
    )


def consultar(client: Client, pedido: Intent) -> Any:
    return client.get(
        f"/api/pagamentos/intents/{pedido.id}/installments?amount_cents=1",
        HTTP_AUTHORIZATION="Bearer token-teste",
    )


def test_parcelas_ignoram_valor_do_navegador_e_usam_total_gravado(
    client: Client, pedido: Intent
) -> None:
    with respx.mock as rede:
        rede.post(AUTH).respond(
            200,
            json={"access_token": "falso", "token_type": "Bearer", "expires_in": 3600},
        )
        rota = rede.post(API).respond(
            200,
            json={
                "data": {
                    "installments": {"1": {"total": 20000}, "3": {"total": 20812}},
                    "settings": {"modality": "PP", "max_installments": 12},
                }
            },
        )
        resposta = consultar(client, pedido)
    assert resposta.status_code == 200, resposta.content
    assert resposta.json() == {
        "amount_cents": 20000,
        "modality": "PP",
        "options": [
            {"installments": 1, "total_cents": 20000, "installment_cents": 20000},
            {"installments": 3, "total_cents": 20812, "installment_cents": 6937},
        ],
    }
    assert json.loads(rota.calls[0].request.content) == {
        "installments": 12,
        "total_value": 20000,
        "settings": True,
    }
    assert "falso" not in resposta.content.decode()


@pytest.mark.parametrize(
    "corpo",
    [
        {},
        {
            "data": {
                "installments": {},
                "settings": {"modality": "PP", "max_installments": 12},
            }
        },
    ],
)
def test_parcelas_incompletas_retornam_erro_com_orientacao(
    client: Client, pedido: Intent, corpo: dict[str, Any]
) -> None:
    with respx.mock as rede:
        rede.post(AUTH).respond(
            200,
            json={"access_token": "falso", "token_type": "Bearer", "expires_in": 3600},
        )
        rede.post(API).respond(200, json=corpo)
        resposta = consultar(client, pedido)
    assert resposta.status_code == 502
    assert resposta.json() == {
        "detail": "não foi possível consultar as parcelas; tente novamente"
    }


def test_parcelas_exigem_autenticacao_e_intent_de_cartao(
    client: Client, pedido: Intent
) -> None:
    assert (
        client.get(f"/api/pagamentos/intents/{pedido.id}/installments").status_code
        == 401
    )
    pedido.method = "pix"
    pedido.save(update_fields=["method"])
    assert consultar(client, pedido).status_code == 409
    assert (
        client.get(
            "/api/pagamentos/intents/invalido/installments",
            HTTP_AUTHORIZATION="Bearer token-teste",
        ).status_code
        == 404
    )
