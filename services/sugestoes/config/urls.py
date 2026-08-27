from django.urls import path, re_path

from apps.core.avisos import marcar_lido, marcar_tudo_lido, ver_avisos
from apps.core.changespecs import changespecs
from apps.core.moderacao import avaliar, moderar, mudar_status, ver_fila
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
    # O rosto (EVO-30). Rota de MÁQUINA, como o `/healthz`: sem ela o CSS é 404
    # em produção e SÓ lá (`armadilhas/083` — com DEBUG=0 o Django não serve
    # estático, e não há nginx nem CDN atrás do Traefik).
    #
    # O nome é `estatico`, e não `static`, de propósito: os templates o chamam
    # por `{% url 'estatico' … %}`, e `{% url 'static' … %}` ao lado do
    # `{% static %}` do Django seriam duas coisas diferentes com o mesmo nome na
    # mesma linha. **É `{% url %}` e não `{% static %}` porque só o primeiro
    # carrega o prefixo público**: `/static/caixa.css` em `meshcraft.top` é
    # endereço do `funil`, não da Caixa (`armadilhas/029` e `/081`).
    re_path(r"^static/(?P<caminho>.*)$", servir_estatico, name="estatico"),
    # Superfície de MÁQUINA (DECISAO-onde-mora-a-sessao): o `funil` pergunta
    # quem é o dono da sessão. Prefixo `interno/` no nome porque é assim que a
    # fronteira fica legível no urlconf — do mesmo jeito que `moderacao/`
    # deixa visível a fronteira do crachá, e não só no decorador. Não confundir
    # com as rotas de GENTE abaixo: esta não renderiza página nenhuma e exige
    # Bearer do par consumidor.
    path("interno/", api.urls),
    path("", ver_quadro, name="quadro"),
    path("entrar", entrar, name="entrar"),
    # A fila de liberacao (DECISAO-fila-de-liberacao.md). POST, e nao GET,
    # porque cria uma linha na fila do mantenedor: um GET seria disparado por
    # qualquer pre-carregamento de link do navegador. A TELA do formulario nao
    # tem rota propria — ela e a propria porta, no estado SEM_MATRICULA, que e
    # a decisao de "uma tela so" da lei §6.
    path("entrar/pedido", pedir_entrada, name="pedir_entrada"),
    path("entrar/google", entrar_google, name="entrar_google"),
    path("entrar/google/retorno", entrar_google_retorno, name="entrar_google_retorno"),
    path("sair", sair, name="sair"),
    path("sugestoes/nova", nova_sugestao, name="nova_sugestao"),
    path("sugestoes/<int:sugestao_id>", ver_sugestao, name="sugestao"),
    path("sugestoes/<int:sugestao_id>/votar", votar, name="votar"),
    path("sugestoes/<int:sugestao_id>/desvotar", desvotar, name="desvotar"),
    path("sugestoes/<int:sugestao_id>/comentarios", comentar, name="comentar"),
    # O sininho (EVO-21). Prefixo próprio, como a moderação: `/avisos` é do
    # ALUNO e só dele — cada rota daqui enxerga exclusivamente os avisos de quem
    # está na sessão (apps/core/avisos.py). Marcar como lido é POST, e não GET,
    # porque muda estado: um GET seria marcado como lido por qualquer
    # pré-carregamento de link do navegador.
    #
    # `<str:aviso_id>`, não `<int:...>` — desde a Fase 3/4 do sininho o `id` de
    # um aviso é o valor OPACO que `GET /avisos` devolve (a caixa central,
    # `contracts/notificacoes.openapi.yaml`), não mais o pk local desta célula.
    # Tratá-lo como inteiro seria a Caixa inventando uma forma que a porta de
    # fora não promete.
    path("avisos", ver_avisos, name="avisos"),
    path("avisos/marcar-tudo", marcar_tudo_lido, name="marcar_todos_avisos_lidos"),
    path("avisos/<str:aviso_id>/lido", marcar_lido, name="marcar_aviso_lido"),
    # A moderação (EVO-13) mora sob um prefixo próprio, `/moderacao`, e não
    # espalhada por `/sugestoes/<id>/...`: assim a fronteira do crachá é legível
    # no urlconf, e não só no decorador. Toda rota daqui responde **403** a quem
    # tem sessão sem papel `staff` (apps/core/moderacao.py).
    path("moderacao", ver_fila, name="fila"),
    path("moderacao/<int:sugestao_id>", moderar, name="moderar"),
    path("moderacao/<int:sugestao_id>/status", mudar_status, name="mudar_status"),
    path("moderacao/<int:sugestao_id>/avaliacao", avaliar, name="avaliar"),
    # O corredor do ChangeSpec (EVO-40). Mora sob `/moderacao` porque é tela da
    # EQUIPE — e é a única rota da célula com um SEGUNDO portão em cima do
    # crachá: só quem está em `SUGESTOES_APROVADORES` passa
    # (`apps/core/changespecs.py`). Uma rota para os dois métodos, de propósito:
    # o GET é a página, o POST é o formulário dela mesma. Duas rotas seriam
    # duas entradas a mais em cada varredura de urlconf desta célula para
    # servir uma tela só.
    path(
        "moderacao/<int:sugestao_id>/changespec",
        changespecs,
        name="changespecs",
    ),
]
