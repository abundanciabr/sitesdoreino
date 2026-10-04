"""O que o atendimento do CRM precisa de pagamentos.

1. Os avisos do pagamento ecoam `oportunidade_ref` e `oferta_ref` que o
   checkout pôs no `metadata` (mesma técnica do `product_id`), junto do
   `order_id` que já levavam. Sem elas no `metadata`, o aviso sai igual.
2. `GET /parcelas?amount_cents=` cota as parcelas do cartão para um valor,
   antes de existir pedido, com a mesma conta de `getCardInstallments`.
"""
from typing import Any

import pytest
import respx
from django.core.cache import cache
from django.test import Client

from pagamentos.core import ledger
from pagamentos.core.models import Intent, OutboxEvent

pytestmark = pytest.mark.django_db

AUTH = "https://auth.sandboxappmax.com.br/oauth2/token"
API = "https://api.sandboxappmax.com.br/v1/payments/installments"


def _intent(metadata: dict[str, Any]) -> Intent:
    return Intent.objects.create(
        idempotency_key=f"crm-{len(metadata)}-{sorted(metadata)}",
        site_id="site-crm",
        order_id="pedido-crm",
        method="pix",
        status="pending",
        amount_cents=990,
        customer={"email": "a@b.com", "name": "A B"},
        metadata=metadata,
    )


def _dados() -> dict[str, Any]:
    return {
        "platform_site_id": "site-crm",
        "payment_id": "pag-1",
        "order_id": "pedido-crm",
        "amount_cents": 990,
        "method": "pix",
        "provider": "mercadopago",
        "provider_reference_id": "mp-1",
        "customer": {"email": "a@b.com", "name": "A B"},
    }


def test_aviso_do_pagamento_leva_as_referencias_do_pedido() -> None:
    intent = _intent({"oportunidade_ref": "op-1", "oferta_ref": "curso", "outra": "x"})
    assert ledger.registrar_fato(
        intent, novo_status="approved", evento="pagamento.aprovado",
        dados=_dados(), version=2,
    )
    payload = OutboxEvent.objects.get(event="pagamento.aprovado").payload
    assert payload["order_id"] == "pedido-crm"
    assert payload["oportunidade_ref"] == "op-1"
    assert payload["oferta_ref"] == "curso"
    assert "outra" not in payload


def test_sem_referencias_o_aviso_sai_como_antes() -> None:
    intent = _intent({"product_id": "p"})
    assert ledger.registrar_fato(
        intent, novo_status="rejected", evento="pagamento.recusado",
        dados={**_dados(), "reason_code": "x"}, version=2,
    )
    assert OutboxEvent.objects.get(event="pagamento.recusado").payload == {
        **_dados(), "reason_code": "x",
    }


def test_referencia_vazia_ou_que_nao_e_texto_nao_entra() -> None:
    intent = Intent(metadata={"oportunidade_ref": "", "oferta_ref": 7})
    assert ledger.com_referencias_do_pedido({"a": 1}, intent) == {"a": 1}


@pytest.fixture
def appmax(settings: Any) -> None:
    settings.TOKENS_ACEITOS = {"token-teste"}
    settings.APPMAX_AUTH_URL = AUTH
    settings.APPMAX_API_URL = "https://api.sandboxappmax.com.br"
    settings.APPMAX_MERCHANT_CLIENT_ID = "merchant-falso"
    settings.APPMAX_MERCHANT_CLIENT_SECRET = "secret-falso"
    cache.clear()


def test_cotacao_de_parcelas_por_valor_sem_pedido(client: Client, appmax: None) -> None:
    with respx.mock as rede:
        rede.post(AUTH).respond(
            200, json={"access_token": "falso", "token_type": "Bearer", "expires_in": 3600}
        )
        rede.post(API).respond(
            200,
            json={
                "data": {
                    "installments": {"1": {"total": 990}, "3": {"total": 1050}},
                    "settings": {"modality": "PP", "max_installments": 12},
                }
            },
        )
        resposta = client.get(
            "/api/pagamentos/parcelas?amount_cents=990",
            HTTP_AUTHORIZATION="Bearer token-teste",
        )
    assert resposta.status_code == 200, resposta.content
    assert resposta.json() == {
        "amount_cents": 990,
        "modality": "PP",
        "options": [
            {"installments": 1, "total_cents": 990, "installment_cents": 990},
            {"installments": 3, "total_cents": 1050, "installment_cents": 350},
        ],
    }


def test_cotacao_de_parcelas_exige_token_e_valor_positivo(
    client: Client, appmax: None
) -> None:
    assert client.get("/api/pagamentos/parcelas?amount_cents=990").status_code == 401
    assert (
        client.get(
            "/api/pagamentos/parcelas?amount_cents=0",
            HTTP_AUTHORIZATION="Bearer token-teste",
        ).status_code
        == 422
    )


def test_cotacao_fora_do_ar_e_502(client: Client, appmax: None) -> None:
    with respx.mock as rede:
        rede.post(AUTH).respond(
            200, json={"access_token": "falso", "token_type": "Bearer", "expires_in": 3600}
        )
        rede.post(API).respond(500)
        resposta = client.get(
            "/api/pagamentos/parcelas?amount_cents=990",
            HTTP_AUTHORIZATION="Bearer token-teste",
        )
    assert resposta.status_code == 502
