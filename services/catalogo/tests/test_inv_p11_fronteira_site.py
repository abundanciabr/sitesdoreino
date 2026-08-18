# tests/test_inv_p11_fronteira_site.py  # [RECEITA:R5 v1]
# Nome do arquivo = código do invariante. Um arquivo por invariante.
import pytest

from apps.ofertas.models import Offer
from apps.produtos.models import Product
from apps.sites.models import Site

pytestmark = pytest.mark.django_db


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def test_host_nao_cadastrado_e_404_nunca_site_padrao(client, token_valido):
    Site.objects.create(host="cadastrado.com.br", name="Cadastrado", active=True)

    resp = client.get(
        "/api/catalogo/sites/by-host/nao-cadastrado.teste",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )

    assert resp.status_code == 404


def test_mesma_slug_em_outro_site_nao_vaza_pela_fronteira(client, token_valido):
    site_a = Site.objects.create(host="loja-a.com.br", name="Loja A", active=True)
    site_b = Site.objects.create(host="loja-b.com.br", name="Loja B", active=True)
    produto = Product.objects.create(slug="curso-x", name="Curso X", price_cents=1000)
    Offer.objects.create(site=site_a, slug="curso-x", product=produto, price_cents=1000)
    # Site B nunca cadastrou "curso-x" — mesma slug, site diferente.

    resp_a = client.get(
        f"/api/catalogo/sites/{site_a.id}/ofertas/curso-x",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    resp_b = client.get(
        f"/api/catalogo/sites/{site_b.id}/ofertas/curso-x",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )

    assert resp_a.status_code == 200
    assert resp_a.json()["price_cents"] == 1000
    assert resp_b.status_code == 404  # [INV-P11] existir noutro site não é existir aqui


def test_site_inativo_e_404_por_host_e_por_oferta(client, token_valido):
    site = Site.objects.create(
        host="desativado.com.br", name="Desativado", active=False
    )
    produto = Product.objects.create(slug="curso-y", name="Curso Y", price_cents=500)
    Offer.objects.create(site=site, slug="curso-y", product=produto, price_cents=500)

    resp_host = client.get(
        "/api/catalogo/sites/by-host/desativado.com.br",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    resp_oferta = client.get(
        f"/api/catalogo/sites/{site.id}/ofertas/curso-y",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )

    assert resp_host.status_code == 404
    assert resp_oferta.status_code == 404
