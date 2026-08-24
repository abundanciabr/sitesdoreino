"""Guardas 2 e 3 do D6 — os que valem HOJE, com a fase 5 congelada.

O D6 (`docs/i18n/PLANO-I18N.md`) decidiu o roteamento de idioma além do funil e
registrou três guardas como "teste"; a fase 5 (internacionalizar outra célula)
ficou congelada por falta de alvo legítimo, mas estes dois guardas independem
da ativação — protegem o roteamento de HOJE contra quebra silenciosa.

  GUARDA 2 — rotas de MÁQUINA nunca se localizam (`/api/**`, `/webhooks/**`,
  `/static/**`, `/healthz`, `/sitemap.xml`).
  GUARDA 3 — link para OUTRA célula sai SEM prefixo de idioma, e isso é
  deliberado: prefixá-lo hoje produz 404 (a prova está aqui embaixo).

O guarda 1 ("nenhum prefixo de rota de célula pode ter forma de locale") NÃO
mora aqui: ele lê `infra/traefik/dynamic/plataforma.yml` + `infra/sites.json`,
e a mudança que ele precisa pegar toca `infra/`, não `services/` — a CI de
célula nunca rodaria nesse PR. Vive em `ci/tests/test_rotas_sem_forma_de_locale.py`,
que roda em TODO PR pelo workflow `muralhas`. O porquê completo está no
cabeçalho de lá.
"""

import re
from urllib.parse import urlsplit

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import Resolver404, path, re_path, resolve

from apps.core.middleware import (
    CAMINHOS_DE_MAQUINA,
    CAMINHOS_SEM_SITE,
    ROTAS_DE_MAQUINA,
    SiteResolutionMiddleware,
)
from config.urls import urlpatterns
from tests.conftest import CATALOGO, HOST_MESH, IDIOMAS_MESH, OFERTA_MESH

IDIOMAS = tuple(idioma["code"] for idioma in IDIOMAS_MESH)


def _view(request):  # dublê: path()/re_path() exigem um callable
    return HttpResponse("ok")


# ===========================================================================
# GUARDA 2 — rotas de máquina nunca se localizam.
# ===========================================================================
def test_a_lista_de_isencoes_do_middleware_nao_regrediu():
    """As isenções são DADO do middleware; este teste é o cadeado delas.

    `/healthz` e `/static/` saem antes de QUALQUER lógica (nem catálogo, nem
    idioma): a sonda do container não pode depender do catálogo estar de pé.
    `/sitemap.xml` precisa do Site (desde a fase 4 os idiomas vêm do catálogo)
    mas nunca se localiza. Tirar um destes daqui é a regressão silenciosa que
    o D6 manda vigiar.
    """
    assert "/healthz" in CAMINHOS_SEM_SITE
    assert "/static/" in CAMINHOS_SEM_SITE
    assert "/sitemap.xml" in CAMINHOS_DE_MAQUINA


@pytest.mark.parametrize("caminho", ["/healthz", "/static/funil/api.js"])
def test_isencao_sem_site_roda_antes_do_catalogo_e_sem_idioma(rede, caminho):
    """A isenção é medida no comportamento, não só na constante.

    Espião no lugar da view: se a isenção regredir, o middleware chama o
    catálogo e/ou marca `request.idioma` — e este teste vê as duas coisas.
    """
    visto = {}

    def espiao(request):
        visto["path_info"] = request.path_info
        visto["idioma"] = getattr(request, "idioma", None)
        visto["site"] = getattr(request, "site", None)
        return HttpResponse("ok")

    pedido = RequestFactory().get(caminho, HTTP_HOST=HOST_MESH)
    SiteResolutionMiddleware(espiao)(pedido)

    assert visto == {"path_info": caminho, "idioma": None, "site": None}
    chamadas = [c for c in rede.calls if "/sites/by-host/" in str(c.request.url)]
    assert chamadas == [], f"{caminho} tocou o catálogo — a isenção regrediu"


