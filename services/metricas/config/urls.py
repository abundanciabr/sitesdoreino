from django.urls import path

from apps.core.views import healthz

# O urlconf da célula NÃO conhece prefixo público: quem o aplica é
# `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py` (`armadilhas/029`;
# guarda em `tests/test_healthz_script_name.py`).
#
# Esta célula não terá tela: quem mostra número é a `admin`. O que nasce aqui
# adiante é porta de MÁQUINA:
#
#   degrau 7.3 — a recepção de eventos (`/interno/eventos`), fechada por Bearer
#                de par, fail-closed: evento inválido vai para a fila de
#                eventos mortos e vira incidente, nunca é aceito pela metade.
#   degrau 7.4 — a API de leitura (`/api/metricas/`): fotos de coorte, marcos
#                por pessoa, contadores históricos, cobertura e conciliação.
#
# Os dois nascem com o teste de 401 em TODAS as operações no MESMO PR: a
# topologia não fecha nada (`armadilhas/186`), quem fecha é o Bearer.
urlpatterns = [
    path("healthz", healthz),
]
