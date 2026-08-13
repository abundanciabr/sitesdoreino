# [RECEITA:R10 v1]
import pytest


@pytest.mark.smoke_catalogo
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
        "/api/catalogo/sites/by-host/loja1.com.br",
        "/api/catalogo/sites/site-1/ofertas/curso-esqueleto",
        "/api/catalogo/produtos/produto-1",
    ],
)
def test_superficie_da_api_ainda_nao_implementada(client, token_valido, path):
    """Fase 0 — esqueleto: a superfície existe (espelha o contrato congelado),
    mas os handlers ainda respondem 501 (regra de negócio real é fora de escopo)."""
    resp = client.get(path, HTTP_AUTHORIZATION=f"Bearer {token_valido}")
    assert resp.status_code == 501


def test_superficie_sem_token_e_401(client):
    resp = client.get("/api/catalogo/produtos/produto-1")
    assert resp.status_code == 401
