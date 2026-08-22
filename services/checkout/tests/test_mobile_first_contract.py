# tests/test_mobile_first_contract.py  [RECEITA:R10 v1] adaptado — guarda de
# doutrina (AGENTS.checkout.md: páginas mobile-first) e não de invariante numerado.
#
# Caminhos SEM o prefixo "checkout/": as rotas de página perderam o prefixo em
# 22/08/2026 (em produção o SCRIPT_NAME=/checkout é removido pelo ASGI antes do
# casamento de rotas, e rota COM o prefixo dentro só casava com a URL dobrada
# /checkout/checkout/... — semântica completa em test_paginas_producao.py).
# Aqui, sem FORCE_SCRIPT_NAME, o caminho de dev também é sem prefixo.
import re

import pytest

from tests.conftest import HOST_A, SLUG

pytestmark = pytest.mark.django_db

VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">'


def _sem_largura_fixa_de_desktop(html: str) -> bool:
    return not re.search(r"width:\s*\d{3,}px", html)


def _abrir_pedido(api, sessao_a, method):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "method": method,
        },
    )
    assert resp.status_code == 201, resp.content
    return resp.json()["order_id"]


@pytest.mark.smoke_checkout
def test_pagina_dados_e_mobile_first(client, rede):
    resp = client.get(f"/{SLUG}/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    corpo = resp.content.decode()
    assert VIEWPORT in corpo
    assert _sem_largura_fixa_de_desktop(corpo)


def test_pagina_pix_e_mobile_first(client, api, rede, sessao_a):
    order_id = _abrir_pedido(api, sessao_a, "pix")
    resp = client.get(f"/pedido/{order_id}/pix/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    corpo = resp.content.decode()
    assert VIEWPORT in corpo
    assert _sem_largura_fixa_de_desktop(corpo)


def test_pagina_cartao_e_mobile_first(client, api, rede, sessao_a):
    order_id = _abrir_pedido(api, sessao_a, "card")
    resp = client.get(f"/pedido/{order_id}/cartao/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    corpo = resp.content.decode()
    assert VIEWPORT in corpo
    assert _sem_largura_fixa_de_desktop(corpo)


def test_pix_nao_carrega_sdk_do_mercado_pago(client, api, rede, sessao_a):
    order_id = _abrir_pedido(api, sessao_a, "pix")
    resp = client.get(f"/pedido/{order_id}/pix/", HTTP_HOST=HOST_A)
    corpo = resp.content.decode().lower()
    assert "mercadopago" not in corpo


def test_pagina_pix_de_pedido_de_cartao_e_404(client, api, rede, sessao_a):
    """Doutrina: dados/pix/cartão são ilhas — a página do método errado não
    pode nem renderizar o snapshot do pedido."""
    order_id = _abrir_pedido(api, sessao_a, "card")
    resp = client.get(f"/pedido/{order_id}/pix/", HTTP_HOST=HOST_A)
    assert resp.status_code == 404


def test_pagina_de_pedido_de_outro_site_e_404(client, api, rede, sessao_a):
    from tests.conftest import HOST_B

    order_id = _abrir_pedido(api, sessao_a, "pix")
    resp = client.get(f"/pedido/{order_id}/pix/", HTTP_HOST=HOST_B)
    assert resp.status_code == 404
