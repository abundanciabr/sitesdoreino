from django.http import JsonResponse
from django.urls import path

from apps.pedidos import views as paginas
from config.api import api


def healthz(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz", healthz),
    path("api/checkout/", api.urls),
    # [RECEITA:R6 v1] páginas públicas — ilhas Alpine, zero estado compartilhado.
    path("checkout/<slug:offer_slug>/", paginas.dados, name="checkout_dados"),
    path("checkout/pedido/<uuid:order_id>/pix/", paginas.pix, name="checkout_pix"),
    path(
        "checkout/pedido/<uuid:order_id>/cartao/",
        paginas.cartao,
        name="checkout_cartao",
    ),
]
