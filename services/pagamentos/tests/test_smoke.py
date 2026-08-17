# [RECEITA:R10 v1]
from typing import Any

import pytest
from django.test import Client


@pytest.mark.smoke_pix
@pytest.mark.smoke_card
def test_healthz_responde_200(client: Client) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.fixture
def token_valido(settings: Any) -> str:
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


@pytest.mark.smoke_pix
@pytest.mark.smoke_card
@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/pagamentos/intents"),
        ("get", "/api/pagamentos/intents/intent-1"),
        ("post", "/api/pagamentos/intents/intent-1/card"),
    ],
)
def test_superficie_de_intents_ainda_nao_implementada(
    client: Client, token_valido: str, method: str, path: str
) -> None:
    """Fase 0 — esqueleto: a superfície existe (espelha o contrato congelado),
    mas os handlers ainda respondem 501 (regra de negócio real é fora de escopo)."""
    extra: dict[str, str] = {
        "HTTP_AUTHORIZATION": f"Bearer {token_valido}",
        "HTTP_X_IDEMPOTENCY_KEY": "11111111-1111-1111-1111-111111111111",
    }
    if method == "post":
        extra["data"] = "{}"
        extra["content_type"] = "application/json"
    resp = getattr(client, method)(path, **extra)
    assert resp.status_code == 501


@pytest.mark.smoke_pix
@pytest.mark.smoke_card
def test_intents_sem_token_e_401(client: Client) -> None:
    resp = client.post(
        "/api/pagamentos/intents", data="{}", content_type="application/json"
    )
    assert resp.status_code == 401


@pytest.mark.smoke_pix
@pytest.mark.smoke_card
@pytest.mark.parametrize(
    "path",
    ["/api/pagamentos/webhooks/mp/pix", "/api/pagamentos/webhooks/mp/card"],
)
def test_webhooks_sao_publicos_e_ainda_nao_implementados(
    client: Client, path: str
) -> None:
    """Webhooks não exigem Bearer (autenticam por assinatura x-signature, INV-P10) —
    sem token, o handler é alcançado e responde 501, nunca 401."""
    resp = client.post(path, data="{}", content_type="application/json")
    assert resp.status_code == 501
