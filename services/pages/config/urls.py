from django.urls import path, re_path

from apps.core.views import (
    assumir,
    baixar_dossie,
    decidir,
    despublicar_vitrine,
    fila_da_equipe,
    guardar_peca,
    healthz,
    marcar,
    mudar_peca,
    pecas,
    pedir_conferencia,
    prancheta,
    publicar_vitrine,
    responder_peca,
    vitrine_publica,
)
from config.api import api
from apps.core.enderecos import trabalhos_antigos
from apps.portfolio.imagens import servir_imagem

urlpatterns = [
    path("healthz", healthz),
    path("interno/", api.urls),
    path("marcar", marcar, name="marcar"),
    path("trabalhos", pecas, name="pecas"),
    path("trabalhos/guardar", guardar_peca, name="guardar_peca"),
    path("trabalhos/mudar", mudar_peca, name="mudar_peca"),
    path("trabalhos/responder", responder_peca, name="responder_peca"),
    path("trabalhos/conferir", pedir_conferencia, name="pedir_conferencia"),
    path("equipe", fila_da_equipe, name="equipe"),
    path("equipe/decidir", decidir, name="decidir"),
    path("equipe/assumir", assumir, name="assumir"),
    path("vitrine/publicar", publicar_vitrine, name="publicar_vitrine"),
    path("vitrine/despublicar", despublicar_vitrine, name="despublicar_vitrine"),
    path("dossie", baixar_dossie, name="dossie"),
    path("imagens/<uuid:imagem_id>", servir_imagem, name="imagem_portfolio"),
    path("pecas", trabalhos_antigos),
    path("pecas/<path:restante>", trabalhos_antigos),
    path("", prancheta, name="prancheta"),
    re_path(r"^(?P<apelido>[a-z0-9-]+)/?$", vitrine_publica, name="vitrine"),
]

handler404 = "site_errors.handlers.page_not_found_shared"
handler500 = "site_errors.handlers.server_error_shared"
