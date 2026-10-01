"""Only used before the contextual settings are installed."""

from django.http import JsonResponse
from django.urls import path

urlpatterns = [path("healthz", lambda request: JsonResponse({"status": "ok"}))]
