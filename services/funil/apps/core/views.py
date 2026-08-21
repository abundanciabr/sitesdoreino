import json
from urllib.parse import urlencode

from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from apps.core.clients import CatalogoClient, LeadsClient

# Ordem fixa: é também a ordem em que a query string do link do checkout é
# montada — preservar isso torna o teste de UTM determinístico.
CHAVES_UTM = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")


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

    return render(
        request,
        "funil/landing.html",
        {
            "site": site,
            "oferta": oferta,
            "preco_formatado": f"{oferta['price_cents'] / 100:.2f}".replace(".", ","),
            "url_checkout": url_checkout,
            "utm": utm,
        },
    )


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
