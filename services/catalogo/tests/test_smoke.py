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


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/api/catalogo/sites/by-host/loja1.com.br",
        "/api/catalogo/sites/site-1/ofertas/curso-esqueleto",
        "/api/catalogo/produtos/produto-1",
    ],
)
def test_superficie_da_api_serve_do_banco(client, token_valido, path):
    """A superfície espelha o contrato congelado e os handlers servem do banco:
    sem dado cadastrado, a resposta é 404 (nunca 501/500)."""
    resp = client.get(path, HTTP_AUTHORIZATION=f"Bearer {token_valido}")
    assert resp.status_code == 404


def test_superficie_sem_token_e_401(client):
    resp = client.get("/api/catalogo/produtos/produto-1")
    assert resp.status_code == 401
