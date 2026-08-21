# apps/pedidos/views.py  # [RECEITA:R6 v1]
# Páginas públicas dados/pix/cartão. Cada view só monta o contexto mínimo que o
# template embute via json_script — a lógica de negócio vive na API interna
# (apps/core/api.py), nunca aqui.
import os
import uuid

from django.http import Http404
from django.shortcuts import render

from apps.pedidos.models import Order as OrderModel

# Token do próprio front para chamar a API interna — par consumidor "paginas",
# no mesmo padrão CONV de apps/core/auth.py (um TOKENS_ACEITOS_<NOME> por
# consumidor). Lido no ponto de uso, não em settings.py: não é fail-hard porque
# sem ele as páginas ainda renderizam (só a chamada à API falhará com 401).
_API_TOKEN = os.environ.get("TOKENS_ACEITOS_PAGINAS", "")


def dados(request, offer_slug: str):
    return render(
        request,
        "checkout/dados.html",
        {"offer_slug": offer_slug, "api_token": _API_TOKEN},
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
            "api_token": _API_TOKEN,
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
            "api_token": _API_TOKEN,
        },
    )
