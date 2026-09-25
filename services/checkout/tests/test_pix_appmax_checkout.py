"""O checkout entrega ao Pix Appmax só dados coletados e itens do catálogo."""

import json

import pytest

from tests.conftest import HOST_A, PAGAMENTOS, SITE_A, SLUG

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
    assert "telefone" in resposta.json()["detail"]
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
