# [RECEITA:R10 v1]
import pytest


@pytest.mark.smoke_checkout
def test_healthz_responde_200(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def test_criar_sessao_ainda_nao_implementado(client, token_valido):
    resp = client.post(
        "/api/checkout/sessoes",
        data="{}",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 501


def test_fechar_pedido_ainda_nao_implementado(client, token_valido):
    resp = client.post(
        "/api/checkout/sessoes/sessao-1/pedido",
        data="{}",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 501


def test_obter_pedido_ainda_nao_implementado(client, token_valido):
    resp = client.get(
        "/api/checkout/pedidos/pedido-1",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 501


def test_superficie_sem_token_e_401(client):
    resp = client.get("/api/checkout/pedidos/pedido-1")
    assert resp.status_code == 401
