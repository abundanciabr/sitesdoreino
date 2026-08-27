"""O meshcraft.top multilíngue DE VERDADE: matriz D1 viva, landing prefixada
nos 3 idiomas e sitemap.xml.

Desde a FASE 4 os 3 idiomas vêm do CATÁLOGO (`conftest.SITE_MESH`, no formato
do contrato) — nenhum arquivo local declara idioma, e nenhum teste aqui
monkeypatcha registro nenhum. O `es` continua `indexable: false`: noindex,
fora do hreflang e fora do sitemap."""

import httpx
import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils.html import escape

from apps.core.enderecos import CAIXA_PADRAO as CAIXA
from apps.core.middleware import SiteResolutionMiddleware
from apps.i18n.catalogo import t

# `logado` e `COOKIE` moram no arquivo que os define — mesma importação que
# tests/test_sino.py faz, pelo mesmo motivo: a fixture de "alguém entrou" é
# uma só, e duplicá-la aqui seria duas verdades sobre o que a sessão devolve.
from test_sessao_no_site import COOKIE, logado  # noqa: F401  (fixture)
from tests.conftest import (
    CATALOGO,
    HOST_A,
    HOST_DESCONHECIDO,
    HOST_MESH,
    SITE_MESH_SEM_IDIOMAS,
    caminho_mesh,
)

IDIOMAS = ("en", "pt-br", "es")


# ---------------------------------------------------------------------------
# Matriz D1 viva — REVISTA em 25/08/2026: o inglês mora na raiz nua, sem
# prefixo, e `/en/…` deixou de existir.
# ---------------------------------------------------------------------------
def test_raiz_serve_o_ingles_sem_redirecionar(client, rede):
    # O endereço que o dono do projeto divulga: meshcraft.top, em inglês, 200
    # na primeira requisição — sem salto de redirecionamento no caminho de
    # maior volume de um funil de tráfego pago.
    resp = client.get("/", HTTP_HOST=HOST_MESH)
    assert resp.status_code == 200
    assert b'<html lang="en"' in resp.content


def test_cadastro_nu_serve_o_ingles(client, rede):
    resp = client.get("/cadastro", HTTP_HOST=HOST_MESH)
    assert resp.status_code == 200
    assert b'<html lang="en"' in resp.content


def test_prefixo_do_idioma_padrao_e_404(client, rede):
    # A escolha do mantenedor em 25/08/2026: `/en/…` não redireciona para a
    # forma nua, deixa de existir. Uma forma canônica por página, sem gêmea —
    # e nada estava indexado quando a decisão foi tomada.
    for caminho in ("/en", "/en/", "/en/cadastro", "/en/login"):
        resp = client.get(caminho, HTTP_HOST=HOST_MESH)
        assert resp.status_code == 404, f"{caminho} devolveu {resp.status_code}"


def test_post_no_caminho_nu_chega_a_view_e_cria_o_lead(client, rede):
    # Ganho direto de não haver redirecionamento no meio: na matriz antiga este
    # POST era 404 (302 converteria em GET e descartaria o corpo). Agora ele é
    # simplesmente o cadastro em inglês.
    resp = client.post(
        "/cadastro",
        {"name": "Ana", "email": "ana@exemplo.com", "phone": ""},
        HTTP_HOST=HOST_MESH,
    )
    assert resp.status_code == 200
    enviados = [c for c in rede.calls if str(c.request.url).endswith("/leads")]
    assert enviados, "o POST no caminho nu não chegou à célula leads"
    assert b'"source":"cadastro-meshcraft-en"' in enviados[-1].request.content


def test_idioma_nao_habilitado_404(client, rede):
    resp = client.get("/fr/cadastro", HTTP_HOST=HOST_MESH)
    assert resp.status_code == 404


@pytest.mark.parametrize("forma", ["EN", "En", "PT-BR", "pt_br", "Es"])
def test_forma_nao_canonica_de_idioma_habilitado_e_404(client, rede, forma):
    # Fail-closed, nunca redirect: nada nunca linkou para essas formas.
    assert client.get(f"/{forma}/", HTTP_HOST=HOST_MESH).status_code == 404


@pytest.mark.parametrize("curto", ["faq", "api", "pro"])
def test_endereco_curto_em_ingles_chega_ao_urlconf(rede, curto):
    """404 do urlconf, não de uma regex — e a diferença é o futuro do site.

    Até 25/08/2026 uma regex de 2-3 letras recusava QUALQUER primeiro segmento
    com "cara de idioma", o que condenava `/faq`, `/api` e `/pro` a nunca
    existirem como página. Só não doía porque o inglês vivia atrás de `/en/`.

    Medir isso pelo status seria um teste vazio: `/faq` responde 404 dos dois
    jeitos — a página realmente não existe ainda. O que mudou é ONDE o 404
    nasce, então a prova é um espião no lugar da view: se o middleware ainda
    barrasse o caminho, a view não seria chamada nenhuma vez.
    """
    chegou = {}

    def espiao(request):
        chegou["idioma"] = request.idioma
        chegou["path_info"] = request.path_info
        return HttpResponse("ok")

    pedido = RequestFactory().get(f"/{curto}", HTTP_HOST=HOST_MESH)
    SiteResolutionMiddleware(espiao)(pedido)

    assert chegou == {"idioma": "en", "path_info": f"/{curto}"}, (
        f"/{curto} não chegou à resolução de URL — algo no resolver ainda o "
        "confunde com um pedido de idioma. Endereço curto em inglês é página "
        "legítima desde o D1 revisto (25/08/2026)."
    )


