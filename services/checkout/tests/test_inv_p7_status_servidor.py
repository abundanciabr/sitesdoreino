# tests/test_inv_p7_status_servidor.py  [RECEITA:R5 v1]
# [INV-P7] Status na UI deriva do servidor: o consumer de eventos é quem move
# Order.status.
import pytest

from apps.pedidos.management.commands.consume_eventos import aplicar
from apps.pedidos.models import Order
from conftest import aprovado_v1, pix_expirado_v1, recusado_v1

pytestmark = pytest.mark.django_db


def _pedido(api, sessao_a, method="pix"):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "method": method,
        },
    )
    assert resp.status_code == 201, resp.content
    return resp.json()


def test_pagamento_aprovado_move_o_status_do_pedido(api, rede, sessao_a):
    pedido = _pedido(api, sessao_a)
    order = Order.objects.get(pk=pedido["order_id"])

    aplicar(aprovado_v1(order, mp_payment_id="mp-1"))

    status = api.get(f"/api/checkout/pedidos/{pedido['order_id']}")
    assert status.json()["status"] == "pago"


def test_evento_reentregue_nao_reabre_a_maquina_de_estado(api, rede, sessao_a):
    """Reentrega (at-least-once) e eventos fora de ordem não podem fazer um
    pedido já decidido 'voltar' para outro estado — a transição só sai de
    aguardando_pagamento, e só uma vez."""
    pedido = _pedido(api, sessao_a)
    order = Order.objects.get(pk=pedido["order_id"])
    aprovado = aprovado_v1(order, mp_payment_id="mp-1")

    aplicar(aprovado)
    aplicar(aprovado)  # reentrega do mesmo evento
    # Recusa de OUTRA tentativa do mesmo pedido, atrasada e fora de ordem: é um
    # fato diferente, então a dedup não a barra e quem a barra é o estado.
    aplicar(recusado_v1(order, payment_id="pag-de-outra-tentativa"))

    order.refresh_from_db()
    assert order.status == "pago"


def test_pix_expirado_move_o_status(api, rede, sessao_a):
    pedido = _pedido(api, sessao_a)
    order = Order.objects.get(pk=pedido["order_id"])

    aplicar(pix_expirado_v1(order, payment_id="pag-1"))

    order.refresh_from_db()
    assert order.status == "expirado"


def test_evento_de_outro_site_nao_move_o_pedido(api, rede, sessao_a):
    """[INV-P11] site_id do evento tem que bater com o do pedido."""
    pedido = _pedido(api, sessao_a)
    order = Order.objects.get(pk=pedido["order_id"])

    de_outro_site = aprovado_v1(order, mp_payment_id="mp-1")
    de_outro_site["data"]["site_id"] = "site-de-outro-lugar"
    aplicar(de_outro_site)

    order.refresh_from_db()
    assert order.status == "aguardando_pagamento"
