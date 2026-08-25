import json
from urllib.parse import urlencode

import httpx
from django import forms
from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import (
    require_http_methods,
    require_POST,
    require_safe,
)
from django.views.static import serve as serve_do_django

from apps.core.clients import CatalogoClient, LeadsClient
from apps.core.enderecos import url_de_entrada
from apps.i18n.catalogo import js_da_pagina
from apps.i18n.idiomas import caminho_publico

# Ordem fixa: é também a ordem em que a query string do link do checkout é
# montada — preservar isso torna o teste de UTM determinístico.
CHAVES_UTM = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")

# Páginas públicas localizadas da célula, para o sitemap (fase 2; a Receita
# R12 da fase 3 decide se isto vira registro por página).
PAGINAS_PUBLICAS = ("/", "/cadastro")


def _utm_da_requisicao(request) -> dict:
    return {chave: valor for chave in CHAVES_UTM if (valor := request.GET.get(chave))}


@require_safe
def healthz(request):
    return JsonResponse({"status": "ok"})


def servir_estatico(request, path):
    """Estáticos em produção. Sem esta rota o formulário da landing não existe.

    Com `DEBUG=0` o Django não serve estático por conta própria, e esta célula
    está SOZINHA atrás do Traefik: não há nginx, CDN nem router `/static` no
    gateway (o catch-all `PathPrefix(/)` manda tudo para cá). Resultado medido
    ao vivo em 24/08/2026: `/static/funil/api.js` respondia 404 nos dois
    domínios, as landings carregavam esse `<script>` mesmo assim, e a ilha
    Alpine quebrava no `api.post(...)` — em silêncio para o visitante. A célula
    checkout resolveu o MESMO problema assim em 22/08/2026 e está verde em
    produção desde então; aqui se copia o padrão, não o arquivo (Lei 7).

    Duas escolhas que parecem detalhe e são o fix:

    1. **Serve do diretório-FONTE (`STATICFILES_DIRS[0]`), nunca de
       `STATIC_ROOT`.** O `collectstatic --noinput || true` do Dockerfile falha
       em TODO build — não há `DJANGO_SECRET_KEY` em tempo de build e o
       `settings.py` é fail-hard — e o `|| true` engole o erro: a imagem sobe
       com `STATIC_ROOT` vazio. Servir de lá (o default do whitenoise, entre
       outros) manteria o 404 com a suíte inteira verde. O diretório-fonte
       está na imagem pelo `COPY . .`, e é o mesmo caminho em dev e em prod.
    2. **É rota de MÁQUINA e nunca se localiza (D6).** O resolver de idioma
       decapa o prefixo em `path_info` ANTES da resolução de URL, então sem
       esta guarda `/pt-br/static/funil/api.js` passaria a responder 200 —
       uma URL de máquina por idioma, conteúdo duplicado para robô e
       superfície nova para ninguém. Mesma guarda do `sitemap_xml` abaixo.
    """
    if getattr(request, "idioma", None) is not None:
        raise Http404("estático não tem prefixo de idioma")
    return serve_do_django(request, path, document_root=settings.STATICFILES_DIRS[0])


@require_safe
def landing(request):
    """[RECEITA:R6 v1] Vitrine mínima: lê a default_offer do site (R2, server-side)
    e monta o link do checkout preservando UTM na query string."""
    site = request.site
    slug = site.get("default_offer_slug")
    if not slug:
        raise Http404("site sem oferta padrão configurada")

    oferta = CatalogoClient().obter_oferta(site["id"], slug)
    if oferta is None:
        raise Http404("oferta padrão não encontrada neste site")

    utm = _utm_da_requisicao(request)
    query = urlencode(utm)
    url_checkout = f"/checkout/{slug}/" + (f"?{query}" if query else "")

    contexto = {
        "site": site,
        "oferta": oferta,
        "preco_formatado": f"{oferta['price_cents'] / 100:.2f}".replace(".", ","),
        "url_checkout": url_checkout,
        "utm": utm,
    }
    if getattr(request, "idioma", None):
        # Site registrado no i18n: template PRÓPRIO (Lei 7 — cópia do padrão).
        # O caminho do site NÃO registrado fica intocado, byte a byte (golden
        # da fase 1) — por isso dois templates, nunca um `if` dentro de um só.
        contexto["i18n_js"] = js_da_pagina("landing", request.idioma)
        return render(request, "funil/landing_i18n.html", contexto)
    return render(request, "funil/landing.html", contexto)


