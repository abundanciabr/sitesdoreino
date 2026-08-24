import json
from urllib.parse import urlencode

import httpx
from django import forms
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.core.clients import CatalogoClient, LeadsClient
from apps.i18n.catalogo import js_da_pagina
from apps.i18n.registro import registro_do_host

# Ordem fixa: é também a ordem em que a query string do link do checkout é
# montada — preservar isso torna o teste de UTM determinístico.
CHAVES_UTM = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")

# Páginas públicas localizadas da célula, para o sitemap (fase 2; a Receita
# R12 da fase 3 decide se isto vira registro por página).
PAGINAS_PUBLICAS = ("/", "/cadastro")


def _utm_da_requisicao(request) -> dict:
    return {chave: valor for chave in CHAVES_UTM if (valor := request.GET.get(chave))}


@require_GET
def healthz(request):
    return JsonResponse({"status": "ok"})


@require_GET
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


@require_http_methods(["GET", "POST"])
def cadastro(request):
    """PLANO-I18N fase 2: página de cadastro, só no regime prefixado.

    O form posta para a PRÓPRIA URL prefixada (decisão da maestro sobre a
    pendência 1 do PR #87): o resolver decapa o prefixo, esta view recebe e
    repassa à célula leads server-side — mesmo canal POST /leads da landing,
    com o idioma do lead gravado em `source` (D9: lead sem idioma não tem
    retrofit). Caminho nu POST /cadastro morre 404 na matriz, antes daqui."""
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


@require_GET
def sitemap_xml(request):
    """D6: rota de MÁQUINA — sem prefixo de idioma, isenta do CONV-SITE (não
    depende do catálogo, como /healthz). Por Host: URLs dos idiomas indexáveis
    do site registrado, absolutas com o host canônico (a chave do registro É o
    host canônico — host desconhecido dele, inclusive preview, é 404). Site
    não registrado: 404, o comportamento de hoje, intocado."""
    if getattr(request, "idioma", None) is not None or request.path != "/sitemap.xml":
        # /en/sitemap.xml e afins: rota de máquina nunca se localiza (D6).
        raise Http404("sitemap não tem prefixo de idioma")
    host = request.get_host().split(":")[0].lower()
    cfg = registro_do_host(host)
    if cfg is None:
        raise Http404("site sem sitemap")

    urls = [
        f"https://{host}/{codigo}{pagina}"
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
