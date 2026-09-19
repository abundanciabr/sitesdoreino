# tests/test_paginas_pela_porta.py
# As quatro rotas da estrutura de paginas, da cadeira de quem consome.
import pytest

from apps.ofertas.models import Offer
from apps.paginas.models import Page, PageVersion
from apps.produtos.models import Product
from apps.sites.models import Site

pytestmark = pytest.mark.django_db


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


@pytest.fixture
def cenario():
    site = Site.objects.create(host="loja.com.br", name="Loja", active=True)
    produto = Product.objects.create(slug="curso-z", name="Curso Z", price_cents=990)
    oferta = Offer.objects.create(
        site=site, slug="curso-z", product=produto, price_cents=990
    )
    pagina = Page.objects.create(site=site, slug="oferta", offer=oferta)
    return site, oferta, pagina


def _get(client, token, url):
    return client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")


def _put(client, token, url, corpo):
    return client.put(
        url,
        data=corpo,
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


def _post(client, token, url):
    return client.post(url, HTTP_AUTHORIZATION=f"Bearer {token}")


def test_rascunho_de_pagina_recem_criada_e_200_vazio(client, token_valido, cenario):
    site, _, _ = cenario

    resp = _get(
        client, token_valido, f"/api/catalogo/sites/{site.id}/paginas/oferta/rascunho"
    )

    # Toda pagina nasce com um rascunho, ainda que vazio: "ainda nao escrevi
    # nada" e estado normal de quem vai configurar, nao erro, pela mesma regra
    # do `getSiteMenu`.
    assert resp.status_code == 200
    assert resp.json()["secoes"] == []
    assert resp.json()["base_version"] == 0


def test_gravar_rascunho_devolve_as_secoes_na_ordem_canonica(
    client, token_valido, cenario
):
    site, _, _ = cenario

    resp = _put(
        client,
        token_valido,
        f"/api/catalogo/sites/{site.id}/paginas/oferta/rascunho",
        {
            "secoes": [
                {"nome": "oferta", "ordem": 0, "slots": {"preco_texto": "R$ 9,90"}},
                {"nome": "hero", "ordem": 0, "slots": {"headline": "Curso Z"}},
            ]
        },
    )

    assert resp.status_code == 200
    assert [secao["nome"] for secao in resp.json()["secoes"]] == ["hero", "oferta"]

    lido = _get(
        client, token_valido, f"/api/catalogo/sites/{site.id}/paginas/oferta/rascunho"
    )
    assert [secao["nome"] for secao in lido.json()["secoes"]] == ["hero", "oferta"]


def test_rascunho_com_secao_invalida_e_422_e_nada_e_gravado(
    client, token_valido, cenario
):
    site, _, _ = cenario

    resp = _put(
        client,
        token_valido,
        f"/api/catalogo/sites/{site.id}/paginas/oferta/rascunho",
        {"secoes": [{"nome": "banner", "ordem": 0, "slots": {"headline": "x"}}]},
    )

    assert resp.status_code == 422
    assert "banner" in resp.json()["detail"]
    assert "hero" in resp.json()["detail"]

    lido = _get(
        client, token_valido, f"/api/catalogo/sites/{site.id}/paginas/oferta/rascunho"
    )
    assert lido.json()["secoes"] == []


def test_publicar_congela_o_rascunho_e_a_versao_cresce(client, token_valido, cenario):
    site, _, pagina = cenario
    rascunho = f"/api/catalogo/sites/{site.id}/paginas/oferta/rascunho"
    publicar = f"/api/catalogo/sites/{site.id}/paginas/oferta/publicar"

    _put(
        client,
        token_valido,
        rascunho,
        {"secoes": [{"nome": "hero", "ordem": 0, "slots": {"headline": "Um"}}]},
    )
    primeira = _post(client, token_valido, publicar)

    assert primeira.status_code == 200
    assert primeira.json()["version"] == 1
    assert primeira.json()["offer_slug"] == "curso-z"
    assert primeira.json()["secoes"][0]["slots"]["headline"] == "Um"

    _put(
        client,
        token_valido,
        rascunho,
        {"secoes": [{"nome": "hero", "ordem": 0, "slots": {"headline": "Dois"}}]},
    )
    segunda = _post(client, token_valido, publicar)

    assert segunda.json()["version"] == 2
    # A primeira versao continua la, intacta: publicar nao reescreve o passado.
    assert PageVersion.objects.filter(page=pagina).count() == 2
    assert (
        PageVersion.objects.get(page=pagina, version=1).secoes[0]["slots"]["headline"]
        == "Um"
    )


def test_publicada_serve_sempre_a_ultima_versao(client, token_valido, cenario):
    site, _, pagina = cenario
    PageVersion.objects.create(
        page=pagina,
        version=1,
        secoes=[{"nome": "hero", "slots": {"headline": "Velha"}}],
    )
    PageVersion.objects.create(
        page=pagina, version=2, secoes=[{"nome": "hero", "slots": {"headline": "Nova"}}]
    )

    resp = _get(client, token_valido, f"/api/catalogo/sites/{site.id}/paginas/oferta")

    assert resp.status_code == 200
    assert resp.json()["version"] == 2
    assert resp.json()["secoes"][0]["slots"]["headline"] == "Nova"


def test_publicar_rascunho_vazio_e_409(client, token_valido, cenario):
    site, _, _ = cenario

    resp = _post(
        client, token_valido, f"/api/catalogo/sites/{site.id}/paginas/oferta/publicar"
    )

    assert resp.status_code == 409
    assert "rascunho" in resp.json()["detail"].lower()


def test_pagina_nunca_publicada_e_404_na_rota_publicada(client, token_valido, cenario):
    site, _, _ = cenario

    resp = _get(client, token_valido, f"/api/catalogo/sites/{site.id}/paginas/oferta")

    assert resp.status_code == 404


def test_slug_e_unico_por_site_e_a_pagina_de_um_site_nao_vaza_para_outro(
    client, token_valido, cenario
):
    site_a, _, pagina_a = cenario
    site_b = Site.objects.create(host="outra.com.br", name="Outra", active=True)
    PageVersion.objects.create(
        page=pagina_a,
        version=1,
        secoes=[{"nome": "hero", "slots": {"headline": "Do A"}}],
    )
    # Mesma slug no site B: existir noutro site nao e existir aqui (INV-P11).
    pagina_b = Page.objects.create(site=site_b, slug="oferta")
    PageVersion.objects.create(
        page=pagina_b,
        version=1,
        secoes=[{"nome": "hero", "slots": {"headline": "Do B"}}],
    )

    resp_a = _get(
        client, token_valido, f"/api/catalogo/sites/{site_a.id}/paginas/oferta"
    )
    resp_b = _get(
        client, token_valido, f"/api/catalogo/sites/{site_b.id}/paginas/oferta"
    )

    assert resp_a.json()["secoes"][0]["slots"]["headline"] == "Do A"
    assert resp_b.json()["secoes"][0]["slots"]["headline"] == "Do B"


def test_pagina_que_so_existe_noutro_site_e_404(client, token_valido, cenario):
    site_a, _, pagina_a = cenario
    site_b = Site.objects.create(host="vazia.com.br", name="Vazia", active=True)
    PageVersion.objects.create(
        page=pagina_a,
        version=1,
        secoes=[{"nome": "hero", "slots": {"headline": "Do A"}}],
    )

    for rota in ("", "/rascunho"):
        resp = _get(
            client,
            token_valido,
            f"/api/catalogo/sites/{site_b.id}/paginas/oferta{rota}",
        )
        assert resp.status_code == 404, rota
    resp = _post(
        client, token_valido, f"/api/catalogo/sites/{site_b.id}/paginas/oferta/publicar"
    )
    assert resp.status_code == 404


def test_site_desativado_nao_serve_pagina_publicada(client, token_valido):
    site = Site.objects.create(host="off.com.br", name="Off", active=False)
    pagina = Page.objects.create(site=site, slug="oferta")
    PageVersion.objects.create(
        page=pagina, version=1, secoes=[{"nome": "hero", "slots": {"headline": "x"}}]
    )

    resp = _get(client, token_valido, f"/api/catalogo/sites/{site.id}/paginas/oferta")

    assert resp.status_code == 404


def test_slot_vazio_some_da_resposta_em_vez_de_virar_texto_de_mentira(
    client, token_valido, cenario
):
    site, _, _ = cenario

    resp = _put(
        client,
        token_valido,
        f"/api/catalogo/sites/{site.id}/paginas/oferta/rascunho",
        {
            "secoes": [
                {
                    "nome": "hero",
                    "ordem": 0,
                    "slots": {"headline": "Curso Z", "subheadline": ""},
                },
                {"nome": "prova", "ordem": 0, "slots": {"depoimento": ""}},
            ]
        },
    )

    assert [secao["nome"] for secao in resp.json()["secoes"]] == ["hero"]
    assert resp.json()["secoes"][0]["slots"] == {"headline": "Curso Z"}


def test_sem_token_nenhuma_rota_responde(client, cenario):
    site, _, _ = cenario

    assert (
        client.get(f"/api/catalogo/sites/{site.id}/paginas/oferta").status_code == 401
    )
    assert (
        client.get(f"/api/catalogo/sites/{site.id}/paginas/oferta/rascunho").status_code
        == 401
    )
    assert (
        client.post(
            f"/api/catalogo/sites/{site.id}/paginas/oferta/publicar"
        ).status_code
        == 401
    )


def test_site_id_sem_forma_de_uuid_e_404_e_nao_500(client, token_valido, cenario):
    # Id torto e engano de quem chama, nao defeito do servidor: sem o guarda o
    # ORM estouraria e a resposta viraria 500.
    resp = _get(
        client, token_valido, "/api/catalogo/sites/nao-e-um-uuid/paginas/oferta"
    )

    assert resp.status_code == 404
