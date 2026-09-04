from django.urls import path

from apps.core.views import healthz

# O urlconf da célula NÃO conhece o prefixo público (`/encomendas`): quem o
# aplica é `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py`. Mover a
# célula de endereço é editar Traefik + env, nunca cirurgia aqui
# (`armadilhas/029`; guarda em `tests/test_healthz_script_name.py`).
#
# Quando as telas nascerem (Fases 3 e 4 da lei — o aluno em `/encomendas`, o
# cliente em `/encomendas/pedir`, o plantão em `/encomendas/plantao`): TODA
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
# `services/forum` e `services/gamificacao`.
#
# E quando a porta de MÁQUINA nascer (degrau 2.7 — `getParameters`,
# `getQueueStanding`, `getApprovedPieces`, `confirmPayment`, `reportAudit`):
# ela mora em `/api/encomendas/` e `/interno/`, e nesta célula esses caminhos
# FICAM DEBAIXO do prefixo roteado. Ou seja, `meshcraft.top/encomendas/interno/…`
# é alcançável pela internet — o corte do prefixo é do Django, não do Traefik
# (`armadilhas/186`). Quem fecha a porta é o Bearer do par, e o guarda que
# importa é o teste de 401 em TODAS as operações; a topologia não fecha nada
# aqui, e escrever o contrário no comentário seria ensinar errado quem chegar
# depois.
urlpatterns = [
    path("healthz", healthz),
]
