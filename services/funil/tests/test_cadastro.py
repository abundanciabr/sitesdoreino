"""Fase 2 do PLANO-I18N — página de cadastro do meshcraft nos 3 idiomas.

Os 3 idiomas vêm do CATÁLOGO (fase 4: `conftest.SITE_MESH`, no formato do
contrato) — nada aqui monkeypatcha idioma. O catálogo (célula) e a leads
entram só como contrato mockado (respx), com Host válido (ARMADILHAS §4.6) e
filtro por endpoint nas asserções de chamada (LICOES: o CONV-SITE sempre bate
no catálogo)."""

import json
from types import MappingProxyType

import httpx
import pytest
from django.template.loader import get_template
from django.test import RequestFactory
from django.utils.html import escape
from django.utils.translation import gettext, override

from apps.core.views import FormularioDeCadastro
from apps.i18n import catalogo as cat
from apps.i18n.catalogo import t
from apps.i18n.validador import pseudo_do_catalogo, texto_hardcoded
from tests.conftest import HOST_MESH, SITE_MESH, caminho_mesh

IDIOMAS = ("en", "pt-br", "es")
TAGS = {"en": "en", "pt-br": "pt-BR", "es": "es"}


def _chamadas_a_leads(rede):
    # LICOES: nunca "nenhuma chamada de rede" — o CONV-SITE sempre resolve o
    # site no catálogo; o que se afirma é sobre o ENDPOINT /leads.
    return [c for c in rede.calls if "/leads" in str(c.request.url)]


# ---------------------------------------------------------------------------
# Render nos 3 idiomas: title/meta/og e h1 no idioma certo, action prefixado.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_pagina_nos_3_idiomas_title_meta_e_action(client, rede, idioma):
    resp = client.get(caminho_mesh(idioma, "/cadastro"), HTTP_HOST=HOST_MESH)
    assert resp.status_code == 200
    conteudo = resp.content.decode()
    assert f'<html lang="{TAGS[idioma]}" dir="ltr">' in conteudo
    assert f"<title>{escape(t('cadastro.titulo', idioma))}</title>" in conteudo
    assert (
        f'<meta name="description" content="{escape(t("cadastro.meta_descricao", idioma))}">'
        in conteudo
    )
    assert (
        f'<meta property="og:title" content="{escape(t("cadastro.titulo", idioma))}">'
        in conteudo
    )
    assert f"<h1>{escape(t('cadastro.titulo_pagina', idioma))}</h1>" in conteudo
    # O form posta para a PRÓPRIA URL prefixada ({% url_i18n %}) — decisão da
    # maestro sobre a pendência 1 do PR #87.
    # O form posta para a PRÓPRIA URL pública da página — nua em inglês,
    # prefixada nos outros. É o {% url_i18n %} do template, e a asserção sai do
    # mesmo caminho_publico que ele usa.
    assert f'action="{caminho_mesh(idioma, "/cadastro")}"' in conteudo


# ---------------------------------------------------------------------------
# POST prefixado feliz: lead sai server-side com o idioma no source (D9).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_post_feliz_grava_lead_com_idioma_no_source(client, rede, idioma):
    resp = client.post(
        caminho_mesh(idioma, "/cadastro"),
        {
            "name": "Aluno Teste",
            "email": "aluno@exemplo.com",
            "phone": "+5511900000000",
        },
        HTTP_HOST=HOST_MESH,
    )
    assert resp.status_code == 200
    assert escape(t("cadastro.sucesso", idioma)) in resp.content.decode()

    chamadas = _chamadas_a_leads(rede)
    assert len(chamadas) == 1
    enviado = json.loads(chamadas[0].request.content)
    assert enviado["site_id"] == SITE_MESH["id"]  # [INV-P11] do Host, não do payload
    assert enviado["source"] == f"cadastro-meshcraft-{idioma}"
    assert enviado["email"] == "aluno@exemplo.com"
    assert enviado["name"] == "Aluno Teste"
    assert enviado["phone"] == "+5511900000000"


# ---------------------------------------------------------------------------
# POST com erro de validação: mensagem do Django NO IDIOMA da página (o
# activate() da fase 1), e nenhum lead sai.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_post_sem_email_erro_localizado_e_nenhum_lead(client, rede, idioma):
    resp = client.post(
        caminho_mesh(idioma, "/cadastro"), {"name": "Sem E-mail"}, HTTP_HOST=HOST_MESH
    )
    assert resp.status_code == 200
    with override(TAGS[idioma]):
        esperado = gettext("This field is required.")
    assert escape(esperado) in resp.content.decode()
    assert _chamadas_a_leads(rede) == []


