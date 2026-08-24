from django.urls import path

from apps.core.moderacao import avaliar, moderar, mudar_status, ver_fila
from apps.core.participacao import (
    comentar,
    desvotar,
    nova_sugestao,
    ver_quadro,
    ver_sugestao,
    votar,
)
from apps.core.views import entrar, entrar_google, entrar_google_retorno, healthz, sair

# O urlconf da célula NÃO conhece o prefixo público (/forms/sugestoes): quem o
# aplica é FORCE_SCRIPT_NAME, lido do env em config/settings.py. Mover a Caixa
# de URL é editar Traefik + env, nunca cirurgia aqui.
#
# TODA rota TEM nome (`name=`), e nenhum template escreve caminho à mão: é
# `reverse()`/`{% url %}` quem carrega o prefixo público para dentro do
# endereço. Caminho cravado em string quebra em produção e SÓ lá
# (armadilhas/029 e /081; tests/test_entrada_script_name.py e
# tests/test_participacao_script_name.py).
#
# A raiz é o quadro desde o EVO-12b, como o EVO-12a já previa: quem entra quer
# ver o que os outros pediram. `/entrar` continua respondendo e continua sendo
# o destino de quem chega sem sessão — inclusive na raiz, que exige sessão como
# todo o resto da participação (apps/core/participacao.py).
urlpatterns = [
    path("healthz", healthz),
    path("", ver_quadro, name="quadro"),
    path("entrar", entrar, name="entrar"),
    path("entrar/google", entrar_google, name="entrar_google"),
    path("entrar/google/retorno", entrar_google_retorno, name="entrar_google_retorno"),
    path("sair", sair, name="sair"),
    path("sugestoes/nova", nova_sugestao, name="nova_sugestao"),
    path("sugestoes/<int:sugestao_id>", ver_sugestao, name="sugestao"),
    path("sugestoes/<int:sugestao_id>/votar", votar, name="votar"),
    path("sugestoes/<int:sugestao_id>/desvotar", desvotar, name="desvotar"),
    path("sugestoes/<int:sugestao_id>/comentarios", comentar, name="comentar"),
    # A moderação (EVO-13) mora sob um prefixo próprio, `/moderacao`, e não
    # espalhada por `/sugestoes/<id>/...`: assim a fronteira do crachá é legível
    # no urlconf, e não só no decorador. Toda rota daqui responde **403** a quem
    # tem sessão sem papel `staff` (apps/core/moderacao.py).
    path("moderacao", ver_fila, name="fila"),
    path("moderacao/<int:sugestao_id>", moderar, name="moderar"),
    path("moderacao/<int:sugestao_id>/status", mudar_status, name="mudar_status"),
    path("moderacao/<int:sugestao_id>/avaliacao", avaliar, name="avaliar"),
]
