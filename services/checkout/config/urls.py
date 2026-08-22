from django.conf import settings
from django.http import JsonResponse
from django.urls import path, re_path
from django.views.static import serve as servir_estatico

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
    # Com DEBUG=0 o Django não serve estáticos sozinho, e esta célula está
    # sozinha atrás do Traefik (não há nginx/CDN na frente): sem esta rota as
    # páginas subiam em produção sem NENHUM .js — ninguém conseguia comprar.
    # django.views.static.serve do diretório-fonte é suficiente para o volume
    # destas páginas e evita dependência nova (whitenoise); o dia em que houver
    # CDN/collectstatic de verdade, esta rota sai. Funciona igual em dev.
    re_path(
        r"^static/(?P<path>.*)$",
        servir_estatico,
        {"document_root": settings.STATICFILES_DIRS[0]},
    ),
]
