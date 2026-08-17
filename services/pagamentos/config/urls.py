from django.http import HttpRequest, JsonResponse
from django.urls import path

from config.api import api


def healthz(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz", healthz),
    path("api/pagamentos/", api.urls),
]
