"""O meshcraft.top multilíngue DE VERDADE: matriz D1 viva, landing prefixada
nos 3 idiomas e sitemap.xml.

Desde a FASE 4 os 3 idiomas vêm do CATÁLOGO (`conftest.SITE_MESH`, no formato
do contrato) — nenhum arquivo local declara idioma, e nenhum teste aqui
monkeypatcha registro nenhum. O `es` continua `indexable: false`: noindex,
fora do hreflang e fora do sitemap."""

import httpx
import pytest
from django.utils.html import escape

from apps.i18n.catalogo import t
from tests.conftest import (
    CATALOGO,
    HOST_A,
    HOST_DESCONHECIDO,
    HOST_MESH,
    OFERTA_MESH,
    SITE_MESH_SEM_IDIOMAS,
)

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
# sitemap.xml — rota de máquina (D6): host canônico do Site, es fora.
# ---------------------------------------------------------------------------
def test_sitemap_lista_so_os_idiomas_indexaveis_com_host_canonico(client, rede):
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
    assert "/es" not in conteudo  # D5: `indexable: false` fica fora do sitemap


def test_sitemap_agora_depende_do_catalogo_e_404_em_host_desconhecido(client, rede):
    # MUDANÇA DA FASE 4, declarada: os idiomas do sitemap vêm do catálogo,
    # então esta rota deixou de ser isenta do CONV-SITE (só /healthz e
    # /static/ continuam). Host que o catálogo não conhece morre 404 no
    # middleware, como qualquer outra rota — nunca um sitemap de site padrão.
    assert client.get("/sitemap.xml", HTTP_HOST=HOST_DESCONHECIDO).status_code == 404
    assert [c for c in rede.calls if "/sites/by-host/" in str(c.request.url)] != []


def test_sitemap_de_site_monolingue_404(client, rede):
    resp = client.get("/sitemap.xml", HTTP_HOST=HOST_A)  # Site sem `languages`
    assert resp.status_code == 404


def test_sitemap_prefixado_404_rota_de_maquina_nunca_se_localiza(client, rede):
    resp = client.get("/en/sitemap.xml", HTTP_HOST=HOST_MESH)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DEGRADAÇÃO DECLARADA (fase 4): o catálogo ainda não serve os campos.
# ---------------------------------------------------------------------------
def test_catalogo_sem_os_campos_de_idioma_serve_o_site_monolingue(client, rede):
    """O motivo de este PR só entrar DEPOIS do deploy verde do catálogo.

    Site vivo, catálogo de pé, mas sem `default_language`/`languages` (o que o
    provedor devolve hoje): o funil serve o meshcraft como MONOLÍNGUE — a
    landing volta a responder na raiz e as URLs prefixadas somem (404). Nada
    quebra, nada fica meio-traduzido, e o sitemap some junto. Mergear na ordem
    inversa deixaria o site sem /en/ até o catálogo subir."""
    rede.get(f"{CATALOGO}/sites/by-host/{HOST_MESH}").mock(
        return_value=httpx.Response(200, json=SITE_MESH_SEM_IDIOMAS)
    )
    assert client.get("/", HTTP_HOST=HOST_MESH).status_code == 200
    for caminho in ("/en/", "/pt-br/", "/es/", "/en/cadastro"):
        assert client.get(caminho, HTTP_HOST=HOST_MESH).status_code == 404
    assert client.get("/sitemap.xml", HTTP_HOST=HOST_MESH).status_code == 404
