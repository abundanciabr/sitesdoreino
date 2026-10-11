from django.urls import path, re_path
from apps.core.views import (
    base, inicio_pagina, inicio_conquista, medalhas, healthz, servir_estatico, salvar_jornada, print_recebimento,
    interno_reconhecimentos, decidir_reconhecimento,
)
from apps.core.trilha_pessoal import minha_trilha
from config.api import api
from apps.core.inventario import inventario, arquivo_do_inventario
from apps.core.reinicio_faixas import relatorio_reinicio

urlpatterns = [
    path("interno/reinicio-faixas/", relatorio_reinicio, name="relatorio-reinicio-faixas"),
    path("inicio/motivo/", inicio_pagina, {"etapa": 1}, name="inicio-motivo"),
    path("inicio/objetivo/", inicio_pagina, {"etapa": 2}, name="inicio-objetivo"),
    path("inicio/item/", inicio_pagina, {"etapa": 3}, name="inicio-item"),
    path("inicio/envio/", inicio_pagina, {"etapa": 4}, name="inicio-envio"),
    path("inicio/conquista/<int:etapa>/", inicio_conquista, name="inicio-conquista"),
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
