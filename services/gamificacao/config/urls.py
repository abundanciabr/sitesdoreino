from django.urls import path, re_path

from apps.core.views import base, healthz, servir_estatico
from config.api import api

# O urlconf da célula NÃO conhece o prefixo público (`/conquistas`): quem o
# aplica é `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py`. Mover a
# célula de endereço é editar Traefik + env, nunca cirurgia aqui
# (`armadilhas/029`; guarda em `tests/test_healthz_script_name.py`).
#
# Quando as telas nascerem (PR 7 da escada — a Base, o Passaporte, a loja):
# TODA rota leva `name=`, e nenhum template escreve caminho à mão — é
# `reverse()`/`{% url %}` quem carrega o prefixo público para dentro do
# endereço. Caminho cravado em string quebra em produção e SÓ lá
# (`armadilhas/029` e `/081`).
#
# E quando houver CSS: a rota `servir_estatico` é obrigatória, com nome próprio
# (`estatico`), porque com DEBUG=0 o Django não serve estático e não há nginx
# nem CDN atrás do Traefik — o arquivo vira 404 em produção e SÓ lá
# (`armadilhas/083`). Sob prefixo, o `<link>` sai de `{% url 'estatico' %}` e
# **nunca** de `{% static %}`: as duas tags leem prefixos diferentes, e
# `/static/…` em `meshcraft.top` é endereço do `funil`, não desta célula
# (`armadilhas/102`). O molde vivo está em `services/forum`.
#
# A porta de MÁQUINA (PR 16 — `getPublicProfiles`, `getMyStatus`) nasceu aqui
# embaixo, e o endereço dela NÃO é o que este comentário previa na gênese.
#
# A gênese escreveu `/interno/` (o formato de `identidade` e `forum`). O
# contrato foi congelado na Sessão B de 30/08/2026 com
# `servers: http://gamificacao:8000/api/gamificacao` (o formato de `alunos`,
# `catalogo` e `notificacoes`), e o cabeçalho do contrato registra a divergência
# de propósito, resolvendo-a: **o contrato vence**. Trocar o endereço depois é
# Rito de Contrato (RITOS.md §3), não preferência de sessão.
#
# O que a gênese acertou, e continua valendo: nesta célula o caminho FICA
# DEBAIXO do prefixo roteado. `meshcraft.top/conquistas/api/gamificacao/…` é
# alcançável pela internet — o corte do prefixo é do Django, não do Traefik
# (`armadilhas/186`; premissa fixada em
# `tests/test_healthz_script_name.py::test_o_prefixo_alcanca_a_raiz_do_urlconf`).
# Quem fecha a porta é o Bearer do par, e o guarda que importa é o teste de 401
# em TODAS as operações (`tests/test_porta_de_maquina.py`); a topologia não
# fecha nada aqui, e escrever o contrário no comentário seria ensinar errado
# quem chegar depois.
urlpatterns = [
    path("healthz", healthz),
    path("api/gamificacao/", api.urls),
    # O CSS, servido pela própria célula. Sem esta rota o estilo é 404 em
    # produção e SÓ lá (`armadilhas/083`): com DEBUG=0 o Django não serve
    # estático, e não há nginx nem CDN atrás do Traefik.
    re_path(r"^static/(?P<caminho>.*)$", servir_estatico, name="estatico"),
    # A BASE, e ela é a raiz da célula: `meshcraft.top/conquistas` sem mais
    # nada. Nomeada, como todas: é `{% url 'base' %}` quem carrega o prefixo
    # público para dentro do endereço. Vem por último porque `path("")` casa o
    # caminho vazio, e ler a lista de cima para baixo é como se confere isto.
    path("", base, name="base"),
]
