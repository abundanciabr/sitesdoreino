# [RECEITA:R10 v1]
import pytest


@pytest.mark.smoke_leads
def test_healthz_responde_200(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


@pytest.mark.parametrize(
    "path",
    [
        "/api/leads/leads",
        "/api/leads/leads/lead-1/tags",
    ],
)
def test_superficie_da_api_ainda_nao_implementada(client, token_valido, path):
    """Fase 0 — esqueleto: a superfície existe (espelha o contrato congelado),
    mas os handlers ainda respondem 501 (regra de negócio real é fora de escopo)."""
    resp = client.post(
        path,
        data="{}",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 501


def test_superficie_sem_token_e_401(client):
    resp = client.post("/api/leads/leads", data="{}", content_type="application/json")
    assert resp.status_code == 401
