"""Guarda: o aviso da Appmax chega no endereco que ela usa.

A Appmax dispara os avisos para /api/pagamentos/appmax/webhooks (plural), o
endereco cadastrado no aplicativo dela. Enquanto a rota era a do singular,
todo aviso caiu em 404. Este teste reprova se a rota do receptor deixar de ser
a do plural ou se o singular voltar como apelido.
"""

from django.test import Client
from django.urls import Resolver404, resolve

from pagamentos.api.webhooks import webhook_appmax

ROTA_DO_AVISO = "/api/pagamentos/appmax/webhooks"
ROTA_ANTIGA = "/api/pagamentos/appmax/webhook"


def test_rota_do_aviso_e_a_do_plural_que_a_appmax_usa():
    assert resolve(ROTA_DO_AVISO).func is webhook_appmax


def test_singular_nao_e_apelido_do_receptor():
    try:
        destino = resolve(ROTA_ANTIGA).func
    except Resolver404:
        return
    assert destino is not webhook_appmax


def test_post_no_plural_chega_ao_receptor_e_o_singular_nao():
    cliente = Client()
    assert (
        cliente.post(ROTA_ANTIGA, "{}", content_type="application/json").status_code
        == 404
    )
    assert (
        cliente.post(ROTA_DO_AVISO, "{}", content_type="application/json").status_code
        != 404
    )
