from django.urls import path, re_path

from apps.core.diagnostico import diag_json
from apps.core.caixa import (
    assinar_obra,
    avaliar_ideia,
    ideia,
    mesa,
    mover_ideia,
    quem_espera,
    travessia,
)
from apps.core.divida import divida_json
from apps.core.mapa_ia import mapa_ia_arquivo, mapa_ia_indice
from apps.core.painel import painel, painel_arquivo
from apps.core.robos import robos
from apps.core.views import (
    escola,
    escola_admin_promover,
    escola_admin_remover,
    escola_aluno_salvar,
    escola_alunos,
    escola_cadastrar,
    escola_jornada,
    escola_decidir,
    escola_prontuario,
    healthz,
    visao_geral,
)

# O urlconf da célula NÃO conhece o prefixo público (`/admin`): quem o aplica é
# `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py`. Mover a área
# administrativa de endereço é editar Traefik + env, nunca cirurgia aqui
# (`armadilhas/029`; guarda em `tests/test_healthz_script_name.py`).
#
# TODA rota desta célula terá `name=`, e nenhum template escreverá caminho à
# mão: é `reverse()`/`{% url %}` quem carrega o prefixo público para dentro do
# endereço. Caminho cravado em string quebra em produção e SÓ lá
# (`armadilhas/081`). O `/healthz` é a exceção que confirma a regra — ele não
# tem `name` porque ninguém o referencia: é endereço de MÁQUINA, fixado por
# contrato com o healthcheck do compose, não por `reverse()`.
urlpatterns = [
    path("healthz", healthz),
    # O PAINEL DO SISTEMA, vivo (`apps/core/painel.py`). A barra final é
    # ESTRUTURAL, não estilo: o HTML pede `manifesto.js` e `registros/*.js` por
    # caminho RELATIVO, e sem ela o navegador os buscaria um nível acima, na
    # raiz da área — a página abriria vazia, sem erro nenhum. Quem manda
    # `/painel` para `/painel/` é o APPEND_SLASH do CommonMiddleware, que já
    # está na cadeia.
    path("painel/", painel, name="painel"),
    # ANTES da rota genérica de arquivo, e a ordem é o que faz funcionar: esta
    # medição não é um arquivo em disco, e a rota de baixo responderia 404 por
    # ela. É a dívida do livro — merges que ninguém contou ao dono —, medida ao
    # vivo (`apps/core/divida.py`).
    path("painel/divida.json", divida_json, name="painel_divida"),
    # Pelo mesmo motivo da linha acima: medição, não arquivo em disco — a rota
    # genérica abaixo responderia 404 por ela. Aqui o SERVIDOR conta o que
    # aconteceu com ele (apps/core/medidor.py): quantas vezes perguntou à
    # identidade, quantas estourou o tempo, quantas ela recusou, e a latência.
    # Sem esta rota, saber isso exige entrar na VPS — e ninguém entra (Lei 5).
    path("painel/diag.json", diag_json, name="painel_diag"),
    re_path(r"^painel/(?P<path>.+)$", painel_arquivo, name="painel_arquivo"),
    # O MAPA PARA IA (`apps/core/mapa_ia.py`) — a ÚNICA área desta célula que
    # responde SEM sessão, além de `/healthz` (INV-P14, `CAMINHOS_ISENTOS` em
    # `apps/core/porta.py`). Nasce fora do prefixo `painel/` de propósito: um
    # nome de rota que começa com `painel/` sinaliza "atrás da porta" em todo
    # o resto deste arquivo, e misturar os dois seria o tipo de detalhe que
    # engana quem lê o diff rápido demais.
    path("mapa-ia/", mapa_ia_indice, name="mapa_ia_indice"),
    re_path(r"^mapa-ia/(?P<nome>[\w.-]+)$", mapa_ia_arquivo, name="mapa_ia_arquivo"),
    # A ESCOLA — o painel do NEGÓCIO, vizinho e separado do painel do SISTEMA
    # acima. Os dois são "painéis" e é por isso que a separação precisa estar
    # no endereço, e não só no texto do link: `/painel/` mostra como a
    # plataforma está sendo construída (o livro de ocorrências); `/escola/`
    # mostra a escola funcionando — alunos, e o que vier depois deles.
    #
    # Barra final nas duas, e aqui ela é só convenção (nenhuma delas pede
    # arquivo por caminho relativo) — mas convenção MISTURADA é o que produz
    # link quebrado quando alguém copia a linha de cima. O APPEND_SLASH já
    # cuida de quem digitar sem a barra.
    # A CAIXA DE SUGESTOES — a gestao das ideias dos alunos, que ate 28/08/2026
    # morava nas telas da celula sugestoes. Decisao do mantenedor, na frase
    # dele: "nao vamos espalhar paineis ou gestao por ai, tudo sera em /admin".
    # Lei: docs/decisoes/DECISAO-a-gestao-da-caixa-mora-no-admin.md.
    #
    # NAO fica sob /painel/: aquele prefixo ja tem dono (o livro do projeto, e a
    # rota generica de arquivo acima engoliria qualquer irmao). Fica ao lado de
    # /escola/, na mesma gramatica — e com barra final, pela mesma convencao.
    #
    # Pela Lei 3 esta celula nao le o banco da Caixa: ela pergunta, pelo
    # contrato congelado (contracts/sugestoes.openapi.yaml).
    path("caixa/", mesa, name="caixa"),
    path("caixa/travessia/", travessia, name="caixa_travessia"),
    path("caixa/esperando/", quem_espera, name="caixa_esperando"),
    # A aba 4 — "Os robôs": o quadro da fila de trabalho (fila/ na raiz),
    # embutida no build como o painel. Esperada desde 28/08/2026; a fonte
    # nasceu em 29/08 e a aba nasceu junto (apps/core/robos.py).
    path("caixa/robos/", robos, name="caixa_robos"),
    # A ideia por dentro, e as tres acoes. Elas sao POST de propósito: mudam
    # coisa, e um GET seria disparado por qualquer pre-carregamento de link do
    # navegador. Depois de agir, tudo redireciona de volta para a ideia — e o
    # redirecionamento e o que impede o F5 de repetir a acao.
    path("caixa/ideia/<int:ideia_id>/", ideia, name="caixa_ideia"),
    path("caixa/ideia/<int:ideia_id>/fase", mover_ideia, name="caixa_mover"),
    path("caixa/ideia/<int:ideia_id>/avaliacao", avaliar_ideia, name="caixa_avaliar"),
    path("caixa/ideia/<int:ideia_id>/assinatura", assinar_obra, name="caixa_assinar"),
    path("escola/", escola, name="escola"),
    # [JORNADA] O mapa, com os numeros de agora
    # (`DECISAO-o-mapa-da-jornada-do-aluno.md`). Vizinho da lista e nao dentro
    # dela: sao perguntas diferentes — "como funciona a escola?" e "quem esta
    # nela?" — e o mapa precisa abrir sem que ninguem role uma lista.
    path("escola/jornada/", escola_jornada, name="escola_jornada"),
    path("escola/alunos/", escola_alunos, name="escola_alunos"),
    # [PRONTUARIO] A historia de UMA pessoa (`DECISAO-a-ficha-nao-se-apaga` §5).
    # GET, e o e-mail vem por querystring: esta tela so PERGUNTA, nao decide
    # nada — e um e-mail no caminho da URL exigiria escapar barra e ponto para
    # nada, ja que quem autoriza e a porta, na entrada.
    path("escola/alunos/prontuario", escola_prontuario, name="escola_prontuario"),
    # A ÚNICA rota de escrita desta célula. POST-only (`require_POST` na view):
    # decisão que se aplica por GET é decisão que um pré-carregador de link, um
    # antivírus corporativo ou um crawler autenticado tomam sozinhos — e aqui
    # ela muda a vida de uma pessoa. Sem barra final e sem id no caminho: o
    # alvo vem no corpo do formulário, junto do CSRF que o protege.
    path("escola/alunos/decidir", escola_decidir, name="escola_decidir"),
    # A segunda rota de escrita: o formulario de gestao de quem JA e aluno.
    # POST-only pelo mesmo motivo da de cima.
    path("escola/alunos/salvar", escola_aluno_salvar, name="escola_aluno_salvar"),
    # [A MAO] Por uma pessoa na escola sem esperar que ela peca
    # (`DECISAO-cadastrar-alguem-a-mao.md`). POST, como todo gesto que muda a
    # vida de alguem — decisao que se aplica por GET e decisao que um
    # pre-carregador de link toma sozinho.
    path("escola/alunos/cadastrar", escola_cadastrar, name="escola_cadastrar"),
    # As escritas de PODER da DECISAO-administradores-e-apagar. POST-only,
    # pelo mesmo motivo das outras.
    #
    # A rota `escola/alunos/apagar` NAO existe mais, e a ausencia e a lei:
    # `DECISAO-a-ficha-nao-se-apaga.md` (29/08/2026) tirou do sistema a
    # capacidade de apagar uma ficha — aqui, e na porta da `alunos` que ela
    # chamava. Tirar o acesso e o estado `Ex-aluno`, no formulario de gestao.
    path("escola/admin/promover", escola_admin_promover, name="escola_admin_promover"),
    path("escola/admin/remover", escola_admin_remover, name="escola_admin_remover"),
    path("", visao_geral, name="visao_geral"),
]
