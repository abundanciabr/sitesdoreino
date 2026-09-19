from django.urls import path

from apps.core import telas_do_cliente
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
#
# AS TELAS DO CLIENTE (Fase 3) ENTRAM AQUI, E UMA ROTA FALTA DE PROPÓSITO:
# **não existe rota de pagar.** A pausa financeira de 22/08/2026 continua, e
# uma rota que respondesse "ainda não" seria uma promessa com data. O que não
# existe responde 404, e 404 não promete nada. O guarda que mede essa ausência é
# `tests/test_cliente_nao_paga_nem_ve_contato.py`, e ele percorre os endereços
# que alguém escreveria por instinto. Quem registra "pago pela escola" é o
# plantão, com autor e data (lei §3.4).
urlpatterns = [
    path("healthz", healthz),
    path("plantao", plantao, name="plantao"),
    path("plantao/titulo", dar_titulo, name="plantao_titulo"),
    path("cardapio", telas_do_cliente.cardapio_do_cliente, name="cardapio_do_cliente"),
    path("cardapio/<str:cartao>", telas_do_cliente.briefing, name="briefing"),
    path(
        "cardapio/<str:cartao>/pedir",
        telas_do_cliente.abrir_pedido,
        name="abrir_pedido",
    ),
    path("pedidos/<uuid:encomenda_id>", telas_do_cliente.pedido, name="pedido"),
    path(
        "pedidos/<uuid:encomenda_id>/aceitar",
        telas_do_cliente.aceitar_proposta,
        name="aceitar_proposta",
    ),
    path(
        "pedidos/<uuid:encomenda_id>/contrapor",
        telas_do_cliente.contrapor,
        name="contrapor",
    ),
    path(
        "pedidos/<uuid:encomenda_id>/desistir",
        telas_do_cliente.desistir_da_negociacao,
        name="desistir_da_negociacao",
    ),
    path(
        "pedidos/<uuid:encomenda_id>/aprovar",
        telas_do_cliente.aprovar_entrega,
        name="aprovar_entrega",
    ),
    path(
        "pedidos/<uuid:encomenda_id>/ajuste",
        telas_do_cliente.pedir_ajuste,
        name="pedir_ajuste",
    ),
    path(
        "pedidos/<uuid:encomenda_id>/cancelar",
        telas_do_cliente.cancelar_pedido,
        name="cancelar_pedido",
    ),
    path("api/encomendas/", api.urls),
]
