from django.urls import path, re_path

from apps.core.divida import divida_json
from apps.core.painel import painel, painel_arquivo
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
    # O PAINEL DO DONO, vivo (`apps/core/painel.py`). A barra final é
    # ESTRUTURAL, não estilo: o HTML pede `manifesto.js` e `registros/*.js` por
    # caminho RELATIVO, e sem ela o navegador os buscaria um nível acima, na
    # raiz da área — a página abriria vazia, sem erro nenhum. Quem manda
    # `/painel` para `/painel/` é o APPEND_SLASH do CommonMiddleware, que já
    # está na cadeia.
    path("painel/", painel, name="painel"),
    # ANTES da rota genérica de arquivo, e a ordem é o que faz funcionar: esta
    # medição não é um arquivo em disco, e a rota de baixo responderia 404 por
    # ela. É a dívida do livro — merges que ninguém contou ao dono —, medida ao
    # vivo (`apps/core/divida.py`).
    path("painel/divida.json", divida_json, name="painel_divida"),
    re_path(r"^painel/(?P<path>.+)$", painel_arquivo, name="painel_arquivo"),
    path("", visao_geral, name="visao_geral"),
]
