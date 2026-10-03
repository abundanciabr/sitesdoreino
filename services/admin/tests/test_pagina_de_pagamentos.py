from unittest.mock import patch

from django.test import RequestFactory

from apps.core.pagamentos import pagamentos, pagamentos_devolver


def _pedido(method, path="/pagamentos/"):
    pedido = getattr(RequestFactory(), method)(path, HTTP_HOST="meshcraft.top")
    pedido.admin = {"email": "admin@example.test"}
    return pedido


def test_pagina_mostra_empresa_valor_e_confirmacao():
    compra = {
        "pedido": "pedido-1", "valor_centavos": 990, "empresa": "mercadopago",
        "estado": "approved", "metodo": "card", "data": "2026-10-03",
        "segunda_empresa": True, "estorno": "", "pode_devolver": True,
        "tentativa_id": "123", "presa": False,
    }
    with patch("apps.core.pagamentos.site_de", return_value="site-um"), patch(
        "apps.core.pagamentos.PagamentosClient.compras", return_value=[compra]
    ):
        resposta = pagamentos(_pedido("get"))
    assert resposta.status_code == 200
    assert b"R$ 9,90" in resposta.content
    assert b"mercadopago" in resposta.content
    assert b"Devolver" in resposta.content


def test_post_usa_site_do_host_e_id_da_tentativa():
    tentativa = "123"
    pedido = RequestFactory().post(
        "/pagamentos/devolver", {"tentativa_id": tentativa}, HTTP_HOST="meshcraft.top"
    )
    pedido.admin = {"email": "admin@example.test"}
    with patch("apps.core.pagamentos.site_de", return_value="site-um"), patch(
        "apps.core.pagamentos.PagamentosClient.devolver", return_value=(200, {"estorno": "solicitado"})
    ) as devolver:
        resposta = pagamentos_devolver(pedido)
    assert resposta.status_code == 302
    devolver.assert_called_once_with("site-um", tentativa)
