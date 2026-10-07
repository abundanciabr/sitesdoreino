import uuid

import pytest

from apps.core.api import _ambiente_de_teste
from apps.pedidos.models import Order, Session
from tests.conftest import HOST_A, SITE_A

pytestmark = pytest.mark.django_db


@pytest.fixture
def production(settings):
    settings.MP_PRODUCTION_PUBLIC_KEY = "APP_USR-publica-simulada"
    settings.MP_PRODUCTION_ENABLED_SITES = frozenset({SITE_A["id"]})
    settings.MP_PRODUCTION_PRODUCT_IDS = frozenset({"produto-producao"})
    settings.MP_PUBLIC_KEY = "TEST-simulada"
    settings.APPMAX_CARD_ENABLED_SITES = frozenset()
    settings.FORCE_SCRIPT_NAME = "/checkout"


def test_oferta_habilita_cartao_sem_appmax(client, rede, production):
    page = client.get("/teste-mercado-pago/", HTTP_HOST=HOST_A)
    assert page.status_code == 200
    assert b'<script id="appmax-card-enabled" type="application/json">true</script>' in page.content
    assert not _ambiente_de_teste(SITE_A["id"], "card", False, "produto-producao")
    assert _ambiente_de_teste(SITE_A["id"], "card", False, "outro-produto")


def test_pagina_usa_sdk_publico_de_producao_e_campos_seguros(client, rede, production):
    session = Session.objects.create(site_id=SITE_A["id"], offer_slug="teste-mercado-pago", offer={})
    order = Order.objects.create(
        session=session, site_id=SITE_A["id"], items=[{"product_id": "produto-producao", "price_cents": 990}],
        total_cents=990, customer={"email": "pagador@example.com"}, method="card", intent_id=str(uuid.uuid4()),
    )
    page = client.get(f"/pedido/{order.id}/cartao/", HTTP_HOST=HOST_A)
    assert page.status_code == 200
    html = page.content.decode()
    assert "APP_USR-publica-simulada" in html and "TEST-simulada" not in html
    assert "scripts.appmax" not in html and "appmax-form-element" not in html
    assert 'src="/checkout/static/checkout/cartao_mp.js"' in html
    assert 'src="https://sdk.mercadopago.com/js/v2"' in html
    assert 'id="mp-card-number" class="campo"' in html and 'id="mp-security" class="campo"' in html
    assert "Pagamento à vista" in html
    asset = client.get("/static/checkout/cartao_mp.js", HTTP_HOST=HOST_A)
    assert asset.status_code == 200
