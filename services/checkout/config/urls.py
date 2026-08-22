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
    # SEM o prefixo "checkout/" nas rotas: em produção a célula vive sob
    # SCRIPT_NAME=/checkout, e o handler ASGI REMOVE esse prefixo do path_info
    # ANTES do casamento de rotas — rota escrita COM o prefixo dentro só casava
    # com a URL dobrada (/checkout/checkout/<slug>/, medida ao vivo em
    # 22/08/2026, enquanto /checkout/<slug>/ dava 404). Estáticos e healthz
    # sempre foram sem prefixo — por isso nunca quebraram. Os names continuam
    # os mesmos: {% url %}/reverse() prefixam o SCRIPT_NAME sozinhos.
    path("pedido/<uuid:order_id>/pix/", paginas.pix, name="checkout_pix"),
    path(
        "pedido/<uuid:order_id>/cartao/",
        paginas.cartao,
        name="checkout_cartao",
    ),
    path("<slug:offer_slug>/", paginas.dados, name="checkout_dados"),
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
