"""Matriz HTTP do resolver (D1), emissão SEO (D5), pseudo-locale (D8.4) e
REGRESSÃO MONOLÍNGUE (site sem idiomas: bytes idênticos ao comportamento de
antes do i18n).

Todos os hosts são de teste. Desde a FASE 4 o idioma é dado do SITE, servido
pelo catálogo: o site multilíngue destes testes nasce do mock do catálogo
(fixture `com_i18n`), no formato do contrato — nenhum arquivo local declara
idioma nesta célula."""

from types import MappingProxyType

import httpx
import pytest
from django.http import HttpResponse
from django.template import engines
from django.test import RequestFactory
from django.utils import translation

from apps.core.middleware import SiteResolutionMiddleware
from apps.i18n import catalogo as catalogo_mod
from apps.i18n.validador import pseudo_do_catalogo, texto_hardcoded
from apps.i18n.idiomas import caminho_publico, idiomas_do_site
from tests.conftest import CATALOGO, HOST_A, SITE_A

HOST_PREVIEW = "preview.exemplo.com"  # resolve para o MESMO Site A (host canônico)

IDIOMAS_TESTE = ("en", "pt-br", "es")
# Formato do contrato (`contracts/catalogo.openapi.yaml`, schema Site): o
# catálogo diz o CÓDIGO e o `indexable`; tag BCP 47 e dir a célula deriva.
SITE_A_MULTILINGUE = {
    **SITE_A,
    "default_language": "en",
    "languages": [
        {"code": "en", "indexable": True},
        {"code": "pt-br", "indexable": True},
        {"code": "es", "indexable": False},  # D5: es nasce noindex
    ],
}
# O caminho público de cada idioma vem do MESMO lugar que o código usa. Montar
# f"/{idioma}{caminho}" aqui faria os casos do idioma PADRÃO baterem em 404 —
# desde o D1 revisto (25/08/2026) o padrão mora na raiz nua.
CFG_A = idiomas_do_site(SITE_A_MULTILINGUE)


def caminho_de(idioma: str, caminho: str = "/") -> str:
    return caminho_publico(CFG_A, idioma, caminho)


def url_de(idioma: str, caminho: str = "/") -> str:
    return f"https://{HOST_A}{caminho_de(idioma, caminho)}"


@pytest.fixture
def com_i18n(rede):
    """HOST_A — e o host de preview, que resolve para o MESMO Site — passa a
    ser servido pelo catálogo COM idiomas. Sem esta fixture o SITE_A não tem
    `languages` e o site é monolíngue: é a regressão do fim do arquivo."""
    for host in (HOST_A, HOST_PREVIEW):
        rede.get(f"{CATALOGO}/sites/by-host/{host}").mock(
            return_value=httpx.Response(200, json=SITE_A_MULTILINGUE)
        )
    return rede


