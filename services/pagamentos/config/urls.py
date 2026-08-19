from django.http import HttpRequest, JsonResponse
from django.urls import path

from config.api import api
from pagamentos.api.webhooks import simulate_webhook


def healthz(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz", healthz),
    path("api/pagamentos/", api.urls),
    # Rota fora do NinjaAPI de propósito: nunca aparece no export_openapi/freeze
    # de contrato. simulate_webhook() checa settings.DEBUG e 404 sozinha (ver
    # ESQUELETO-QUE-ANDA.md — com DEBUG=0 o endpoint NÃO EXISTE).
    path("debug/simulate-webhook", simulate_webhook),
]
