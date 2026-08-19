# [RECEITA:R10 v1]
import pytest

from apps.pedidos.models import Order, OutboxEvent
from tests.conftest import BUMP_A, HOST_A, OFERTA_A, SLUG


@pytest.mark.smoke_checkout
def test_healthz_responde_200(client):
    # Sonda de container/gateway: chega sem Host de site e não pode depender do
    # catálogo estar de pé — por isso o CONV-SITE não a intercepta.
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.django_db
@pytest.mark.smoke_checkout
def test_caminho_feliz_sessao_pedido_e_status(api, rede):
    sessao = api.post("/api/checkout/sessoes", {"offer_slug": SLUG})
    assert sessao.status_code == 201, sessao.content
    assert sessao.json()["offer"]["product_name"] == OFERTA_A["product"]["name"]
    assert sessao.json()["offer"]["bumps"][0]["id"] == BUMP_A["id"]

    pedido = api.post(
        f"/api/checkout/sessoes/{sessao.json()['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "bump_ids": [BUMP_A["id"]],
            "method": "pix",
        },
    )
    assert pedido.status_code == 201, pedido.content
    corpo = pedido.json()
    assert corpo["status"] == "aguardando_pagamento"
    assert corpo["payment"]["method"] == "pix"
    assert corpo["payment"]["intent_id"] == "intent-de-teste"
    assert corpo["payment"]["pix"]["qr_code"].startswith("00020126")

    status = api.get(f"/api/checkout/pedidos/{corpo['order_id']}")
    assert status.status_code == 200
    assert status.json()["status"] == "aguardando_pagamento"
    assert status.json()["total_cents"] == (
        OFERTA_A["price_cents"] + BUMP_A["price_cents"]
    )
    assert len(status.json()["items"]) == 2


@pytest.mark.django_db
def test_pedido_criado_vai_para_a_outbox_na_mesma_transacao(api, rede, sessao_a):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "method": "pix",
        },
    )
    assert resp.status_code == 201, resp.content

    eventos = OutboxEvent.objects.filter(event="pedido.criado")
    assert eventos.count() == 1  # [INV-P6]
    dados = eventos.get().payload
    pedido = Order.objects.get()
    assert dados["order_id"] == str(pedido.id)
    assert dados["site_id"] == pedido.site_id
    assert dados["total_cents"] == pedido.total_cents
    assert dados["customer"]["email"] == "cliente@exemplo.com"
    assert "cpf" not in dados["customer"]  # o evento não carrega documento


@pytest.mark.django_db
def test_card_nao_leva_bloco_pix_na_resposta(api, rede, sessao_a):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "method": "card",
        },
    )
    assert resp.status_code == 201, resp.content
    assert "pix" not in resp.json()["payment"]


@pytest.mark.django_db
def test_metodo_invalido_e_422(api, rede, sessao_a):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "method": "boleto",
        },
    )
    assert resp.status_code == 422
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_pedido_inexistente_e_404(api, rede):
    resp = api.get("/api/checkout/pedidos/06b7b0d6-0000-4000-8000-000000000000")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_superficie_sem_token_e_401(client, rede):
    resp = client.get(
        "/api/checkout/pedidos/06b7b0d6-0000-4000-8000-000000000000",
        HTTP_HOST=HOST_A,
    )
    assert resp.status_code == 401
