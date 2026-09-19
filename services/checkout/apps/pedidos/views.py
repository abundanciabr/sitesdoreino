# apps/pedidos/views.py  # [RECEITA:R6 v1]
# Páginas públicas dados/pix/cartão. Cada view só monta o contexto mínimo que o
# template embute via json_script — a lógica de negócio vive na API interna
# (apps/core/api.py), nunca aqui.
import uuid

from django.conf import settings
from django.http import Http404
from django.shortcuts import render

from apps.pedidos.models import Order as OrderModel


def _api_base(request) -> str:
    """Base da API interna a partir do prefixo REAL da requisição. Atrás do
    Traefik a célula vive sob SCRIPT_NAME=/checkout — um caminho hardcoded
    ("/api/checkout") no front chamaria a raiz do domínio e cairia FORA da
    célula. O template embute isto como window.API_BASE; api.js nunca hardcoda
    prefixo nenhum."""
    return request.META.get("SCRIPT_NAME", "") + "/api/checkout"


def dados(request, offer_slug: str):
    return render(
        request,
        "checkout/dados.html",
        {
            "offer_slug": offer_slug,
            "api_token": settings.TOKEN_DA_PAGINA,
            "api_base": _api_base(request),
        },
    )


def _pedido_do_site(request, order_id: uuid.UUID, method: str) -> OrderModel:
    try:
        # [INV-P11] pedido de outro site é 404 aqui, igual ao GET /pedidos/{id}.
        pedido = OrderModel.objects.get(pk=order_id, site_id=request.site["id"])
    except OrderModel.DoesNotExist:
        raise Http404("pedido inexistente neste site")
    if pedido.method != method:
        raise Http404("pedido não usa este método de pagamento")
    return pedido


def pix(request, order_id: uuid.UUID):
    pedido = _pedido_do_site(request, order_id, "pix")
    return render(
        request,
        "checkout/pix.html",
        {
            "order_id": str(pedido.id),
            "pix_data": pedido.pix,
            "api_token": settings.TOKEN_DA_PAGINA,
            "api_base": _api_base(request),
        },
    )


def cartao(request, order_id: uuid.UUID):
    pedido = _pedido_do_site(request, order_id, "card")
    return render(
        request,
        "checkout/cartao.html",
        {
            "order_id": str(pedido.id),
            "total_cents": pedido.total_cents,
            "api_token": settings.TOKEN_DA_PAGINA,
            "api_base": _api_base(request),
        },
    )
