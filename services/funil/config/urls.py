from django.urls import path

from apps.core.views import capturar_lead, healthz, landing

urlpatterns = [
    path("healthz", healthz),
    path("leads", capturar_lead, name="capturar_lead"),
    # [RECEITA:R6 v1] catch-all: funil serve a raiz de QUALQUER host cadastrado.
    path("", landing, name="landing"),
]
