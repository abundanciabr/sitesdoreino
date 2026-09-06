from django.urls import path

from apps.core.views import healthz, prancheta
from config.api import api

# O urlconf da célula NÃO conhece o prefixo público: quem o aplica é
# `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py`. Mover a célula de
# endereço é editar Traefik + env, nunca cirurgia aqui (`armadilhas/029`;
# guarda em `tests/test_healthz_script_name.py`).
#
# Esta casa tem DOIS endereços públicos (`PLANO-PORTFOLIO-DO-ALUNO.md` §4):
# `/pages/...` para o aluno logado e `/estudio/<apelido>` para a vitrine que
# ele manda ao cliente. Qual dos dois vira `SCRIPT_NAME` e como o outro chega
# até aqui é decisão do degrau 05 (o PR do Traefik e do compose), e o motivo
# de ela não estar tomada nesta gênese está escrito em `config/settings.py`.
#
# Quando as telas nascerem (degrau 06, a porta e a tela mínima; 07, a
# Prancheta; 08, as peças por link; 11, a fila da equipe; 13, a vitrine): TODA
# rota leva `name=`, e nenhum template escreve caminho à mão — é
# `reverse()`/`{% url %}` quem carrega o prefixo público para dentro do
# endereço. Caminho cravado em string quebra em produção e SÓ lá
# (`armadilhas/029` e `/081`).
#
# E quando houver CSS: a rota `servir_estatico` é obrigatória, com nome próprio
# (`estatico`), porque com DEBUG=0 o Django não serve estático e não há nginx
# nem CDN atrás do Traefik — o arquivo vira 404 em produção e SÓ lá
# (`armadilhas/083`). Sob prefixo, o `<link>` sai de `{% url 'estatico' %}` e
# **nunca** de `{% static %}` (`armadilhas/102`). O molde vivo está em
# `services/forum` e `services/cursos`.
#
# A PORTA DE MÁQUINA nasceu no degrau 03, e mora em `/interno/`, o mesmo
# endereço que o `forum`, a `identidade` e a `sugestoes` usam. Nesta célula esse
# caminho FICA DEBAIXO do prefixo roteado: `meshcraft.top/pages/interno/…` é
# alcançável pela internet, porque o corte do prefixo é do Django, não do
# Traefik (`armadilhas/186`). Quem fecha a porta é o Bearer do par, e o guarda
# que importa é o teste de 401 em TODAS as operações
# (`tests/test_porta_de_maquina.py`); a topologia não fecha nada aqui, e
# escrever o contrário no comentário seria ensinar errado quem chegar depois.
urlpatterns = [
    path("healthz", healthz),
    path("interno/", api.urls),
    # A RAIZ do prefixo, que pela borda pública é `meshcraft.top/pages/`: a
    # tela mínima do degrau 06. Ela leva `name=` como toda rota desta casa, e
    # é por `{% url 'prancheta' %}` que o prefixo entra no endereço, nunca por
    # caminho cravado em string (`armadilhas/029` e `/081`).
    #
    # Vem por ÚLTIMA de propósito: `path("")` casa com a raiz, e as duas rotas
    # de máquina acima precisam ser encontradas antes de qualquer coisa
    # declarada na raiz do urlconf.
    path("", prancheta, name="prancheta"),
]