def test_post_email_invalido_erro_localizado_em_es(client, rede):
    resp = client.post(
        "/es/cadastro",
        {"name": "Aluno", "email": "isto-nao-e-email"},
        HTTP_HOST=HOST_MESH,
    )
    assert resp.status_code == 200
    with override("es"):
        esperado = gettext("Enter a valid email address.")
    assert escape(esperado) in resp.content.decode()
    assert _chamadas_a_leads(rede) == []


# ---------------------------------------------------------------------------
# Leads fora do ar: 502 honesto (ARMADILHAS §4.9), mensagem localizada, e o
# que a pessoa digitou continua no formulário.
# ---------------------------------------------------------------------------
def test_leads_fora_do_ar_e_502_localizado_preservando_o_form(client, rede):
    rede["upsert_lead"].mock(return_value=httpx.Response(500))
    resp = client.post(
        "/pt-br/cadastro",
        {"name": "Aluno Teste", "email": "aluno@exemplo.com"},
        HTTP_HOST=HOST_MESH,
    )
    assert resp.status_code == 502
    conteudo = resp.content.decode()
    assert escape(t("cadastro.erro_envio", "pt-br")) in conteudo
    assert 'value="aluno@exemplo.com"' in conteudo


# ---------------------------------------------------------------------------
# es noindex de fato (entrega 7): 200 + robots noindex + fora do hreflang.
# ---------------------------------------------------------------------------
def test_es_cadastro_serve_200_noindex_e_fora_do_hreflang(client, rede):
    conteudo = client.get("/es/cadastro", HTTP_HOST=HOST_MESH).content.decode()
    assert '<meta name="robots" content="noindex">' in conteudo
    # Fora do hreflang de ROBÔ (tag <link>); o seletor <a> continua listando
    # es — seletor é para gente, hreflang é para robô (fase 1).
    assert '<link rel="alternate" hreflang="es"' not in conteudo
    ptbr = client.get("/pt-br/cadastro", HTTP_HOST=HOST_MESH).content.decode()
    assert '<meta name="robots" content="noindex">' not in ptbr
    assert f'hreflang="pt-BR" href="https://{HOST_MESH}/pt-br/cadastro"' in ptbr


# ---------------------------------------------------------------------------
# Pseudo-locale (D8.4) nos DOIS templates novos: nenhum texto visível fora do
# catálogo. Dados de contexto (nome de produto, preço) entram como dígitos —
# são DADO, não copy; o detector deve enxergar só o template.
# ---------------------------------------------------------------------------
@pytest.fixture
def catalogo_pseudo(monkeypatch):
    chaves = pseudo_do_catalogo(dict(cat.catalogo_instalado()))
    monkeypatch.setattr(cat, "_CATALOGO", MappingProxyType(chaves))


def _request_pseudo(caminho):
    request = RequestFactory().get(caminho, HTTP_HOST=HOST_MESH)
    request.idioma = "qps"
    return request


def test_pseudo_locale_cadastro_sem_texto_hardcoded(catalogo_pseudo):
    html = get_template("funil/cadastro.html").render(
        {"form": FormularioDeCadastro(), "sucesso": True, "erro_envio": True},
        request=_request_pseudo("/qps/cadastro"),
    )
    assert texto_hardcoded(html) == []


class _AtorFalso:
    """Alguém entrou — o mínimo que a home e o cabeçalho de sessão leem.

    `nome` em dígitos pela mesma convenção do resto deste bloco: o detector
    procura LETRAS visíveis fora do catálogo, e nome de pessoa é DADO, não
    copy. `avisos_nao_lidos = None` é o "não sei" que apaga o sino — o sino
    tem os guardas dele em tests/test_sino.py.
    """

    nome = "123"
    avisos_nao_lidos = None


def test_pseudo_locale_home_de_visitante_sem_texto_hardcoded(catalogo_pseudo):
    html = get_template("funil/landing_i18n.html").render(
        {}, request=_request_pseudo("/qps/")
    )
    assert texto_hardcoded(html) == []


def test_pseudo_locale_home_de_quem_entrou_sem_texto_hardcoded(catalogo_pseudo):
    """O OUTRO ramo da home — o que a versão anterior deste teste não tinha.

    Enquanto a raiz era vitrine, ela mostrava a mesma página para todo mundo e
    um render só a cobria inteira. Desde 27/08/2026 ela tem dois ramos, e o de
    quem entrou é justamente o que ganhou texto novo (o aviso de novidade, o
    rótulo da Caixa). Um pseudo-locale que só varresse o ramo do visitante
    ficaria verde com uma string cravada no ramo de dentro.
    """
    pedido = _request_pseudo("/qps/")
    pedido.ator = _AtorFalso()
    pedido.url_da_caixa = "/forms/sugestoes/"

    html = get_template("funil/landing_i18n.html").render({}, request=pedido)

    assert texto_hardcoded(html) == []