# ---------------------------------------------------------------------------
# Matriz HTTP (D1, REVISTO em 25/08/2026) — toda ela vira teste.
# O idioma PADRÃO mora na raiz nua; `/{padrão}/…` é 404; os outros idiomas
# seguem prefixados, exatamente como antes.
# ---------------------------------------------------------------------------
def test_raiz_serve_o_idioma_padrao_em_uma_requisicao(client, rede, com_i18n):
    resp = client.get("/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    assert b'<html lang="en"' in resp.content


def test_raiz_com_query_nao_perde_a_query_nem_redireciona(client, rede, com_i18n):
    """A query de campanha chega inteira à página, sem salto no meio — antes
    ela sobrevivia a um 302, agora não há 302 nenhum no caminho de maior
    volume de um funil de tráfego pago.

    O INSTRUMENTO mudou em 27/08/2026, o sentido não. Até então a prova era o
    eco da UTM no HTML (`{{ utm|json_script }}`), que a home nova não imprime:
    a raiz do site multilíngue deixou de ser vitrine e não monta mais link de
    checkout nenhum. Medir pelo eco amarrava um teste de ROTEAMENTO ao que a
    página escolhe mostrar; o espião abaixo mede a mesma coisa uma camada
    antes, e continua valendo no dia em que a home mudar de novo.
    """
    resp = client.get("/?utm_source=ig&utm_medium=cpc", HTTP_HOST=HOST_A)
    assert resp.status_code == 200

    chegou = {}

    def espiao(request):
        chegou["query"] = request.META.get("QUERY_STRING")
        chegou["path_info"] = request.path_info
        return HttpResponse("ok")

    pedido = RequestFactory().get(
        "/", {"utm_source": "ig", "utm_medium": "cpc"}, HTTP_HOST=HOST_A
    )
    SiteResolutionMiddleware(espiao)(pedido)

    assert chegou == {"query": "utm_source=ig&utm_medium=cpc", "path_info": "/"}


def test_raiz_head_serve(client, rede, com_i18n):
    assert client.head("/", HTTP_HOST=HOST_A).status_code == 200


def test_raiz_metodo_nao_seguro_chega_ao_urlconf(client, rede, com_i18n):
    # A matriz não recusa mais método nenhum: quem decide o que fazer com um
    # POST é a view (aqui o urlconf da landing, que só aceita GET) — não um
    # redirecionamento que engoliria o corpo antes de qualquer view ver.
    assert client.post("/", {}, HTTP_HOST=HOST_A).status_code == 405


def test_caminho_nu_serve_o_padrao_com_a_query_intacta(client, rede, com_i18n):
    resp = client.get("/cadastro?ref=email", HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    assert b'<html lang="en"' in resp.content


def test_post_no_caminho_nu_chega_a_view(client, rede, com_i18n):
    # Era 404 pela matriz antiga (302 converteria POST em GET e descartaria o
    # corpo). Sem redirecionamento no meio, o POST é o cadastro em inglês.
    assert client.post("/cadastro", {}, HTTP_HOST=HOST_A).status_code == 200


def test_post_leads_em_site_multilingue_funciona(client, rede, com_i18n):
    # A consequência mais estranha da matriz antiga morreu aqui: `POST /leads`
    # em site multilíngue respondia 404 por ser "caminho nu não-GET", enquanto
    # o MESMO POST funcionava em site monolíngue. Agora é só o /leads inglês.
    resp = client.post(
        "/leads", '{"email": "a@b.c"}', "application/json", HTTP_HOST=HOST_A
    )
    assert resp.status_code == 200
    assert resp.json()["created"] is True


@pytest.mark.parametrize("caminho", ["/en", "/en/", "/en/cadastro", "/en/login"])
def test_prefixo_do_idioma_padrao_e_404(client, rede, com_i18n, caminho):
    # Decisão do mantenedor (25/08/2026): `/en/…` não redireciona, deixa de
    # existir. Uma forma canônica por página, sem gêmea.
    assert client.get(caminho, HTTP_HOST=HOST_A).status_code == 404


@pytest.mark.parametrize("prefixo", ["pt-BR", "PT-BR", "pt_br", "EN", "Es"])
def test_caixa_ou_forma_nao_minuscula_e_404(client, rede, com_i18n, prefixo):
    resp = client.get(f"/{prefixo}/", HTTP_HOST=HOST_A)
    assert resp.status_code == 404  # fail-closed: nada nunca linkou essas formas


@pytest.mark.parametrize("caminho", ["/fr/cadastro", "/de/", "/pt/"])
def test_prefixo_de_idioma_nao_habilitado_e_404(client, rede, com_i18n, caminho):
    # Continua 404 — mas agora pelo urlconf (não há rota `fr/cadastro`), e não
    # por uma regex adivinhando que o segmento "tem cara de idioma". A
    # diferença é o que libera /faq e /api a existirem um dia.
    resp = client.get(caminho, HTTP_HOST=HOST_A)
    assert resp.status_code == 404


@pytest.mark.parametrize("idioma", ["en", "pt-br", "es"])
def test_cada_idioma_serve_a_pagina_no_seu_caminho(client, rede, com_i18n, idioma):
    resp = client.get(caminho_de(idioma), HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    conteudo = resp.content.decode()
    # A prova de que chegou a página CERTA NO IDIOMA certo. Era o nome do
    # produto (dado, igual nos três idiomas); desde 27/08/2026 a raiz é a home
    # e o que ela mostra a quem não entrou é o convite — que é copy, e portanto
    # DIFERE por idioma. Instrumento melhor que o antigo: um resolver que
    # servisse sempre o inglês passaria pelo nome do produto e reprova aqui.
    assert catalogo_mod.t("landing.entrar", idioma) in conteudo


def test_prefixo_sem_barra_redireciona_para_a_forma_canonica(client, rede, com_i18n):
    # Vale para os idiomas prefixados; o padrão não tem essa forma (404 acima).
    resp = client.get("/pt-br", HTTP_HOST=HOST_A)
    assert resp.status_code == 302
    assert resp["Location"] == "/pt-br/"
    assert resp["Cache-Control"] == "max-age=300"  # nunca 301


def test_prefixo_sem_barra_preserva_query(client, rede, com_i18n):
    resp = client.get("/pt-br?utm_source=ig", HTTP_HOST=HOST_A)
    assert resp["Location"] == "/pt-br/?utm_source=ig"


def test_uma_url_um_idioma_bytes_identicos(client, rede, com_i18n):
    # Invariante D1: Accept-Language NUNCA muda o conteúdo de uma URL fixa.
    # Medido na RAIZ, que é onde a tentação de negociar idioma sempre mora.
    a = client.get("/", HTTP_HOST=HOST_A, HTTP_ACCEPT_LANGUAGE="pt-BR,pt;q=0.9")
    b = client.get("/", HTTP_HOST=HOST_A, HTTP_ACCEPT_LANGUAGE="en")
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


def test_o_caminho_nu_ativa_o_idioma_padrao_sem_reescrever_o_path(rede, com_i18n):
    """O ramo do idioma padrão faz TUDO que o ramo prefixado faz — menos decapar.

    Este é o teste que pega a falha por omissão mais provável desta mudança: um
    ramo novo que serve a página mas esquece de ativar a tradução, ou de
    preparar quem-está-vendo. Ele afirma as três coisas de uma vez.
    """
    capturado = {}

    def espiao(request):
        capturado["idioma"] = request.idioma
        capturado["path_info"] = request.path_info
        capturado["lang_ativo"] = translation.get_language()
        capturado["tem_ator"] = getattr(request, "ator", None) is not None
        capturado["tem_seo"] = getattr(request, "i18n_seo", None) is not None
        return HttpResponse("ok")

    request = RequestFactory().get("/cadastro", HTTP_HOST=HOST_A)
    SiteResolutionMiddleware(espiao)(request)
    assert capturado == {
        "idioma": "en",
        "path_info": "/cadastro",  # NÃO reescrito: já é o que o urlconf resolve
        "lang_ativo": "en",
        "tem_ator": True,  # sem isto, o cabeçalho de sessão some só no inglês
        "tem_seo": True,
    }
    assert translation.get_language() != "en"


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
    assert f'<link rel="canonical" href="{url_de("pt-br")}">' in conteudo
    assert f'<link rel="canonical" href="{url_de("en")}">' not in conteudo


def test_canonical_do_idioma_padrao_e_a_raiz_nua(client, rede, com_i18n):
    # O que o Google lê no endereço principal do site. `/en/` aqui seria pior
    # que inútil: apontaria o canônico para uma URL que responde 404.
    conteudo = client.get("/", HTTP_HOST=HOST_A).content.decode()
    assert f'<link rel="canonical" href="https://{HOST_A}/">' in conteudo
    assert f"https://{HOST_A}/en/" not in conteudo


def test_hreflang_reciproco_so_de_idioma_indexavel_e_um_x_default(
    client, rede, com_i18n
):
    conteudo = client.get("/pt-br/", HTTP_HOST=HOST_A).content.decode()
    # O alternate do inglês aponta para a raiz nua — é a URL que existe.
    assert f'<link rel="alternate" hreflang="en" href="{url_de("en")}">' in conteudo
    assert (
        f'<link rel="alternate" hreflang="pt-BR" href="{url_de("pt-br")}">' in conteudo
    )
    # es é noindex ⇒ fora do hreflang (o SELETOR <a> continua listando es —
    # seletor é para gente, hreflang é para robô).
    assert '<link rel="alternate" hreflang="es"' not in conteudo
    assert conteudo.count('hreflang="x-default"') == 1
    assert (
        f'hreflang="x-default" href="{url_de("en")}"' in conteudo
    )  # x-default da MESMA página, no idioma padrão


def test_o_par_hreflang_da_pagina_interna_usa_a_forma_nua_do_padrao(
    client, rede, com_i18n
):
    # A regra vale em toda página, não só na raiz: o inglês de /cadastro é
    # /cadastro, e o pt-br é /pt-br/cadastro. Um par errado aqui é o tipo de
    # coisa que só aparece meses depois, no relatório de cobertura do Google.
    conteudo = client.get("/pt-br/cadastro", HTTP_HOST=HOST_A).content.decode()
    assert f'hreflang="en" href="{url_de("en", "/cadastro")}"' in conteudo
    assert f'hreflang="pt-BR" href="{url_de("pt-br", "/cadastro")}"' in conteudo


def test_es_noindex_emite_robots_e_pt_br_nao(client, rede, com_i18n):
    es = client.get("/es/", HTTP_HOST=HOST_A).content.decode()
    ptbr = client.get("/pt-br/", HTTP_HOST=HOST_A).content.decode()
    assert '<meta name="robots" content="noindex">' in es
    assert '<meta name="robots" content="noindex">' not in ptbr


def test_canonical_usa_o_host_canonico_do_site_nunca_o_da_requisicao(
    client, rede, com_i18n
):
    # Host de preview resolve para o MESMO Site A (a fixture com_i18n o mocka
    # devolvendo o Site cujo `host` é o canônico): o canonical/hreflang têm de
    # sair com o host canônico do Site — nunca request.get_host() (D5).
    conteudo = client.get("/", HTTP_HOST=HOST_PREVIEW).content.decode()
    assert f'<link rel="canonical" href="{url_de("en")}">' in conteudo
    assert HOST_PREVIEW not in conteudo


def test_toda_url_do_hreflang_aparece_como_ancora_real(client, rede, com_i18n):
    # D5: seletor de idioma é <a href> real — versão sem link rastreável pode
    # nunca ser descoberta. O seletor cobre TODOS os idiomas habilitados, e o
    # link do padrão é a raiz nua (mesma regra do canonical, mesma função).
    conteudo = client.get("/", HTTP_HOST=HOST_A).content.decode()
    for codigo in IDIOMAS_TESTE:
        assert f'<a href="{url_de(codigo)}"' in conteudo


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
# REGRESSÃO MONOLÍNGUE — Site que o catálogo serve SEM `languages`: NADA muda
# (nem um byte). É também a prova da degradação da fase 4: se o provedor não
# estiver no ar, é exatamente isto que o site multilíngue vira.
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
  <title>Curso Esqueleto (Site A)</title>
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
    # Capturado do código ANTERIOR à fase 1 (baseline verde daquele despacho).
    # Se este teste quebrar por mudança LEGÍTIMA de layout, recapture o HTML
    # renderizado da landing de teste e atualize a constante — nunca o afrouxe.
    resp = client.get("/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    assert resp.content.decode("utf-8") == HTML_DE_HOJE


@pytest.mark.parametrize("caminho", ["/en/", "/pt-br/", "/es/", "/pt-br/cadastro"])
def test_site_sem_languages_nao_tem_url_prefixada(client, rede, caminho):
    # A outra metade da regressão: sem `languages` no Site, as URLs de idioma
    # não existem — nem como redirect. É o que o funil serve enquanto o
    # provedor do catálogo não estiver no ar (degradação declarada da fase 4).
    assert client.get(caminho, HTTP_HOST=HOST_A).status_code == 404


def test_regressao_healthz_intocado(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_healthz_nao_toca_o_catalogo(client, rede):
    # A isenção do /healthz é a de sempre (sonda do container e do gateway não
    # pode depender do catálogo) — a fase 4 só tirou o /sitemap.xml dela.
    client.get("/healthz")
    assert [c for c in rede.calls if "/sites/by-host/" in str(c.request.url)] == []


def test_regressao_leads_de_site_nao_registrado_segue_funcionando(client, rede):
    resp = client.post(
        "/leads",
        '{"email": "aluno@exemplo.com"}',
        "application/json",
        HTTP_HOST=HOST_A,
    )
    assert resp.status_code == 200
    assert resp.json()["created"] is True
