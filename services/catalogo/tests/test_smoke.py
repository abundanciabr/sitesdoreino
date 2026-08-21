# [RECEITA:R10 v1]
import pytest
from django.core.management import call_command

from apps.ofertas.models import Offer
from apps.produtos.models import Product
from apps.sites.models import Site


@pytest.mark.smoke_catalogo
def test_healthz_responde_200(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/api/catalogo/sites/by-host/loja1.com.br",
        "/api/catalogo/sites/site-1/ofertas/curso-esqueleto",
        "/api/catalogo/produtos/produto-1",
    ],
)
def test_superficie_da_api_serve_do_banco(client, token_valido, path):
    """A superfície espelha o contrato congelado e os handlers servem do banco:
    sem dado cadastrado, a resposta é 404 (nunca 501/500)."""
    resp = client.get(path, HTTP_AUTHORIZATION=f"Bearer {token_valido}")
    assert resp.status_code == 404


def test_superficie_sem_token_e_401(client):
    resp = client.get("/api/catalogo/produtos/produto-1")
    assert resp.status_code == 401


# [RECEITA:R9 v1] — seed idempotente do esqueleto
@pytest.mark.django_db
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


@pytest.mark.django_db
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
# golpe4: comentario trivial e reversivel para teste de orcamento
