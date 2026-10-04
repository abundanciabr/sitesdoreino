# apps/pedidos/views.py  # [RECEITA:R6 v1]
# Páginas públicas dados/pix/cartão. Cada view só monta o contexto mínimo que o
# template embute via json_script — a lógica de negócio vive na API interna
# (apps/core/api.py), nunca aqui.
import uuid

from django.conf import settings
from django.http import Http404
from django.shortcuts import render

from apps.pedidos.atribuicao import atribuicao_da_consulta
from apps.pedidos.models import Order as OrderModel


def _api_base(request) -> str:
    """Base da API interna a partir do prefixo REAL da requisição. Atrás do
    Traefik a célula vive sob SCRIPT_NAME=/checkout — um caminho hardcoded
    ("/api/checkout") no front chamaria a raiz do domínio e cairia FORA da
    célula. O template embute isto como window.API_BASE; api.js nunca hardcoda
    prefixo nenhum."""
    return request.META.get("SCRIPT_NAME", "") + "/api/checkout"


def _static_base(request) -> str:
    return request.META.get("SCRIPT_NAME", "").rstrip("/") + "/static/checkout"


def dados(request, offer_slug: str):
    return render(
        request,
        "checkout/dados.html",
        {
            "offer_slug": offer_slug,
            "atribuicao": atribuicao_da_consulta(request.GET),
            "api_token": settings.TOKEN_DA_PAGINA,
            "api_base": _api_base(request),
            "static_base": _static_base(request),
            "appmax_pix_provider": request.site["id"] in settings.APPMAX_PIX_ENABLED_SITES,
            "appmax_pix_enabled": request.site["id"]
            in (settings.APPMAX_PIX_ENABLED_SITES | settings.APPMAX_PIX_FALLBACK_SITES),
            "appmax_card_enabled": request.site["id"]
            in settings.APPMAX_CARD_ENABLED_SITES,
            "appmax_external_id": settings.APPMAX_EXTERNAL_ID,
            "appmax_script_url": (
                "https://scripts.sandboxappmax.com.br/appmax.min.js"
                if settings.APPMAX_API_URL == "https://api.sandboxappmax.com.br"
                else "https://scripts.appmax.com.br/appmax.min.js"
            ),
        },
    )


def _pedido_do_site(request, order_id: uuid.UUID, method: str) -> OrderModel:
    try:
        # pedido de outro site é 404 aqui, igual ao GET /pedidos/{id}.
        pedido = OrderModel.objects.get(pk=order_id, site_id=request.site["id"])
    except OrderModel.DoesNotExist:
        raise Http404("pedido inexistente neste site")
    if pedido.method != method:
        raise Http404("pedido não usa este método de pagamento")
    return pedido


def _url_da_oferta(request, pedido: OrderModel) -> str:
    """Volta para a página de dados da mesma oferta, sob o prefixo real."""
    return request.META.get("SCRIPT_NAME", "").rstrip("/") + f"/{pedido.session.offer_slug}/"


def pix(request, order_id: uuid.UUID):
    pedido = _pedido_do_site(request, order_id, "pix")
    return render(
        request,
        "checkout/pix.html",
        {
            "order_id": str(pedido.id),
            "pix_data": pedido.pix,
            "pix_trocado": bool((pedido.pix or {}).get("trocado_em")),
            "offer_url": _url_da_oferta(request, pedido),
            "api_token": settings.TOKEN_DA_PAGINA,
            "api_base": _api_base(request),
            "static_base": _static_base(request),
        },
    )


def cartao(request, order_id: uuid.UUID):
    pedido = _pedido_do_site(request, order_id, "card")
    script_appmax = "https://scripts.sandboxappmax.com.br/appmax.min.js"
    if settings.APPMAX_API_URL != "https://api.sandboxappmax.com.br":
        script_appmax = "https://scripts.appmax.com.br/appmax.min.js"
    return render(
        request,
        "checkout/cartao.html",
        {
            "order_id": str(pedido.id),
            "total_cents": pedido.total_cents,
            "offer_url": _url_da_oferta(request, pedido),
            "api_token": settings.TOKEN_DA_PAGINA,
            "api_base": _api_base(request),
            "static_base": _static_base(request),
            "appmax_external_id": settings.APPMAX_EXTERNAL_ID,
            "appmax_script_url": script_appmax,
            "mp_public_key": settings.MP_PUBLIC_KEY if pedido.site_id in settings.MP_CARD_FALLBACK_SITES else "",
        },
    )
