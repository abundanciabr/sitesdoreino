from django.urls import path, re_path

from apps.core.avisos import marcar_lido, marcar_tudo_lido, ver_avisos
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
    # A GESTÃO MUDOU DE CASA (28/08/2026, no mesmo dia em que nasceu aqui).
    # Ela mora em /admin/caixa/ por decisão do mantenedor — uma porta só. Lei:
    # docs/decisoes/DECISAO-a-gestao-da-caixa-mora-no-admin.md.
    #
    # Os endereços continuam vivos e redirecionam (301). Apagá-los puniria quem
    # salvou o endereço — e quem salvou foi justamente quem mais usava a tela.
    #
    # Eles continuam ATRÁS DO CRACHÁ: quem não é da equipe leva 403 antes de
    # saber para onde a gestão foi. O redirecionamento é uma cortesia para quem
    # já tinha acesso, nunca um mapa para quem não tem.
    path("gestao", mudou_de_casa, name="mesa"),
    path("gestao/travessia", mudou_de_casa, name="travessia"),
    path("gestao/esperando", mudou_de_casa, name="quem_espera"),
    # A MODERAÇÃO TAMBÉM MUDOU DE CASA (30/08/2026, TAR-023 degrau 4) — e ela
    # foi a última, dois dias depois das três abas acima. O atraso não foi
    # esquecimento: das cinco rotas daqui, quatro já tinham paridade no Admin, e
    # a quinta (o corredor do ChangeSpec) mostrava uma coisa que o Admin não
    # sabia dizer — COM BASE EM QUE cada obra foi liberada. Aposentá-la antes
    # disso teria apagado a única forma de auditar a trava mais dura da célula.
    # O robô da TAR-014 parou aqui e registrou (`20260830-019`); a emenda que
    # destravou é a 4ª do contrato (PR #581), e o Admin passou a mostrar a ficha
    # em `/admin/caixa/ideia/<id>`.
    #
    # Mesmo molde das três de cima, e pelos mesmos motivos: os endereços
    # CONTINUAM VIVOS e redirecionam (301) — apagá-los puniria quem os salvou, e
    # quem salvou foi quem mais usava a tela —, e continuam ATRÁS DO CRACHÁ:
    # quem não é da equipe leva 403 antes de saber para onde a gestão foi.
    #
    # As três rotas de ESCRITA (status, avaliação, changespec) recusam POST com
    # uma frase em português em vez de redirecionar: uma aba velha ainda aberta
    # precisa saber que o que ela enviou NÃO foi salvo, e um 301 num POST vira
    # um GET silencioso no destino — a pessoa veria a página nova e acharia que
    # deu certo (`apps/core/mudou_de_casa.py`).
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