# ---------------------------------------------------------------------------
# A HOME prefixada nos 3 idiomas (template landing_i18n.html).
#
# REESCRITA em 27/08/2026 com a página: a raiz do site deixou de ser vitrine
# de oferta (preço, "Quero comprar", formulário de captura) e virou porta —
# quem não entrou vê o convite para entrar; quem entrou vê o aviso de novidade
# e o caminho para a Caixa. O que estes testes mediam antes (a oferta no
# idioma, a ilha Alpine) não existe mais NA RAIZ; a captura de lead segue
# inteira em `/cadastro`, medida em test_cadastro.py.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_home_de_visitante_convida_a_entrar_no_idioma(client, rede, idioma):
    resp = client.get(caminho_mesh(idioma), HTTP_HOST=HOST_MESH)
    assert resp.status_code == 200
    conteudo = resp.content.decode()
    assert escape(t("landing.titulo", idioma)) in conteudo
    assert escape(t("landing.entrar", idioma)) in conteudo
    # Quem não entrou não vê nem o aviso de novidade nem o caminho da Caixa:
    # a página de quem chegou agora não anuncia uma área que ela não alcança.
    assert escape(t("landing.novidades", idioma)) not in conteudo
    assert CAIXA not in conteudo


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_home_de_quem_entrou_avisa_a_novidade_e_leva_a_caixa(client, logado, idioma):
    conteudo = client.get(
        caminho_mesh(idioma), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert escape(t("landing.novidades", idioma)) in conteudo
    assert f'href="{CAIXA}"' in conteudo
    assert escape(t("landing.ir_para_a_caixa", idioma)) in conteudo
    # E o convite para entrar some — quem já entrou não é convidado de novo.
    assert escape(t("landing.entrar", idioma)) not in conteudo


def test_a_home_nao_pergunta_oferta_nenhuma_ao_catalogo(client, rede):
    """A dependência que caiu junto com a vitrine, e por que ela vale um teste.

    Enquanto a raiz mostrava preço, ela pedia a `default_offer` ao catálogo a
    cada visita — e respondia **404** ao site que não tivesse uma. A home nova
    não mostra oferta nenhuma: manter a consulta seria pagar um salto de rede
    por visita e, pior, deixar a porta do site fechada por causa de um campo
    que a página não usa mais. Site monolíngue segue como sempre (a vitrine
    ainda é vitrine): `test_landing.py::test_site_sem_oferta_padrao_e_404`.
    """
    resp = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH)

    assert resp.status_code == 200
    assert [c for c in rede.calls if "/ofertas/" in str(c.request.url)] == []


def test_post_leads_prefixado_funciona(client, rede):
    # A rota /leads segue pública e prefixável (a vitrine monolíngue posta
    # nela); o que saiu foi a ilha Alpine DA RAIZ multilíngue, não a rota.
    resp = client.post(
        "/pt-br/leads",
        '{"email": "aluno@exemplo.com"}',
        "application/json",
        HTTP_HOST=HOST_MESH,
    )
    assert resp.status_code == 200
    assert resp.json()["created"] is True


def test_a_caixa_segue_sem_prefixo_de_idioma(client, logado):
    # D6, guarda 3: a Caixa é outra célula, monolíngue — o link NÃO ganha
    # prefixo (prefixado, cairia no funil e morreria 404 no gateway real).
    # Era o link do checkout que provava isto até 27/08/2026; a home nova não
    # linka checkout nenhum, e quem carrega a prova agora é a Caixa.
    conteudo = client.get(
        caminho_mesh("en"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()
    assert f'href="{CAIXA}"' in conteudo
    assert 'href="/en/forms/' not in conteudo


# ---------------------------------------------------------------------------
# sitemap.xml — rota de máquina (D6): host canônico do Site, es fora.
# ---------------------------------------------------------------------------
def test_sitemap_lista_so_os_idiomas_indexaveis_com_host_canonico(client, rede):
    resp = client.get("/sitemap.xml", HTTP_HOST=HOST_MESH)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/xml"
    conteudo = resp.content.decode()
    for url in (
        f"https://{HOST_MESH}/",  # inglês: a raiz nua, nunca /en/ (D1 revisto)
        f"https://{HOST_MESH}/cadastro",
        f"https://{HOST_MESH}/pt-br/",
        f"https://{HOST_MESH}/pt-br/cadastro",
    ):
        assert f"<loc>{url}</loc>" in conteudo
    # Um sitemap que anunciasse /en/ mandaria o Google a 404 nossos.
    assert "/en/" not in conteudo
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


@pytest.mark.parametrize("caminho", ["/en/sitemap.xml", "/pt-br/sitemap.xml"])
def test_sitemap_prefixado_404_rota_de_maquina_nunca_se_localiza(client, rede, caminho):
    # Os dois morrem 404, por ramos DIFERENTES do resolver: `/en/…` porque o
    # idioma padrão não tem prefixo (ramo 1), `/pt-br/sitemap.xml` pela guarda
    # de rota de máquina depois da decapagem (armadilhas/086). Vale exercitar
    # os dois — o dia em que um deles regredir, o outro não avisa.
    assert client.get(caminho, HTTP_HOST=HOST_MESH).status_code == 404


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
    for caminho in ("/pt-br/", "/es/", "/pt-br/cadastro", "/cadastro"):
        assert client.get(caminho, HTTP_HOST=HOST_MESH).status_code == 404
    assert client.get("/sitemap.xml", HTTP_HOST=HOST_MESH).status_code == 404
