from django.urls import path

from apps.core.views import dar_titulo, healthz, plantao
from config.api import api

# O urlconf da célula NÃO conhece o prefixo público (`/encomendas`): quem o
# aplica é `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py`. Mover a
# célula de endereço é editar Traefik + env, nunca cirurgia aqui
# (`armadilhas/029`; guarda em `tests/test_healthz_script_name.py`).
#
# TODA rota leva `name=`, e nenhum template escreve caminho à mão: é
# `reverse()`/`{% url %}` quem carrega o prefixo público para dentro do
# endereço. Caminho cravado em string quebra em produção e SÓ lá
# (`armadilhas/029` e `/081`).
#
# E quando houver CSS: a rota `servir_estatico` é obrigatória, com nome próprio
# (`estatico`), porque com DEBUG=0 o Django não serve estático e não há nginx
# nem CDN atrás do Traefik, e o arquivo vira 404 em produção e SÓ lá
# (`armadilhas/083`). Sob prefixo, o `<link>` sai de `{% url 'estatico' %}` e
# **nunca** de `{% static %}` (`armadilhas/102`). A tela do plantão que nasce
# aqui não tem arquivo de estilo de propósito: ela é o mínimo da lei §3.6 e
# §3.4, e a tela cheia do plantão é a Fase 7.
#
# A PORTA DE MAQUINA (degrau 2.7) mora em `api/encomendas/`, e o `/interno/` do
# contrato é um caminho DENTRO dela. Nesta célula esses caminhos ficam DEBAIXO
# do prefixo roteado: `meshcraft.top/encomendas/api/encomendas/interno/...` é
# alcançável pela internet, porque o corte do prefixo é do Django e não do
# Traefik (`armadilhas/186`). Quem fecha a porta é o Bearer do par, e o guarda
# que importa é o teste de 401 em TODAS as operações. A topologia não fecha nada
# aqui, e escrever o contrário no comentário seria ensinar errado quem chegar
# depois.
urlpatterns = [
    path("healthz", healthz),
    path("plantao", plantao, name="plantao"),
    path("plantao/titulo", dar_titulo, name="plantao_titulo"),
    path("api/encomendas/", api.urls),
]