@pytest.mark.parametrize(
    "caminho",
    [
        # /api/** — no gateway real estas rotas vão para OUTRAS células
        # (`checkout-api`, priority 20; `mp-webhooks`, priority 100). Com
        # prefixo de idioma nenhum PathPrefix casa, a request cai no catch-all
        # do funil (priority 1) — e é o funil que precisa dizer 404. É
        # exatamente o que este teste exercita.
        "/pt-br/api/checkout/sessions",
        "/en/api/checkout/orders",
        "/es/api/pagamentos/webhooks/mercadopago",
        # /webhooks/**
        "/pt-br/webhooks/mercadopago",
        # /static/**
        "/pt-br/static/funil/api.js",
        # /sitemap.xml — a rota de máquina que o funil REALMENTE serve
        "/pt-br/sitemap.xml",
        "/en/sitemap.xml",
    ],
)
def test_rota_de_maquina_prefixada_nao_vira_rota_localizada(client, rede, caminho):
    resp = client.get(caminho, HTTP_HOST=HOST_MESH)
    assert resp.status_code == 404, (
        f"{caminho} respondeu {resp.status_code} — rota de máquina ganhou "
        "versão localizada (D6). Uma URL de máquina por idioma é conteúdo "
        "duplicado para robô e superfície nova para ninguém."
    )


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_healthz_prefixado_deveria_ser_404(client, rede, idioma):
    """CONSERTADO em 24/08/2026 — nasceu `xfail(strict=True)` e virou guarda.

    O desvio era real e medido: a isenção do middleware casava o `path_info`
    CRU, então `/pt-br/healthz` não era isenta — o resolver decapava o prefixo
    e o urlconf servia a view, 200. A cura foi conferir `ROTAS_DE_MAQUINA`
    também DEPOIS de decapar (`apps/core/middleware.py`). O `strict=True`
    existia exatamente para este dia: o conserto deixou o teste vermelho por
    XPASS e obrigou a apagar o marcador, junto com o teste que afirmava o 200.
    O desvio não sumiu em silêncio — foi essa a intenção de quem o registrou.
    """
    assert client.get(f"/{idioma}/healthz", HTTP_HOST=HOST_MESH).status_code == 404


def test_healthz_nu_continua_servindo_com_o_catalogo_fora_do_ar(client, rede):
    # A garantia que a isenção existe para dar: sonda do container não morre
    # junto com o catálogo. É por isso que ela roda no path_info CRU, antes de
    # tudo — e por isso o /{idioma}/healthz do teste acima jamais poderia ter
    # esta garantia: para chegar até ele, o middleware já precisou resolver o
    # Host no catálogo. Rota de máquina com dependência a mais é rota de
    # máquina pior; mais uma razão para ela não existir.
    rede.get(f"{CATALOGO}/sites/by-host/{HOST_MESH}").mock(side_effect=OSError)
    resp = client.get("/healthz", HTTP_HOST=HOST_MESH)
    assert resp.status_code == 200


# --- o cadeado da CLASSE, não só do caso ------------------------------------
# O 200 do /pt-br/healthz não foi desatenção de quem escreveu o middleware: foi
# uma rota de máquina que o funil servia sem estar em NENHUMA das duas listas, e
# nada avisava. A guarda do middleware cura aquele caso; esta cura a classe —
# rota nova no urlconf entra numa das listas ou aqui, de propósito e por
# escrito. (RETROSPECTIVA-FASE-D: o catálogo cura o caso, só o padrão cura a
# classe.)
# `/login` é de PÁGINA: serve em /{idioma}/login, com marca e texto traduzido
# (DECISAO-onde-mora-a-sessao). Não é de máquina — apesar de o nome parecer
# infraestrutura, quem a abre é uma pessoa, e ela precisa existir nos três
# idiomas como qualquer outra página do site.
ROTAS_LOCALIZAVEIS = ("/", "/leads", "/cadastro", "/login")

# Um urlconf tem `path()` e `re_path()`, e o guarda precisa comparar os dois com
# as listas do middleware — que casam por `startswith` sobre prefixo LITERAL.
RE_METACARACTERE = re.compile(r"[(\[\?*+{<$]")


def caminho_literal(padrao) -> str:
    """O prefixo literal da rota, com a barra da raiz.

    `path("healthz", …)` → `/healthz`;
    `re_path(r"^static/(?P<path>.*)$", …)` → `/static/`.

    Cortar no primeiro metacaractere não é aproximação: é exatamente o pedaço do
    caminho que decide a isenção no middleware, porque é sobre ele que o
    `startswith` de `ROTAS_DE_MAQUINA` roda.
    """
    bruto = str(padrao.pattern).lstrip("^")
    return "/" + RE_METACARACTERE.split(bruto, maxsplit=1)[0]


