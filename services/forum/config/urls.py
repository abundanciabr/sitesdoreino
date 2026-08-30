from django.urls import path, re_path

from apps.core.views import (
    healthz,
    home,
    novo_topico,
    responder,
    servir_estatico,
    ver_area,
    ver_topico,
)
from config.api import api

# O urlconf da célula NÃO conhece o prefixo público (`/forum`): quem o aplica é
# `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py`. Mover o fórum de
# endereço é editar Traefik + env, nunca cirurgia aqui (`armadilhas/029`;
# guarda em `tests/test_healthz_script_name.py`).
#
# TODA rota leva `name=`, e nenhum template escreve caminho à mão: é
# `reverse()`/`{% url %}` quem carrega o prefixo público para dentro do
# endereço. Caminho cravado em string quebra em produção e SÓ lá
# (`armadilhas/029` e `/081`).
urlpatterns = [
    path("healthz", healthz),
    # A superficie de MAQUINA (`/interno/...`): o que outra celula pode
    # perguntar ao forum. Fica FORA do `/forum` publico de proposito — o
    # Traefik roteia so `/forum`, entao `/interno` nao tem porta pela borda.
    # Quem fecha em qualquer topologia futura e o Bearer do par (config/api.py).
    path("interno/", api.urls),
    # O rosto. Rota de MÁQUINA, como o `/healthz`: sem ela o CSS é 404 em
    # produção e SÓ lá (`armadilhas/083`).
    re_path(r"^static/(?P<caminho>.*)$", servir_estatico, name="estatico"),
    path("", home, name="home"),
    path("a/<slug:slug>", ver_area, name="area"),
    path("t/<int:topico_id>", ver_topico, name="topico"),
    # ESCREVER. Endereco proprio e `require_POST` nas duas: escrita por GET e
    # escrita que um `<img src>` de outro site dispara e que o robo do Google
    # executa ao passear pela pagina. O cadeado de quem pode escrever mora em
    # `apps/core/permissoes.py`, nunca aqui.
    path("a/<slug:slug>/novo", novo_topico, name="novo_topico"),
    path("t/<int:topico_id>/responder", responder, name="responder"),
]
