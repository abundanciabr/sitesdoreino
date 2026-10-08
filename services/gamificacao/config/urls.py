from django.urls import path, re_path
from apps.core.views import (
    base, medalhas, healthz, servir_estatico,
    interno_reconhecimentos, decidir_reconhecimento,
)
from config.api import api

urlpatterns = [
    path("healthz", healthz),
    path("api/gamificacao/", api.urls),
    re_path(r"^static/(?P<caminho>.*)$", servir_estatico, name="estatico"),
    path("medalhas", medalhas, name="medalhas"),
    path("interno/reconhecimentos", interno_reconhecimentos, name="interno-reconhecimentos"),
    path("interno/reconhecimentos/gesto", decidir_reconhecimento, name="decidir-reconhecimento"),
    path("", base, name="base"),
]
handler404 = "site_errors.handlers.page_not_found_shared"
handler500 = "site_errors.handlers.server_error_shared"