@pytest.mark.parametrize(
    "padrao, esperado",
    [
        (path("healthz", _view), "/healthz"),
        (path("sitemap.xml", _view), "/sitemap.xml"),
        (path("", _view), "/"),  # catch-all da landing
        (re_path(r"^static/(?P<path>.*)$", _view), "/static/"),
        (path("cursos/<slug:slug>/", _view), "/cursos/"),
    ],
)
def test_o_caminho_literal_e_o_pedaco_que_o_middleware_compara(padrao, esperado):
    # Sem esta prova o guarda abaixo poderia ficar verde lendo lixo: um
    # `re_path` cru vira "/^static/(?P<path>.*)$", que não casa lista nenhuma.
    assert caminho_literal(padrao) == esperado


def test_toda_rota_do_urlconf_e_classificada_maquina_ou_localizavel():
    caminhos = [caminho_literal(padrao) for padrao in urlpatterns]

    sem_classificacao = [
        caminho
        for caminho in caminhos
        if caminho not in ROTAS_LOCALIZAVEIS
        and not caminho.startswith(ROTAS_DE_MAQUINA)
    ]
    assert sem_classificacao == [], (
        f"Rota nova no urlconf sem classificação: {sem_classificacao}.\n"
        "Toda rota do funil é uma das duas coisas, e a escolha é sua:\n"
        "  · de MÁQUINA (nunca se localiza) — entre com ela em CAMINHOS_SEM_SITE "
        "se não pode depender do catálogo, ou em CAMINHOS_DE_MAQUINA se precisa "
        "do Site; as duas ficam em apps/core/middleware.py.\n"
        "  · de PÁGINA (serve sob /{idioma}/…) — entre com ela em "
        "ROTAS_LOCALIZAVEIS, aqui.\n"
        "Rota de máquina esquecida fora das listas ganha versão localizada em "
        "silêncio: foi exatamente assim que /pt-br/healthz respondeu 200 até "
        "24/08/2026."
    )

    # A lista não pode apodrecer: rota que sai do urlconf sai daqui também,
    # senão o guarda segue verde vigiando uma rota que não existe mais.
    fantasmas = sorted(set(ROTAS_LOCALIZAVEIS) - set(caminhos))
    assert fantasmas == [], f"ROTAS_LOCALIZAVEIS cita rota inexistente: {fantasmas}"


# ===========================================================================
# GUARDA 3 — link cross-célula não leva prefixo de idioma, e é deliberado.
# ===========================================================================
# O scanner define "minha rota" pelo urlconf do PRÓPRIO funil, em vez de
# repetir aqui a lista de prefixos de célula do Traefik (que a célula não pode
# ler, e que já é vigiada pelo guarda 1). Regra: link interno que carrega
# prefixo de idioma TEM de resolver no funil depois de decapado. Se não
# resolve, é link para outra célula — e prefixo ali é o "conserto" que o D6
# manda impedir.
ASPAS = re.compile(r'"([^"\s]+)"')


def caminhos_internos(html: str, host: str) -> list[str]:
    """Todo caminho interno citado na página — atributos E strings de JS.

    Varrer strings entre aspas (em vez de só href/action) é deliberado: o
    action da ilha Alpine é uma string dentro de `api.post(...)`, e um link
    novo pode nascer em qualquer dos dois lugares.
    """
    encontrados = []
    for bruto in ASPAS.findall(html):
        partes = urlsplit(bruto)
        if partes.scheme or partes.netloc:
            if partes.netloc != host:  # CDN do Alpine e afins não são nossos
                continue
        elif not bruto.startswith("/"):
            continue
        if partes.path.startswith("/"):
            encontrados.append(partes.path)
    return encontrados


