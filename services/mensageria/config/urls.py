from django.urls import path

from apps.core.views import healthz
from config.api import api

# A `mensageria` não serve página nenhuma: não há `SCRIPT_NAME`, não há rota no
# Traefik e não há template. As duas rotas abaixo são tudo que esta célula
# expõe, e as duas só existem dentro da rede `interna` do Docker.
#
# `/healthz` é a sonda do compose (`infra/docker-compose.yml`, x-celula) e o que
# faz o processo auxiliar esperar o `migrate` do servidor HTTP terminar
# (ARMADILHAS §3.13). Ela responde sem autenticação nenhuma, de propósito.
#
# `/api/mensageria/` é a porta de MÁQUINA (degrau 6c do
# `PLANO-SEQUENCIAS-DE-MENSAGENS.md`): é por ela que a tela do mantenedor, que
# mora na célula `admin`, lê as sequências e publica uma frase nova. Quem fecha
# é o Bearer, em dois graus (`apps/core/auth.py`). O endereço escolhido e o
# motivo estão em `config/api.py`; congelá-lo é o degrau 6d, PR à parte.
urlpatterns = [
    path("healthz", healthz),
    path("api/mensageria/", api.urls),
]
