from django.urls import path, re_path

from apps.core.views import (
    aula,
    entregar_checkpoint,
    gravar_autoavaliacao,
    healthz,
    mapa,
    registrar_pausa,
    servir_estatico,
)
from config.api import api

# O urlconf da célula NÃO conhece o prefixo público (`/cursos`): quem o aplica
# é `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py`. Mover a célula
# de endereço é editar Traefik + env, nunca cirurgia aqui (`armadilhas/029`;
# guarda em `tests/test_healthz_script_name.py`).
#
# TODA rota leva `name=`, e nenhum template escreve caminho à mão: é
# `reverse()`/`{% url %}` quem carrega o prefixo público para dentro do
# endereço. Caminho cravado em string quebra em produção e SÓ lá
# (`armadilhas/029` e `/081`).
#
# A porta de MÁQUINA (`/api/cursos/`, degrau 1.3) FICA DEBAIXO do prefixo
# roteado: `meshcraft.top/cursos/api/cursos/…` é alcançável pela internet, e o
# corte do prefixo é do Django, não do Traefik (`armadilhas/186`). Quem fecha a
# porta é o Bearer do par (`tests/test_porta_exige_bearer.py`); a topologia não
# fecha nada aqui.
#
# As telas que ainda NÃO existem, e o degrau de cada uma: o laudo recebido em
# `<numero>/laudo` (2.2), o plantão em `plantao` e `plantao/<envio>` (2.2). O
# envio do checkpoint (2.1) é gesto desta mesma tela da aula: `<numero>/checkpoint`.
urlpatterns = [
    path("healthz", healthz),
    path("api/cursos/", api.urls),
    # O CSS, servido pela própria célula. Sem esta rota o estilo é 404 em
    # produção e SÓ lá (`armadilhas/083`): com DEBUG=0 o Django não serve
    # estático, e não há nginx nem CDN atrás do Traefik. O nome é `estatico`,
    # e o `<link>` sai de `{% url 'estatico' %}`, nunca de `{% static %}`: as
    # duas tags leem prefixos diferentes (`armadilhas/102`).
    re_path(r"^static/(?P<caminho>.*)$", servir_estatico, name="estatico"),
    # A SALA DO ALUNO (degrau 1.8). Duas páginas e dois gestos, todos da
    # PESSOA DA SESSÃO: nenhuma rota recebe o id de outra pessoa, e nenhuma
    # lista alunos ([INV-CUR-P1], `tests/test_inv_p1_nenhuma_tela_compara_alunos.py`).
    #
    # A aula vem DEPOIS de `healthz` e de `static/` de propósito: `<str:numero>`
    # casa qualquer segmento único, e a ordem da lista é o que impede a sonda
    # de virar "aula healthz".
    path("<str:numero>/pausas/<int:ordem>", registrar_pausa, name="registrar-pausa"),
    path(
        "<str:numero>/autoavaliacao", gravar_autoavaliacao, name="gravar-autoavaliacao"
    ),
    # O CHECKPOINT (degrau 2.1): o aluno entrega por link, e volta para a aula.
    path("<str:numero>/checkpoint", entregar_checkpoint, name="entregar-checkpoint"),
    path("<str:numero>", aula, name="aula"),
    # O MAPA DAS PORTAS, e ele é a raiz da célula: `meshcraft.top/cursos` sem
    # mais nada. Vem por último porque `path("")` casa o caminho vazio.
    path("", mapa, name="mapa"),
]
