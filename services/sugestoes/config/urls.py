from django.urls import path, re_path

from apps.core.avisos import ver_avisos
from apps.core.mudou_de_casa import mudou_de_casa
from apps.core.participacao import (
    comentar,
    desvotar,
    nova_sugestao,
    ver_quadro,
    ver_sugestao,
    votar,
)
from apps.core.views import (
    entrar,
    entrar_google,
    entrar_google_retorno,
    healthz,
    pedir_entrada,
    sair,
    servir_estatico,
)
from config.api import api

# O prefixo público vem de FORCE_SCRIPT_NAME: as rotas daqui não o conhecem.
# Toda rota tem nome e os templates usam `reverse()`, nunca caminho escrito à mão.
urlpatterns = [
    path("healthz", healthz),
    # Serve o CSS da célula: com DEBUG desligado o Django não serve estático.
    # Os templates usam `{% url 'estatico' %}` porque só ele leva o prefixo público.
    re_path(r"^static/(?P<caminho>.*)$", servir_estatico, name="estatico"),
    # Rota de máquina: o `funil` pergunta quem é o dono da sessão (Bearer do par).
    path("interno/", api.urls),
    path("", ver_quadro, name="quadro"),
    path("entrar", entrar, name="entrar"),
    # POST que cria a linha na fila de liberação; a tela é a própria porta.
    path("entrar/pedido", pedir_entrada, name="pedir_entrada"),
    path("entrar/google", entrar_google, name="entrar_google"),
    path("entrar/google/retorno", entrar_google_retorno, name="entrar_google_retorno"),
    path("sair", sair, name="sair"),
    path("sugestoes/nova", nova_sugestao, name="nova_sugestao"),
    path("sugestoes/<int:sugestao_id>", ver_sugestao, name="sugestao"),
    path("sugestoes/<int:sugestao_id>/votar", votar, name="votar"),
    path("sugestoes/<int:sugestao_id>/desvotar", desvotar, name="desvotar"),
    path("sugestoes/<int:sugestao_id>/comentarios", comentar, name="comentar"),
    # `/avisos` redireciona para a página única `/notificacoes`.
    path("avisos", ver_avisos, name="avisos"),
    # A gestão mora em `/admin/caixa/`: estes endereços redirecionam (301).
    path("gestao", mudou_de_casa, name="mesa"),
    path("gestao/travessia", mudou_de_casa, name="travessia"),
    path("gestao/esperando", mudou_de_casa, name="quem_espera"),
    # A moderação também mora no Admin: os endereços redirecionam (301).
    # As rotas de escrita recusam POST com uma frase, pois nada foi salvo.
    path("moderacao", mudou_de_casa, name="fila"),
    path("moderacao/<int:sugestao_id>", mudou_de_casa, name="moderar"),
    path("moderacao/<int:sugestao_id>/status", mudou_de_casa, name="mudar_status"),
    path("moderacao/<int:sugestao_id>/avaliacao", mudou_de_casa, name="avaliar"),
    path(
        "moderacao/<int:sugestao_id>/changespec",
        mudou_de_casa,
        name="changespecs",
    ),
]

handler404 = "site_errors.handlers.page_not_found_shared"
handler500 = "site_errors.handlers.server_error_shared"
