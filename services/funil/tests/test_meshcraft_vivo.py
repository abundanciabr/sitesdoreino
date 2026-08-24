"""Fase 2 do PLANO-I18N — o meshcraft.top registrado DE VERDADE: matriz D1
viva contra o sites_i18n.yaml real (instalado no boot — nenhum monkeypatch de
registro aqui), landing prefixada nos 3 idiomas e sitemap.xml por Host."""

import pytest
from django.utils.html import escape

from apps.i18n.catalogo import t
from tests.conftest import HOST_A, HOST_MESH, OFERTA_MESH

IDIOMAS = ("en", "pt-br", "es")


# ---------------------------------------------------------------------------
# Matriz D1 viva (o registro real fez a raiz flipar para o regime prefixado).
# ---------------------------------------------------------------------------
def test_raiz_302_para_o_default_en(client, rede):
    resp = client.get("/", HTTP_HOST=HOST_MESH)
    assert resp.status_code == 302
    assert resp["Location"] == "/en/"
    assert resp["Cache-Control"] == "max-age=300"


def test_cadastro_nu_get_302_para_o_default(client, rede):
    resp = client.get("/cadastro", HTTP_HOST=HOST_MESH)
    assert resp.status_code == 302
    assert resp["Location"] == "/en/cadastro"


def test_cadastro_nu_post_404(client, rede):
    # 302 converteria POST em GET e descartaria o corpo em silêncio (D1).
    resp = client.post("/cadastro", {"email": "a@b.c"}, HTTP_HOST=HOST_MESH)
    assert resp.status_code == 404


def test_idioma_nao_habilitado_404(client, rede):
    resp = client.get("/fr/cadastro", HTTP_HOST=HOST_MESH)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Landing prefixada nos 3 idiomas (template landing_i18n.html).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_landing_prefixada_serve_a_oferta_no_idioma(client, rede, idioma):
    resp = client.get(f"/{idioma}/", HTTP_HOST=HOST_MESH)
    assert resp.status_code == 200
    conteudo = resp.content.decode()
    assert OFERTA_MESH["product"]["name"] in conteudo  # nome de produto é DADO
    assert "9,90" in conteudo  # price_cents 990
    assert escape(t("landing.cta_comprar", idioma)) in conteudo
    assert escape(t("landing.novidades_titulo", idioma)) in conteudo


def test_landing_i18n_ilha_posta_na_url_prefixada_com_idioma_no_source(client, rede):
    conteudo = client.get("/pt-br/", HTTP_HOST=HOST_MESH).content.decode()
    # {% url_i18n 'capturar_lead' %}: o /leads NU é 404 pela matriz — o action
    # da ilha TEM de sair prefixado (pendência 2 do PR #87).
    assert '"/pt-br/leads"' in conteudo
    assert "lp-funil-pt-br" in conteudo  # D9: idioma do lead é dado de negócio


def test_post_leads_prefixado_da_ilha_funciona(client, rede):
    resp = client.post(
        "/pt-br/leads",
        '{"email": "aluno@exemplo.com"}',
        "application/json",
        HTTP_HOST=HOST_MESH,
    )
    assert resp.status_code == 200
    assert resp.json()["created"] is True


def test_checkout_segue_sem_prefixo_de_idioma(client, rede):
    # D6 fora desta fase: checkout é outra célula, monolíngue — o link NÃO
    # ganha prefixo (prefixado, cairia no funil e morreria 404 no gateway real).
    conteudo = client.get("/en/", HTTP_HOST=HOST_MESH).content.decode()
    assert f'href="/checkout/{OFERTA_MESH["slug"]}/"' in conteudo


# ---------------------------------------------------------------------------
# sitemap.xml — rota de máquina (D6): por Host, host canônico, es fora.
# ---------------------------------------------------------------------------
def test_sitemap_lista_so_os_idiomas_indexaveis_com_host_canonico(client):
    resp = client.get("/sitemap.xml", HTTP_HOST=HOST_MESH)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/xml"
    conteudo = resp.content.decode()
    for url in (
        f"https://{HOST_MESH}/en/",
        f"https://{HOST_MESH}/en/cadastro",
        f"https://{HOST_MESH}/pt-br/",
        f"https://{HOST_MESH}/pt-br/cadastro",
    ):
        assert f"<loc>{url}</loc>" in conteudo
    assert "/es" not in conteudo  # D5: noindex fica fora do sitemap


def test_sitemap_nao_depende_do_catalogo(client):
    # SEM fixture de rede de propósito: se o sitemap resolvesse o site no
    # catálogo, o httpx estouraria aqui (nenhum mock ativo) — é isenção como
    # o /healthz, por construção.
    resp = client.get("/sitemap.xml", HTTP_HOST=HOST_MESH)
    assert resp.status_code == 200


def test_sitemap_de_site_nao_registrado_404(client):
    resp = client.get("/sitemap.xml", HTTP_HOST=HOST_A)
    assert resp.status_code == 404


def test_sitemap_prefixado_404_rota_de_maquina_nunca_se_localiza(client, rede):
    resp = client.get("/en/sitemap.xml", HTTP_HOST=HOST_MESH)
    assert resp.status_code == 404
