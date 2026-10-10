from django.urls import path, re_path
from apps.core.views import (
    base, inicio_pagina, medalhas, healthz, servir_estatico, salvar_jornada, print_recebimento,
    interno_reconhecimentos, decidir_reconhecimento,
)
from apps.core.trilha_pessoal import minha_trilha
from config.api import api
from apps.core.inventario import inventario, arquivo_do_inventario

urlpatterns = [
    path("inicio/motivo/", inicio_pagina, {"etapa": 1}, name="inicio-motivo"),
    path("inicio/objetivo/", inicio_pagina, {"etapa": 2}, name="inicio-objetivo"),
    path("inicio/item/", inicio_pagina, {"etapa": 3}, name="inicio-item"),
    path("inventario/", inventario, name="inventario"),
    path("inventario/arquivos/<int:anexo_id>/", arquivo_do_inventario, name="arquivo-inventario"),
    path("minha-trilha/", minha_trilha, name="minha-trilha"),
    path("jornada/salvar", salvar_jornada, name="salvar-jornada"),
    path("jornada/prints/<int:versao_id>", print_recebimento, name="print-recebimento"),
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
