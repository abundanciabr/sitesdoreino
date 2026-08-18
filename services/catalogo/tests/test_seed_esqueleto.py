# tests/test_seed_esqueleto.py  # [RECEITA:R9 v1]
import pytest
from django.core.management import call_command

from apps.ofertas.models import Offer
from apps.produtos.models import Product
from apps.sites.models import Site

pytestmark = pytest.mark.django_db


def test_seed_e_idempotente_rodar_2x_nao_duplica():
    call_command("seed_esqueleto")
    call_command("seed_esqueleto")

    assert Site.objects.count() == 1
    assert Product.objects.filter(slug="curso-esqueleto").count() == 1
    assert Offer.objects.count() == 1

    site = Site.objects.get()
    oferta = Offer.objects.get()
    assert oferta.site_id == site.id
    assert oferta.slug == "curso-esqueleto"
    assert oferta.price_cents == 990
    assert site.default_offer_slug == "curso-esqueleto"


def test_seed_expoe_990_cents_via_api(client, settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    call_command("seed_esqueleto")
    site = Site.objects.get()

    resp = client.get(
        f"/api/catalogo/sites/{site.id}/ofertas/curso-esqueleto",
        HTTP_AUTHORIZATION="Bearer token-de-teste",
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["price_cents"] == 990
    assert isinstance(body["price_cents"], int)  # amount_cents é sempre inteiro
