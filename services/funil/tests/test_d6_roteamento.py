"""O roteamento de idioma além do funil, medido por requisição.

  Rotas de MÁQUINA nunca se localizam (`/api/**`, `/webhooks/**`,
  `/static/**`, `/healthz`, `/sitemap.xml`).
  Link para OUTRA célula sai SEM prefixo de idioma, e isso é deliberado:
  prefixá-lo hoje produz 404 (a prova está aqui embaixo).
"""

import re
from urllib.parse import urlsplit

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import Resolver404, resolve

from apps.core.middleware import SiteResolutionMiddleware
from apps.core.enderecos import CAIXA_PADRAO as CAIXA

# `logado` e `COOKIE` moram no arquivo que os define — mesma importação que
# tests/test_sino.py já faz. O guarda 3 mede a página de QUEM ENTROU desde
# 27/08/2026: é ela que carrega os links para fora do funil (a Caixa, o sino,
# o "Sair"). A home de visitante não linka célula nenhuma, e varrê-la deixaria
# o scanner sem nada para julgar.
from test_sessao_no_site import COOKIE, logado  # noqa: F401  (fixture)
from tests.conftest import (
    CATALOGO,
    HOST_MESH,
    IDIOMAS_MESH,
    caminho_mesh,
)

IDIOMAS = tuple(idioma["code"] for idioma in IDIOMAS_MESH)


def _view(request):  # dublê: path()/re_path() exigem um callable
    return HttpResponse("ok")


# ===========================================================================
# GUARDA 2 — rotas de máquina nunca se localizam.
# ===========================================================================


@pytest.mark.parametrize(
    "caminho", ["/healthz", "/static/funil/api.js", "/google0e78b54775677e95.html"]
)
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
        # /google0e78b54775677e95.html — a verificação do Google, mesma regra
        "/pt-br/google0e78b54775677e95.html",
        "/en/google0e78b54775677e95.html",
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


# --- HEAD é método SEGURO: toda página pública responde aos dois -------------
# Descoberto medindo produção em 25/08/2026, logo depois de o inglês passar a
# ser servido na raiz nua. Enquanto a raiz era um redirecionamento, nenhuma
# requisição HEAD chegava às views e o 405 ficava escondido — `require_GET` e
# `require_http_methods(["GET", "POST"])` recusam HEAD, e nenhum dos dois avisa.
# Quem faz HEAD numa página pública: monitor de uptime, pré-visualizador de link
# (WhatsApp, Telegram, Slack) e robô de busca. As páginas do sitemap são
# exatamente as que mais recebem.
@pytest.mark.parametrize("pagina", ["/", "/cadastro", "/login"])
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_head_responde_como_get_em_toda_pagina_publica(client, rede, idioma, pagina):
    caminho = caminho_mesh(idioma, pagina)
    get = client.get(caminho, HTTP_HOST=HOST_MESH)
    head = client.head(caminho, HTTP_HOST=HOST_MESH)
    assert get.status_code == 200, caminho
    assert head.status_code == 200, (
        f"HEAD {caminho} devolveu {head.status_code} — método seguro recusado. "
        "Use @require_safe nas views de leitura; em @require_http_methods, "
        'inclua "HEAD" ao lado de "GET" (ele não vem de graça).'
    )


# ===========================================================================
# GUARDA 3 — link cross-célula não leva prefixo de idioma, e é deliberado.
# ===========================================================================
# O scanner define "minha rota" pelo urlconf do PRÓPRIO funil. Regra: link interno que carrega
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
def test_nenhum_link_cross_celula_leva_prefixo_de_idioma(client, logado, idioma):
    conteudo = client.get(
        caminho_mesh(idioma), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()
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
def test_o_link_da_caixa_e_exatamente_o_caminho_nu(client, aluno, idioma):
    # Metade "não é vazio" do teste acima: se a home deixasse de linkar para
    # outra célula, o scanner ficaria verde por não ter o que varrer.
    #
    # Era o link do checkout que segurava esta ponta até 27/08/2026, quando a
    # raiz do site virou porta e parou de vender. Quem a segura agora é a
    # Caixa — e a troca não afrouxou nada: o link continua sendo para OUTRA
    # célula, continua tendo de sair nu, e continua morrendo 404 se alguém o
    # "consertar" com prefixo (prova logo abaixo).
    conteudo = client.get(
        caminho_mesh(idioma), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()
    assert f'href="{CAIXA}"' in conteudo
    assert f'href="/{idioma}/forms/' not in conteudo


@pytest.mark.parametrize("nu", [CAIXA])
def test_url_de_outra_celula_com_prefixo_morre_404(client, rede, nu):
    """Os DENTES do guarda 3: por que o link nu é contrato, não desleixo.

    No gateway real, `PathPrefix('/forms/sugestoes')` casa prefixo de string
    CRU a partir da posição 0 — `/pt-br/forms/sugestoes/` NÃO casa a rota da
    Caixa (priority 10). Sobra o catch-all do funil (priority 1), que é o que
    este teste exercita: 404 na cara de quem clicou. Prefixar o link
    cross-célula hoje tira do ar o único caminho para a área logada.

    A porta da Caixa entra nesta prova. A tela de avisos agora pertence ao
    funil e, por isso, é uma rota interna localizada.
    """
    assert client.get(f"/pt-br{nu}", HTTP_HOST=HOST_MESH).status_code == 404


def test_o_scanner_enxerga_a_pagina_de_verdade(client, aluno):
    # Instrumentação: sem isto, um scanner que devolvesse [] por não achar
    # NADA passaria como "página limpa".
    conteudo = client.get(
        "/pt-br/", HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()
    caminhos = caminhos_internos(conteudo, HOST_MESH)
    assert CAIXA in caminhos  # link cross-célula
    assert "/entrar/sair" in caminhos  # outra célula ainda: a `identidade`
    # Rota do funil, prefixada: o seletor de idioma da própria página — a
    # prova de que o scanner não está cego para o lado que ele PODE reprovar.
    assert caminho_mesh("pt-br") in caminhos
    # Seletor de idioma (absoluto). No idioma PADRÃO ele aponta para a raiz
    # nua — é a mesma regra do canonical, e vem do mesmo caminho_publico.
    assert caminho_mesh(IDIOMAS[0]) in caminhos
