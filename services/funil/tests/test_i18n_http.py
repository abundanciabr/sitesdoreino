"""Fase 1 do PLANO-I18N — matriz HTTP do resolver (D1), emissão SEO (D5),
pseudo-locale (D8.4) e REGRESSÃO MONOLÍNGUE (site fora do registro: bytes
idênticos ao comportamento de antes desta fase).

Todos os hosts são de teste; nenhum site real está registrado em
sites_i18n.yaml nesta fase — o registro dos testes entra por monkeypatch."""

from types import MappingProxyType

import httpx
import pytest
from django.http import HttpResponse
from django.template import engines
from django.test import RequestFactory
from django.utils import translation

from apps.core.middleware import SiteResolutionMiddleware
from apps.i18n import catalogo as catalogo_mod
from apps.i18n import registro as registro_mod
from apps.i18n.validador import pseudo_do_catalogo, texto_hardcoded
from tests.conftest import CATALOGO, HOST_A, OFERTA_A, SITE_A

HOST_PREVIEW = "preview.exemplo.com"  # resolve para o MESMO Site A (host canônico)

IDIOMAS_TESTE = {
    "en": {"tag": "en", "dir": "ltr", "indexavel": True},
    "pt-br": {"tag": "pt-BR", "dir": "ltr", "indexavel": True},
    "es": {"tag": "es", "dir": "ltr", "indexavel": False},  # D5: es nasce noindex
}
CFG_I18N = {
    "i18n_mode": "prefixed",
    "default": "en",
    "idiomas": IDIOMAS_TESTE,
    "glossario": ("Meshcraft",),
}


@pytest.fixture
def com_i18n(monkeypatch):
    """HOST_A vira site multilíngue registrado (fixture própria — o
    sites_i18n.yaml REAL fica vazio na fase 1, de propósito)."""
    monkeypatch.setattr(
        registro_mod,
        "_REGISTRO",
        MappingProxyType({HOST_A: CFG_I18N, HOST_PREVIEW: CFG_I18N}),
    )


# ---------------------------------------------------------------------------
# Matriz HTTP (D1) — toda ela vira teste.
# ---------------------------------------------------------------------------
def test_raiz_302_para_o_default_com_cache_control(client, rede, com_i18n):
    resp = client.get("/", HTTP_HOST=HOST_A)
    assert resp.status_code == 302  # nunca 301: 301 cacheado travaria a troca
    assert resp["Location"] == "/en/"
    assert resp["Cache-Control"] == "max-age=300"


def test_raiz_preserva_query_string(client, rede, com_i18n):
    resp = client.get("/?utm_source=ig&utm_medium=cpc", HTTP_HOST=HOST_A)
    assert resp.status_code == 302
    assert resp["Location"] == "/en/?utm_source=ig&utm_medium=cpc"


def test_raiz_head_tambem_redireciona(client, rede, com_i18n):
    resp = client.head("/", HTTP_HOST=HOST_A)
    assert resp.status_code == 302


def test_raiz_metodo_nao_seguro_e_404(client, rede, com_i18n):
    resp = client.post("/", {}, HTTP_HOST=HOST_A)
    assert resp.status_code == 404


def test_caminho_nu_redireciona_preservando_query(client, rede, com_i18n):
    resp = client.get("/cadastro?ref=email", HTTP_HOST=HOST_A)
    assert resp.status_code == 302
    assert resp["Location"] == "/en/cadastro?ref=email"
    assert resp["Cache-Control"] == "max-age=300"


def test_caminho_nu_nao_get_e_404(client, rede, com_i18n):
    # 301/302 converteriam POST em GET e descartariam o corpo em silêncio (D1).
    resp = client.post("/cadastro", {}, HTTP_HOST=HOST_A)
    assert resp.status_code == 404


def test_post_leads_em_site_registrado_e_404_pela_matriz(client, rede, com_i18n):
    # Consequência documentada da matriz: /leads é caminho nu não-GET ⇒ 404.
    # A fase 2 (página de cadastro) decide o canal de POST do site registrado;
    # em site NÃO registrado o /leads segue funcionando (regressão abaixo).
    resp = client.post(
        "/leads", '{"email": "a@b.c"}', "application/json", HTTP_HOST=HOST_A
    )
    assert resp.status_code == 404


