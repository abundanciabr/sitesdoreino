from django.urls import path

from apps.core.views import healthz, visao_geral

# O urlconf da célula NÃO conhece o prefixo público (`/admin`): quem o aplica é
# `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py`. Mover a área
# administrativa de endereço é editar Traefik + env, nunca cirurgia aqui
# (`armadilhas/029`; guarda em `tests/test_healthz_script_name.py`).
#
# TODA rota desta célula terá `name=`, e nenhum template escreverá caminho à
# mão: é `reverse()`/`{% url %}` quem carrega o prefixo público para dentro do
# endereço. Caminho cravado em string quebra em produção e SÓ lá
# (`armadilhas/081`). O `/healthz` é a exceção que confirma a regra — ele não
# tem `name` porque ninguém o referencia: é endereço de MÁQUINA, fixado por
# contrato com o healthcheck do compose, não por `reverse()`.
urlpatterns = [
    path("healthz", healthz),
    path("", visao_geral, name="visao_geral"),
]
