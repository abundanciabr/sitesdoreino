from django.urls import path

from apps.core import telas_do_cliente, telas_marketplace
from apps.core.views import dar_titulo, healthz, plantao
from config.api import api

# O urlconf da célula NÃO conhece o prefixo público (`/encomendas`): quem o
# aplica é `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py`. Mover a
# célula de endereço é editar Traefik + env, nunca cirurgia aqui.
#
# TODA rota leva `name=`, e nenhum template escreve caminho à mão: é
# `reverse()`/`{% url %}` quem carrega o prefixo público para dentro do
# endereço. Caminho cravado em string quebra em produção e SÓ lá.
#
# E quando houver CSS: a rota `servir_estatico` é obrigatória, com nome próprio
# (`estatico`), porque com DEBUG=0 o Django não serve estático e não há nginx
# nem CDN atrás do Traefik, e o arquivo vira 404 em produção e SÓ lá.
# Sob prefixo, o `<link>` sai de `{% url 'estatico' %}` e
# **nunca** de `{% static %}`. A tela do plantão que nasce
# aqui não tem arquivo de estilo de propósito: ela é o mínimo da lei §3.6 e
# §3.4, e a tela cheia do plantão é a Fase 7.
#
# A PORTA DE MAQUINA (degrau 2.7) mora em `api/encomendas/`, e o `/interno/` do
# contrato é um caminho DENTRO dela. Nesta célula esses caminhos ficam DEBAIXO
# do prefixo roteado: `meshcraft.top/encomendas/api/encomendas/interno/...` é
# alcançável pela internet, porque o corte do prefixo é do Django e não do
# Traefik. Quem fecha a porta é o Bearer do par, e o guarda
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
    path("escola/", telas_marketplace.escola, name="marketplace_escola"),
    path("escola/autorizar/<str:tipo>/", telas_marketplace.autorizar, name="marketplace_autorizar"),
    path("escola/fase/<str:tipo>/", telas_marketplace.alterar_fase, name="marketplace_alterar_fase"),
    path("fila/", telas_marketplace.fila, name="marketplace_fila"),
    path("fila/disponibilidade/", telas_marketplace.disponibilidade, name="marketplace_disponibilidade"),
    path("fila/ofertas/<uuid:oferta_id>/<str:acao>/", telas_marketplace.responder_oferta, name="marketplace_responder_oferta"),
    path("cliente/", telas_marketplace.cliente, name="marketplace_cliente"),
    path("cliente/novo/", telas_marketplace.novo, name="marketplace_novo"),
    path("cliente/salvar/", telas_marketplace.salvar, name="marketplace_salvar"),
    path("cliente/autosave/", telas_marketplace.autosave, name="marketplace_autosave"),
    path("cliente/pedidos/<uuid:pedido_id>/editar/", telas_marketplace.editar, name="marketplace_editar"),
    path("cliente/pedidos/<uuid:pedido_id>/salvar/", telas_marketplace.salvar, name="marketplace_salvar_edicao"),
    path("cliente/pedidos/<uuid:pedido_id>/repetir/", telas_marketplace.repetir, name="marketplace_repetir"),
    path("cliente/pedidos/<uuid:pedido_id>/publicar/", telas_marketplace.publicar, name="marketplace_publicar"),
    path("cliente/pedidos/<uuid:pedido_id>/cobrar/", telas_marketplace.cobrar, name="marketplace_cobrar"),
    path("cliente/pedidos/<uuid:pedido_id>/confirmar-paypal/", telas_marketplace.confirmar_paypal, name="marketplace_confirmar_paypal"),
    path("cliente/pedidos/<uuid:pedido_id>/retorno-paypal/", telas_marketplace.retorno_paypal, name="marketplace_retorno_paypal"),
    path("cliente/pedidos/<uuid:pedido_id>/", telas_marketplace.pedido_cliente, name="marketplace_pedido_cliente"),
    path("marketplace/pedidos/<uuid:pedido_id>/", telas_marketplace.pedido, name="marketplace_pedido"),
    path("marketplace/pedidos/<uuid:pedido_id>/mensagem/", telas_marketplace.mensagem, name="marketplace_mensagem"),
    path("marketplace/pedidos/<uuid:pedido_id>/arquivo/", telas_marketplace.enviar_arquivo, name="marketplace_arquivo"),
    path("marketplace/arquivos/<uuid:arquivo_id>/", telas_marketplace.baixar_arquivo, name="marketplace_baixar"),
    path("marketplace/pedidos/<uuid:pedido_id>/entregar/", telas_marketplace.entregar, name="marketplace_entregar"),
    path("marketplace/pedidos/<uuid:pedido_id>/<str:acao>/", telas_marketplace.avaliar, name="marketplace_avaliar"),
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

handler404 = "site_errors.handlers.page_not_found_shared"
handler500 = "site_errors.handlers.server_error_shared"
