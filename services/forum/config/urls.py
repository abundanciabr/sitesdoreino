from django.urls import path

from apps.core.views import healthz

# O urlconf da célula NÃO conhece o prefixo público (`/forum`): quem o aplica é
# `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py`. Mover o fórum de
# endereço é editar Traefik + env, nunca cirurgia aqui (`armadilhas/029`;
# guarda em `tests/test_healthz_script_name.py`).
#
# Quando as telas nascerem: TODA rota leva `name=`, e nenhum template escreve
# caminho à mão — é `reverse()`/`{% url %}` quem carrega o prefixo público para
# dentro do endereço. Caminho cravado em string quebra em produção e SÓ lá
# (`armadilhas/029` e `/081`).
#
# E quando houver CSS: a rota `servir_estatico` é obrigatória, com nome próprio
# (`estatico`), porque com DEBUG=0 o Django não serve estático e não há nginx
# nem CDN atrás do Traefik — o arquivo vira 404 em produção e SÓ lá
# (`armadilhas/083` e `/102`). O molde está em `services/sugestoes`.
urlpatterns = [
    path("healthz", healthz),
]