class FormularioDeCadastro(forms.Form):
    """Validação server-side da página de cadastro. As mensagens de erro são
    as do próprio Django — o activate() do resolver (fase 1) as localiza."""

    name = forms.CharField(max_length=200)
    email = forms.EmailField()
    phone = forms.CharField(max_length=40, required=False)


# HEAD junto com GET, sempre: `require_http_methods` NÃO o inclui de graça (o
# `require_safe` das views de leitura inclui, e foi por isso que esta escapou do
# conserto de 25/08). Um HEAD nesta página respondia 405 — e ela está no
# sitemap, então quem a chama assim é justamente robô de busca e
# pré-visualizador de link. Medido em produção depois do deploy do PR #158.
@require_http_methods(["GET", "HEAD", "POST"])
def cadastro(request):
    """PLANO-I18N fase 2: página de cadastro, só no regime prefixado.

    O form posta para a PRÓPRIA URL prefixada (decisão da maestro sobre a
    pendência 1 do PR #87): o resolver decapa o prefixo, esta view recebe e
    repassa à célula leads server-side — mesmo canal POST /leads da landing,
    com o idioma do lead gravado em `source` (D9: lead sem idioma não tem
    retrofit).

    Desde o D1 revisto (25/08/2026) o caminho nu `/cadastro` **é** a página em
    inglês, e o POST dele chega aqui normalmente. Na matriz antiga ele morria
    404 antes desta view — o caminho nu era um 302 para `/en/cadastro`, e
    redirecionar um POST converteria o método em GET e descartaria o corpo em
    silêncio, então recusar era o menos pior. Sem redirecionamento no meio, o
    problema deixou de existir."""
    if getattr(request, "idioma", None) is None:
        # Site fora do registro i18n não tem cadastro — 404, o mesmo que o
        # caminho respondia antes desta fase (rota inexistente).
        raise Http404("cadastro só existe em site registrado no i18n")

    sucesso, erro_envio, status = False, False, 200
    if request.method == "POST":
        form = FormularioDeCadastro(request.POST)
        if form.is_valid():
            payload = {
                "site_id": request.site["id"],  # [INV-P11] do Host, não do payload
                "email": form.cleaned_data["email"],
                "name": form.cleaned_data["name"],
                "phone": form.cleaned_data["phone"],
                "source": f"cadastro-meshcraft-{request.idioma}",
            }
            try:
                LeadsClient().upsert_lead(payload)
                sucesso = True
                form = FormularioDeCadastro()  # sucesso limpa o formulário
            except httpx.HTTPError:
                # Falha fechada e honesta (ARMADILHAS §4.9): nada de 200 com
                # cara de sucesso — 502 com a página e o que a pessoa digitou.
                erro_envio, status = True, 502
    else:
        form = FormularioDeCadastro()

    return render(
        request,
        "funil/cadastro.html",
        {"form": form, "sucesso": sucesso, "erro_envio": erro_envio},
        status=status,
    )


# O vocabulário de recusa da célula `identidade` (LICOES.md dela: "o
# vocabulário de recusa é CONTRATO com o funil") — toda recusa da porta volta
# para esta página com `?erro=<chave>`, e cada chave tem tradução própria em
# `traducoes/login.yaml`. Chave fora desta lista é ignorada em silêncio: query
# string é entrada de rede, nunca vira chave de catálogo sem passar na cerca.
def destino_local(cru: str | None, padrao: str) -> str:
    """Só caminho LOCAL deste site — nunca um endereço de fora.

    O `?next=` chega pela URL, então é entrada de rede. A célula `identidade`
    sanea de novo do lado dela (`views.destino_seguro`), e é lá que mora a
    defesa que importa — esta aqui é a segunda camada, para o valor que ESTE
    site monta no link nunca ser o vetor. `//outro-site` é o clássico: o
    navegador o lê como endereço absoluto sem esquema.
    """
    if not cru or not cru.startswith("/") or cru.startswith("//"):
        return padrao
    if "\\" in cru or any(ord(c) < 0x20 for c in cru):
        return padrao
    return cru


CHAVES_DE_RECUSA = {
    "interrompida",
    "nao-confere",
    "nao-configurada",
    "google-indisponivel",
    "email-nao-verificado",
}


