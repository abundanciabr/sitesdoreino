"""O checkout entrega ao Pix Appmax só dados coletados e itens do catálogo."""

import json
import uuid

import httpx
import pytest

from apps.core.api import _chave_da_compra
from apps.pedidos.models import Order
from tests.conftest import HOST_A, PAGAMENTOS, SITE_A, SLUG, _responder_intent

pytestmark = pytest.mark.django_db


def test_pix_appmax_recusa_telefone_ou_cpf_ausente_antes_de_cobrar(
    api, rede, sessao_a, settings
):
    settings.APPMAX_PIX_ENABLED_SITES = frozenset({SITE_A["id"]})
    resposta = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"name": "Cliente Teste", "email": "cliente@teste.com"},
            "method": "pix",
        },
    )
    assert resposta.status_code == 422
    assert "phone" in resposta.json()["detail"]
    assert not any(
        str(chamada.request.url) == f"{PAGAMENTOS}/intents" for chamada in rede.calls
    )


def test_pix_appmax_envia_documento_ip_e_itens_do_catalogo(
    api, rede, sessao_a, settings
):
    settings.APPMAX_PIX_ENABLED_SITES = frozenset({SITE_A["id"]})
    resposta = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {
                "name": "Cliente Teste",
                "email": "cliente@teste.com",
                "phone": "(11) 99999-9999",
                "cpf": "123.456.789-09",
            },
            "method": "pix",
            "items": [{"product_id": "forjado", "price_cents": 1}],
        },
    )
    assert resposta.status_code == 201, resposta.content
    chamada = next(
        chamada
        for chamada in rede.calls
        if str(chamada.request.url) == f"{PAGAMENTOS}/intents"
    )
    cobranca = json.loads(chamada.request.content)
    assert chamada.request.extensions["timeout"]["read"] == 45.0
    assert cobranca["customer"]["document_number"] == "12345678909"
    assert cobranca["customer"]["ip"] == "127.0.0.1"
    assert cobranca["metadata"]["items"]
    assert cobranca["metadata"]["items"][0]["product_id"] != "forjado"


def test_502_do_pix_orienta_nova_tentativa_e_repete_a_mesma_chave(
    api, rede, sessao_a, settings
):
    """Achado da TAR-711: a compra Pix sandbox recebeu 500 sem QR. O 502 de
    pagamentos vira frase para o comprador, nenhum pedido nasce, e a nova
    tentativa leva a mesma chave de idempotência, sem cobrança duplicada."""
    # guarda: services/checkout/apps/core/api.py:426
    settings.APPMAX_PIX_ENABLED_SITES = frozenset({SITE_A["id"]})
    respostas = [httpx.Response(502, json={"detail": "segredo-interno do provedor"})]
    rota = rede.post(f"{PAGAMENTOS}/intents").mock(
        side_effect=lambda pedido: (
            respostas.pop() if respostas else _responder_intent(pedido)
        )
    )
    corpo = {
        "customer": {
            "name": "Cliente Teste",
            "email": "cliente@teste.com",
            "phone": "(11) 99999-9999",
            "cpf": "123.456.789-09",
        },
        "method": "pix",
    }

    falha = api.post(f"/api/checkout/sessoes/{sessao_a['id']}/pedido", corpo)

    assert falha.status_code == 502, falha.content
    assert falha.json() == {
        "detail": "não foi possível iniciar o pagamento; tente novamente"
    }
    assert "segredo-interno" not in falha.content.decode()
    assert not Order.objects.filter(session_id=sessao_a["id"]).exists()

    nova = api.post(f"/api/checkout/sessoes/{sessao_a['id']}/pedido", corpo)

    assert nova.status_code == 201, nova.content
    assert nova.json()["payment"]["pix"]["qr_code"]
    chaves = {chamada.request.headers["X-Idempotency-Key"] for chamada in rota.calls}
    pedido = Order.objects.get(session_id=sessao_a["id"])
    # a mesma compra (desta sessão, destes itens, deste comprador) repete a mesma chave
    assert chaves == {
        _chave_da_compra(uuid.UUID(sessao_a["id"]), "pix", pedido.items, pedido.customer)
    }


def test_site_habilitado_mostra_opcao_de_cartao_e_exige_dados_do_pix(
    client, rede, settings
):
    settings.APPMAX_PIX_ENABLED_SITES = frozenset({SITE_A["id"]})
    settings.APPMAX_CARD_ENABLED_SITES = frozenset({SITE_A["id"]})
    resposta = client.get(f"/{SLUG}/", HTTP_HOST=HOST_A)
    assert resposta.status_code == 200
    html = resposta.content.decode("utf-8")
    assert (
        '<script id="appmax-pix-enabled" type="application/json">true</script>' in html
    )
    assert (
        '<script id="appmax-card-enabled" type="application/json">true</script>' in html
    )
    assert "@click=\"method = 'card'\"" in html