@pytest.mark.parametrize("prefixo", ["pt-BR", "PT-BR", "pt_br", "EN", "Es"])
def test_caixa_ou_forma_nao_minuscula_e_404(client, rede, com_i18n, prefixo):
    resp = client.get(f"/{prefixo}/", HTTP_HOST=HOST_A)
    assert resp.status_code == 404  # fail-closed: nada nunca linkou essas formas


@pytest.mark.parametrize("caminho", ["/fr/cadastro", "/de/", "/pt/"])
def test_prefixo_com_forma_de_idioma_nao_habilitado_e_404(
    client, rede, com_i18n, caminho
):
    resp = client.get(caminho, HTTP_HOST=HOST_A)
    assert resp.status_code == 404


@pytest.mark.parametrize("idioma", ["en", "pt-br", "es"])
def test_prefixo_habilitado_serve_a_pagina(client, rede, com_i18n, idioma):
    resp = client.get(f"/{idioma}/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    assert OFERTA_A["product"]["name"].encode() in resp.content


def test_prefixo_sem_barra_redireciona_para_a_forma_canonica(client, rede, com_i18n):
    resp = client.get("/en", HTTP_HOST=HOST_A)
    assert resp.status_code == 302
    assert resp["Location"] == "/en/"


def test_uma_url_um_idioma_bytes_identicos(client, rede, com_i18n):
    # Invariante D1: Accept-Language NUNCA muda o conteúdo de uma URL fixa.
    a = client.get("/en/", HTTP_HOST=HOST_A, HTTP_ACCEPT_LANGUAGE="pt-BR,pt;q=0.9")
    b = client.get("/en/", HTTP_HOST=HOST_A, HTTP_ACCEPT_LANGUAGE="en")
    assert a.status_code == b.status_code == 200
    assert a.content == b.content
    assert "accept-language" not in a.get("Vary", "").lower()


def test_resolver_ativa_traducao_decapa_prefixo_e_expoe_idioma(rede, com_i18n):
    capturado = {}

    def espiao(request):
        capturado["idioma"] = request.idioma
        capturado["path_info"] = request.path_info
        capturado["lang_ativo"] = translation.get_language()
        return HttpResponse("ok")

    middleware = SiteResolutionMiddleware(espiao)
    request = RequestFactory().get("/pt-br/cadastro", HTTP_HOST=HOST_A)
    middleware(request)
    assert capturado == {
        "idioma": "pt-br",
        "path_info": "/cadastro",
        "lang_ativo": "pt-br",
    }
    # fora da requisição, o idioma ativado não vaza para a thread
    assert translation.get_language() != "pt-br"


# ---------------------------------------------------------------------------
# Emissão SEO (D5) — tudo gerado do registro, nunca à mão.
# ---------------------------------------------------------------------------
def test_html_lang_dir_e_og_locale_da_pagina(client, rede, com_i18n):
    conteudo = client.get("/pt-br/", HTTP_HOST=HOST_A).content.decode()
    assert '<html lang="pt-BR" dir="ltr">' in conteudo
    assert '<meta property="og:locale" content="pt_BR">' in conteudo
    assert '<meta property="og:locale:alternate" content="en">' in conteudo


def test_canonical_auto_referente_nunca_cruzado(client, rede, com_i18n):
    # Anti-padrão reprovado: canonical de /pt-br/* apontando pra versão inglesa.
    conteudo = client.get("/pt-br/", HTTP_HOST=HOST_A).content.decode()
    assert f'<link rel="canonical" href="https://{HOST_A}/pt-br/">' in conteudo
    assert f'<link rel="canonical" href="https://{HOST_A}/en/">' not in conteudo


def test_hreflang_reciproco_so_de_idioma_indexavel_e_um_x_default(
    client, rede, com_i18n
):
    conteudo = client.get("/pt-br/", HTTP_HOST=HOST_A).content.decode()
    assert (
        f'<link rel="alternate" hreflang="en" href="https://{HOST_A}/en/">' in conteudo
    )
    assert (
        f'<link rel="alternate" hreflang="pt-BR" href="https://{HOST_A}/pt-br/">'
        in conteudo
    )
    # es é noindex ⇒ fora do hreflang (o SELETOR <a> continua listando es —
    # seletor é para gente, hreflang é para robô).
    assert '<link rel="alternate" hreflang="es"' not in conteudo
    assert conteudo.count('hreflang="x-default"') == 1
    assert (
        f'hreflang="x-default" href="https://{HOST_A}/en/"' in conteudo
    )  # x-default da MESMA página, no idioma padrão


def test_es_noindex_emite_robots_e_pt_br_nao(client, rede, com_i18n):
    es = client.get("/es/", HTTP_HOST=HOST_A).content.decode()
    ptbr = client.get("/pt-br/", HTTP_HOST=HOST_A).content.decode()
    assert '<meta name="robots" content="noindex">' in es
    assert '<meta name="robots" content="noindex">' not in ptbr


def test_canonical_usa_o_host_canonico_do_site_nunca_o_da_requisicao(
    client, rede, com_i18n
):
    # Host de preview resolve para o MESMO Site A: o canonical/hreflang têm de
    # sair com o host canônico do Site — nunca request.get_host() (D5).
    rede.get(f"{CATALOGO}/sites/by-host/{HOST_PREVIEW}").mock(
        return_value=httpx.Response(200, json=SITE_A)
    )
    conteudo = client.get("/en/", HTTP_HOST=HOST_PREVIEW).content.decode()
    assert f'<link rel="canonical" href="https://{HOST_A}/en/">' in conteudo
    assert HOST_PREVIEW not in conteudo


def test_toda_url_do_hreflang_aparece_como_ancora_real(client, rede, com_i18n):
    # D5: seletor de idioma é <a href> real — versão sem link rastreável pode
    # nunca ser descoberta. O seletor cobre TODOS os idiomas habilitados.
    conteudo = client.get("/en/", HTTP_HOST=HOST_A).content.decode()
    for codigo in IDIOMAS_TESTE:
        assert f'<a href="https://{HOST_A}/{codigo}/"' in conteudo


# ---------------------------------------------------------------------------
# Pseudo-locale (D8.4): texto visível sem a marca = string hardcoded.
# Vale para os templates que a fase 1 tocou (base_mobile.html).
# ---------------------------------------------------------------------------
def _render_pseudo(monkeypatch, bloco_conteudo: str) -> str:
    chaves = pseudo_do_catalogo(
        {"pagina.titulo": {"_fonte": "000000", "en": "Start building games"}}
    )
    monkeypatch.setattr(catalogo_mod, "_CATALOGO", MappingProxyType(chaves))
    monkeypatch.setattr(catalogo_mod, "_BASES", MappingProxyType({}))
    template = engines["django"].from_string(
        '{% extends "base_mobile.html" %}{% load t %}'
        "{% block conteudo %}" + bloco_conteudo + "{% endblock %}"
    )
    request = RequestFactory().get("/qps/", HTTP_HOST=HOST_A)
    request.idioma = "qps"  # como o resolver deixaria
    return template.render({"site": SITE_A}, request=request)


def test_pseudo_locale_nao_deixa_texto_visivel_sem_marca(monkeypatch):
    html = _render_pseudo(monkeypatch, '<h1>{% t "pagina.titulo" %}</h1><p>123</p>')
    assert texto_hardcoded(html) == []


def test_pseudo_locale_detecta_string_hardcoded(monkeypatch):
    html = _render_pseudo(
        monkeypatch, '<h1>{% t "pagina.titulo" %}</h1><p>Texto cru esquecido</p>'
    )
    assert "Texto cru esquecido" in texto_hardcoded(html)


# ---------------------------------------------------------------------------
# REGRESSÃO MONOLÍNGUE — host fora do registro: NADA muda (nem um byte).
# ---------------------------------------------------------------------------
HTML_DE_HOJE = """<!-- templates/base_mobile.html  [RECEITA:R6 v1] -->
<!-- O viewport abaixo é contrato, não decoração: test_mobile_first_contract.py
     verifica esta tag em toda página que estende este arquivo. Não troque por
     um viewport de largura fixa. -->
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Curso Esqueleto — Site A</title>
  <script src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; font-family: system-ui, sans-serif; background: #f7f7f8; color: #1a1a1a; }
    .wrap { width: 100%; max-width: 32rem; margin: 0 auto; padding: 1rem; }
    .card { background: #fff; border-radius: .75rem; padding: 1rem; margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
    
    .preco { font-size: 1.5rem; font-weight: 700; }
    .cta { display: block; width: 100%; padding: 1rem; border: 0; border-radius: .5rem; background: #16a34a; color: #fff; font-size: 1.1rem; font-weight: 600; text-align: center; text-decoration: none; }
    .cta[aria-disabled=true] { opacity: .5; pointer-events: none; }
    input[type=text], input[type=email], input[type=tel] { width: 100%; padding: .75rem; border: 1px solid #ccc; border-radius: .5rem; font-size: 1rem; margin-bottom: .5rem; }
    .msg { font-size: .875rem; margin-top: .5rem; }
    .erro { color: #b91c1c; }
    .sucesso { color: #16a34a; }

  </style>
  
</head>
<body>
  <div class="wrap">
    
<script id="utm-data" type="application/json">{}</script>
<div class="card">
  <h1>Curso Esqueleto</h1>
  <p class="preco">R$ 99,00</p>
  <a class="cta" href="/checkout/curso-esqueleto/">Quero comprar</a>
</div>

<div class="card" x-data="capturaIsland()" x-init="init()">
  <h2>Receba novidades</h2>
  <form @submit.prevent="enviar">
    <input type="text" placeholder="Nome" x-model="name">
    <input type="email" placeholder="E-mail" x-model="email" required>
    <input type="tel" placeholder="WhatsApp (opcional)" x-model="phone">
    <button class="cta" type="submit" :aria-disabled="enviando ? 'true' : 'false'" :disabled="enviando">
      <span x-text="enviando ? 'Enviando…' : 'Quero receber'"></span>
    </button>
    <p class="msg sucesso" x-show="sucesso">Recebido! Em breve entramos em contato.</p>
    <p class="msg erro" x-show="erro" x-text="erro"></p>
  </form>
</div>

  </div>
  
<script src="/static/funil/api.js"></script>
<script>
function capturaIsland() {
  return {
    name: "", email: "", phone: "",
    enviando: false, sucesso: false, erro: "",
    utm: {},
    init() { this.utm = JSON.parse(document.getElementById("utm-data").textContent); },
    async enviar() {
      this.enviando = true; this.erro = ""; this.sucesso = false;
      try {
        await api.post("/leads", {
          name: this.name, email: this.email, phone: this.phone,
          source: "lp-funil", utm: this.utm,
        });
        this.sucesso = true;
      } catch (e) {
        this.erro = "Não foi possível enviar. Tente de novo.";
      } finally {
        this.enviando = false;
      }
    },
  };
}
</script>

</body>
</html>
"""


def test_regressao_site_nao_registrado_landing_byte_identica(client, rede):
    # Capturado do código ANTERIOR a esta fase (baseline verde do despacho).
    # Se este teste quebrar por mudança LEGÍTIMA de layout, recapture o HTML
    # renderizado da landing de teste e atualize a constante — nunca o afrouxe.
    resp = client.get("/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    assert resp.content.decode("utf-8") == HTML_DE_HOJE


def test_regressao_healthz_intocado(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_regressao_leads_de_site_nao_registrado_segue_funcionando(client, rede):
    resp = client.post(
        "/leads",
        '{"email": "aluno@exemplo.com"}',
        "application/json",
        HTTP_HOST=HOST_A,
    )
    assert resp.status_code == 200
    assert resp.json()["created"] is True
