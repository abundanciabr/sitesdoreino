from django.urls import path

from apps.core.views import healthz
from config.api import api

# O urlconf da célula NÃO conhece prefixo público: quem o aplica é
# `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py` (`armadilhas/029`;
# guarda em `tests/test_healthz_script_name.py`).
#
# Esta célula não tem tela: quem mostra número é a `admin`. As duas rotas aqui
# são de MÁQUINA, e a lista abaixo corrige o que este arquivo previa na gênese:
# a recepção de eventos (degrau 7.3) NÃO virou porta HTTP. Ela é um consumidor
# de Redis Streams (`apps/fatos/management/commands/consume_eventos.py`), como
# nas outras cinco células consumidoras, porque o transporte de evento nesta
# casa é o stream, e uma segunda forma de entrar seria uma segunda forma de o
# mesmo fato chegar.
#
#   /healthz         a sonda do container.
#   /api/metricas/   a porta de leitura (degrau 7.4): contadores históricos por
#                    dia, cobertura de rastreio e a fila de eventos mortos.
#
# A porta nasce com o teste de 401 em TODAS as operações, medidas do schema
# vivo: a topologia não fecha nada (`armadilhas/186`), quem fecha é o Bearer.
urlpatterns = [
    path("healthz", healthz),
    path("api/metricas/", api.urls),
]