def links_cross_celula_com_prefixo(html: str, host: str) -> list[str]:
    """Links que ganharam prefixo de idioma sem serem rota do funil."""
    fora = []
    for caminho in caminhos_internos(html, host):
        segmento, _, resto = caminho[1:].partition("/")
        if segmento not in IDIOMAS:
            continue  # sem prefixo: é o contrato de hoje, nada a julgar
        try:
            resolve(f"/{resto}")
        except Resolver404:
            fora.append(caminho)
    return fora


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_nenhum_link_cross_celula_leva_prefixo_de_idioma(client, rede, idioma):
    conteudo = client.get(f"/{idioma}/", HTTP_HOST=HOST_MESH).content.decode()
    fora = links_cross_celula_com_prefixo(conteudo, HOST_MESH)
    assert fora == [], (
        f"Link com prefixo de idioma apontando para fora do funil: {fora}.\n"
        "Isto NÃO é bug para consertar: enquanto a fase 5 do D6 estiver "
        "congelada, o gateway não casa /{idioma}/<celula> e o link morre 404 "
        "(prova em test_url_de_outra_celula_com_prefixo_morre_404). Se você "
        "está ATIVANDO a fase 5, descongele-a no PLANO-I18N.md e reescreva "
        "este guarda — a hora chegou."
    )


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_o_link_do_checkout_e_exatamente_o_caminho_nu(client, rede, idioma):
    # Metade "não é vazio" do teste acima: se a landing deixasse de linkar para
    # outra célula, o scanner ficaria verde por não ter o que varrer.
    conteudo = client.get(f"/{idioma}/", HTTP_HOST=HOST_MESH).content.decode()
    assert f'href="/checkout/{OFERTA_MESH["slug"]}/"' in conteudo
    assert f'href="/{idioma}/checkout/' not in conteudo


def test_url_de_outra_celula_com_prefixo_morre_404(client, rede):
    """Os DENTES do guarda 3: por que o link nu é contrato, não desleixo.

    No gateway real, `PathPrefix('/checkout')` casa prefixo de string CRU a
    partir da posição 0 — `/pt-br/checkout/...` NÃO casa, nem a rota da célula
    checkout (priority 10) nem a `/api/checkout` (priority 20). Sobra o
    catch-all do funil (priority 1), que é o que este teste exercita: 404 na
    cara de quem clicou. Prefixar o link cross-célula hoje quebra a compra.
    """
    prefixada = f"/pt-br/checkout/{OFERTA_MESH['slug']}/"
    assert client.get(prefixada, HTTP_HOST=HOST_MESH).status_code == 404


# --- prova adversarial do próprio scanner (guarda que não fica vermelho quando
# --- deveria é decoração) ---------------------------------------------------
def test_o_scanner_pega_o_conserto_bem_intencionado():
    html = '<a class="cta" href="/pt-br/checkout/curso-teste/">Comprar</a>'
    assert links_cross_celula_com_prefixo(html, HOST_MESH) == [
        "/pt-br/checkout/curso-teste/"
    ]


def test_o_scanner_pega_o_link_prefixado_escondido_em_javascript():
    # Célula `alunos`, que o funil nunca serve — o caminho não pode virar rota
    # do funil por acidente e desarmar a prova.
    html = 'fetch("/es/alunos/painel/matriculas");'
    assert links_cross_celula_com_prefixo(html, HOST_MESH) == [
        "/es/alunos/painel/matriculas"
    ]


def test_o_scanner_aprova_o_contrato_de_hoje():
    html = (
        '<a href="/checkout/curso-teste/">comprar</a>'  # outra célula, nu: OK
        '<form action="/pt-br/cadastro">'  # rota do funil, prefixada: OK
        '<script src="/static/funil/api.js"></script>'  # máquina, nu: OK
        f'<a href="https://{HOST_MESH}/es/">es</a>'  # seletor absoluto: OK
        '<script src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/x.js"></script>'
    )
    assert links_cross_celula_com_prefixo(html, HOST_MESH) == []


def test_o_scanner_enxerga_a_pagina_de_verdade(client, rede):
    # Instrumentação: sem isto, um scanner que devolvesse [] por não achar
    # NADA passaria como "página limpa" (INV-CI01 na escala de um teste).
    conteudo = client.get("/pt-br/", HTTP_HOST=HOST_MESH).content.decode()
    caminhos = caminhos_internos(conteudo, HOST_MESH)
    assert f"/checkout/{OFERTA_MESH['slug']}/" in caminhos  # link cross-célula
    assert "/pt-br/leads" in caminhos  # rota do funil, prefixada
    assert f"/{IDIOMAS[0]}/" in caminhos  # seletor de idioma (absoluto)
