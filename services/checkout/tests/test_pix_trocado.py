import json

import pytest

from apps.pedidos.management.commands.consume_eventos import aplicar
from apps.pedidos.models import FatoAplicado, Order
from conftest import HOST_A, PAGAMENTOS, SLUG

pytestmark = pytest.mark.django_db

COMPRADOR = {
    "email": "cliente@exemplo.com",
    "name": "Cliente Teste",
    "phone": "11999999999",
    "cpf": "40827365144",
}
PIX_NOVO = {
    "qr_code": "codigo-novo",
    "qr_code_base64": "bm92bw==",
    "expires_at": "2026-10-03T15:00:00+00:00",
}


def _pedido(api, sessao_a, method="pix"):
    resposta = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {"customer": COMPRADOR, "method": method},
    )
    assert resposta.status_code == 201, resposta.content
    return Order.objects.get(pk=resposta.json()["order_id"])


def _troca(pedido, *, site_id=None, payment_id=None):
    return {
        "event": "pix.codigo_trocado",
        "version": 1,
        "data": {
            "site_id": site_id or pedido.site_id,
            "payment_id": payment_id or pedido.intent_id,
            "order_id": str(pedido.id),
            "amount_cents": pedido.total_cents,
            "customer": {
                "name": pedido.customer["name"],
                "email": pedido.customer["email"],
                "phone": pedido.customer["phone"],
            },
            "pix": PIX_NOVO,
            "pagina_url": f"https://{HOST_A}/checkout/pedido/{pedido.id}/pix/",
        },
    }


def test_evento_troca_pix_uma_vez_e_reentrega_nao_muda_o_bloco(api, rede, sessao_a):
    pedido = _pedido(api, sessao_a)
    antigo = pedido.pix["qr_code"]
    evento = _troca(pedido)
    assert aplicar(evento) is True
    pedido.refresh_from_db()
    primeiro = pedido.pix.copy()
    assert primeiro["qr_code"] == PIX_NOVO["qr_code"] != antigo
    assert primeiro["trocado_em"]
    assert pedido.status == Order.AGUARDANDO
    evento["data"]["pix"] = {**PIX_NOVO, "qr_code": "reentrega-diferente"}
    assert aplicar(evento) is False
    pedido.refresh_from_db()
    assert pedido.pix == primeiro
    assert FatoAplicado.objects.count() == 1


@pytest.mark.parametrize("status", ["pago", "recusado", "expirado"])
def test_pedido_decidido_nao_troca(api, rede, sessao_a, status):
    pedido = _pedido(api, sessao_a)
    original = pedido.pix.copy()
    Order.objects.filter(pk=pedido.pk).update(status=status)
    assert aplicar(_troca(pedido)) is False
    pedido.refresh_from_db()
    assert pedido.pix == original
    assert FatoAplicado.objects.count() == 0


@pytest.mark.parametrize("invalido", ["card", "site"])
def test_cartao_ou_outro_site_nao_troca(api, rede, sessao_a, invalido):
    pedido = _pedido(api, sessao_a, method="card" if invalido == "card" else "pix")
    original = pedido.pix.copy()
    evento = _troca(pedido, site_id="outro-site" if invalido == "site" else None)
    assert aplicar(evento) is False
    pedido.refresh_from_db()
    assert pedido.pix == original
    assert FatoAplicado.objects.count() == 0


def test_payment_id_de_outra_intent_nao_troca(api, rede, sessao_a):
    pedido = _pedido(api, sessao_a)
    original = pedido.pix.copy()
    assert aplicar(_troca(pedido, payment_id="outra-intent")) is False
    pedido.refresh_from_db()
    assert pedido.pix == original
    assert FatoAplicado.objects.count() == 0


def test_consulta_e_pagina_aberta_depois_ja_mostram_codigo_novo(api, client, rede, sessao_a):
    pedido = _pedido(api, sessao_a)
    assert aplicar(_troca(pedido)) is True
    consulta = api.get(f"/api/checkout/pedidos/{pedido.id}")
    assert consulta.status_code == 200
    assert consulta.json()["pix"] == PIX_NOVO
    assert consulta.json()["pix_trocado"] is True
    assert "cpf" not in consulta.content.decode().lower()
    pagina = client.get(f"/pedido/{pedido.id}/pix/", HTTP_HOST=HOST_A)
    assert pagina.status_code == 200
    assert PIX_NOVO["qr_code"] in pagina.content.decode()
    assert "Não conseguimos concluir este pagamento. Pague com este novo código." in pagina.content.decode()
    assert '<script id="pix-trocado" type="application/json">true</script>' in pagina.content.decode()


def test_place_order_envia_pagina_url_https_do_site(api, rede, sessao_a):
    pedido = _pedido(api, sessao_a)
    requisicao = rede.post(f"{PAGAMENTOS}/intents").calls.last.request
    metadata = json.loads(requisicao.content)["metadata"]
    assert metadata["pagina_url"] == f"https://{HOST_A}/checkout/pedido/{pedido.id}/pix/"


def test_place_order_envia_link_da_oferta_para_o_email_de_pix_expirado(
    api, rede, sessao_a
):
    _pedido(api, sessao_a)
    requisicao = rede.post(f"{PAGAMENTOS}/intents").calls.last.request
    metadata = json.loads(requisicao.content)["metadata"]
    assert metadata["recovery_url"] == (
        f"https://{HOST_A}/checkout/{SLUG}/"
    )
