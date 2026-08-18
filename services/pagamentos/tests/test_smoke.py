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
def test_get_intent_inexistente_e_404(client: Client, token_valido: str) -> None:
    """Fase 3a: create/get/confirm são reais agora (ver test_intents_golden_path.py
    e test_inv_p4_intent_idempotente.py); esta smoke cobre só a superfície de erro
    que não muda com o método."""
    resp = client.get(
        "/api/pagamentos/intents/intent-inexistente",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 404


@pytest.mark.smoke_pix
@pytest.mark.smoke_card
@pytest.mark.django_db  # create_intent consulta idempotency_key (INV-P4) antes de validar o corpo
def test_create_intent_payload_vazio_e_422(client: Client, token_valido: str) -> None:
    resp = client.post(
        "/api/pagamentos/intents",
        data="{}",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
        HTTP_X_IDEMPOTENCY_KEY="11111111-1111-1111-1111-111111111111",
    )
    assert resp.status_code == 422


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
