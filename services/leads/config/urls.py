from django.http import JsonResponse
from django.urls import path

from config.api import api


def healthz(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz", healthz),
    path("api/leads/", api.urls),
]