@require_safe
def entrar(request):
    """A porta de entrada do site — `/login` em inglês, `/{idioma}/login` nos outros.

    Leis: DECISAO-onde-mora-a-sessao e, desde 25/08/2026,
    DECISAO-celula-de-identidade. Ela leva ao Google; a sessão nasce do outro
    lado, na célula `identidade`. **Esta view não abre sessão nenhuma e não lê
    cookie nenhum** — quem faz isso é quem tem a chave e o banco (Lei 2, Lei 3).

    O `?next=` diz à `identidade` aonde devolver a pessoa depois de entrar —
    a home do idioma desta página. E o `?erro=` é a volta do vocabulário de
    recusa: a porta de lá não renderiza página; quem explica a recusa, nos
    três idiomas, é esta tela.

    Fora do sitemap de propósito: página de entrada não é conteúdo que alguém
    procure no Google, e indexá-la só a faria concorrer com a própria marca.
    """
    if getattr(request, "idioma", None) is None:
        # Mesmo tratamento do cadastro: site fora do registro i18n não tem esta
        # página — 404, e não uma página em inglês servida por engano.
        raise Http404("login só existe em site registrado no i18n")
    erro = request.GET.get("erro") or ""
    if erro not in CHAVES_DE_RECUSA:
        erro = ""
    # A pessoa volta para ONDE ESTAVA, não para a home. O cabeçalho de sessão
    # de toda página manda o caminho atual no `?next=`; sem isso, quem clicava
    # "Entrar" no meio de um cadastro meio preenchido voltava para a home e
    # perdia o que tinha digitado.
    # O fallback é a home DESTE idioma, e ela sai do caminho_publico como
    # qualquer outra URL pública. Escrevê-la à mão aqui — f"/{idioma}/" — era a
    # QUARTA cópia da regra de prefixo, e a que mais doeria: no idioma padrão
    # ela devolveria a pessoa, depois de entrar, para /en/ — 404 desde o D1
    # revisto (25/08/2026). Quem não passa `?next=` é justamente quem clicou
    # "Entrar" na home.
    home = caminho_publico(request.i18n, request.idioma, "/")
    destino = destino_local(request.GET.get("next"), home)
    entrada = f"{url_de_entrada()}?{urlencode({'next': destino})}"
    return render(
        request,
        "funil/login.html",
        {"url_de_entrada": entrada, "erro": erro, "destino": destino},
    )


@require_safe
def sitemap_xml(request):
    """D6: rota de MÁQUINA — nunca se localiza. Desde a fase 4 ela PRECISA do
    Site: os idiomas vêm do catálogo, então o CONV-SITE resolve o Host aqui
    como em qualquer rota (mesmo cache de 60s) e a view lê `request.i18n`. As
    URLs saem absolutas com o **host canônico do Site** — nunca
    `request.get_host()` (D5: preview não vaza pro sitemap de produção). Site
    monolíngue: 404, o comportamento de hoje, intocado."""
    if getattr(request, "idioma", None) is not None or request.path != "/sitemap.xml":
        # /en/sitemap.xml e afins: rota de máquina nunca se localiza (D6).
        raise Http404("sitemap não tem prefixo de idioma")
    cfg = getattr(request, "i18n", None)
    if cfg is None:
        raise Http404("site sem sitemap")
    host = request.site["host"]

    urls = [
        # O caminho sai do caminho_publico, nunca de uma f-string local: desde o
        # D1 revisto (25/08/2026) o idioma padrão não leva prefixo, e um sitemap
        # anunciando /en/ mandaria o Google a 404 nossos.
        f"https://{host}{caminho_publico(cfg, codigo, pagina)}"
        for codigo, definicao in cfg["idiomas"].items()
        if definicao["indexavel"]  # D5: es (noindex) fica fora
        for pagina in PAGINAS_PUBLICAS
    ]
    linhas = "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls)
    corpo = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{linhas}\n"
        "</urlset>\n"
    )
    return HttpResponse(corpo, content_type="application/xml")


@require_POST
def capturar_lead(request):
    """[RECEITA:R2 v1] O formulário nunca fala direto com leads: posta aqui, e o
    servidor repassa com o site_id resolvido pelo CONV-SITE (nunca do payload)."""
    try:
        corpo = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest("payload inválido")

    email = corpo.get("email")
    if not email:
        return JsonResponse({"erro": "email obrigatório"}, status=422)

    payload = {
        "site_id": request.site["id"],
        "email": email,
        "name": corpo.get("name") or "",
        "phone": corpo.get("phone") or "",
        "source": corpo.get("source") or "funil",
        "utm": corpo.get("utm") or {},
    }
    resultado = LeadsClient().upsert_lead(payload)
    return JsonResponse(resultado, status=200)
