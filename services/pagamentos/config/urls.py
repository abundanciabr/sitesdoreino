from django.http import HttpRequest, JsonResponse
from django.urls import path

from config.api import api
from pagamentos.api.appmax import instalacao_appmax
from pagamentos.api.webhooks import simulate_webhook, webhook_appmax, webhook_mp_unificado
from pagamentos.marketplace.api import charge_create, charge_detail, charge_by_order, charge_capture, receivable_register, marketplace_status, paypal_webhook, pix_webhook


def healthz(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz", healthz),
    path("api/pagamentos/marketplace/charges", charge_create),
    path("api/pagamentos/marketplace/orders/<uuid:order_id>/charge", charge_by_order),
    path("api/pagamentos/marketplace/receivables", receivable_register),
    path("api/pagamentos/marketplace/status", marketplace_status),
    path("api/pagamentos/marketplace/charges/<uuid:charge_id>", charge_detail),
    path("api/pagamentos/marketplace/charges/<uuid:charge_id>/capture", charge_capture),
    path("api/pagamentos/marketplace/webhooks/paypal", paypal_webhook),
    path("api/pagamentos/marketplace/webhooks/mp", pix_webhook),
    # Antes de api.urls de propósito: a instalação da Appmax mora fora do
    # NinjaAPI (ver pagamentos/api/appmax.py) e, declarada aqui em cima, não
    # depende de como o resolvedor trata um prefixo que casa sem subrota.
    path("api/pagamentos/appmax/instalacao", instalacao_appmax),
    path("api/pagamentos/appmax/webhooks", webhook_appmax),
    path("api/pagamentos/mp/webhooks", webhook_mp_unificado),
    path("api/pagamentos/mp/webhooks/", webhook_mp_unificado),
    path("api/pagamentos/mercadopago/webhooks", webhook_mp_unificado),
    path("api/pagamentos/mercadopago/webhooks/", webhook_mp_unificado),
    path("api/pagamentos/", api.urls),
    # Rota fora do NinjaAPI de propósito: nunca aparece no export_openapi/freeze
    # de contrato. simulate_webhook() checa settings.DEBUG e 404 sozinha (ver
    # ESQUELETO-QUE-ANDA.md — com DEBUG=0 o endpoint NÃO EXISTE).
    path("debug/simulate-webhook", simulate_webhook),
]
