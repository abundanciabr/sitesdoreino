from django.urls import path, re_path

from apps.core.diagnostico import diag_json
from apps.core.caixa import (
    apagar_ideia,
    arquivar_ideia,
    assinar_obra,
    avaliar_ideia,
    corrigir_ideia,
    desarquivar_ideia,
    exportar,
    ideia,
    mesa,
    mover_ideia,
    quem_espera,
    travessia,
)
from apps.core.divida import divida_json
from apps.core.editor_de_documentos import (
    documento_apagar,
    documento_arquivar,
    documento_criar,
    documento_desarquivar,
    documento_editar,
    documento_novo,
    documento_restaurar,
    documento_salvar,
    documento_versoes,
)
from apps.core.mapa_do_site import mapa_do_site
from apps.core.economia import (
    economia,
    economia_mudar,
    economia_mudar_conquista,
    economia_mudar_degrau,
)
from apps.core.menu import (
    menu_adicionar_item,
    menu_apagar_versao,
    menu_criar_versao,
    menu_do_topo,
    menu_mover_item,
    menu_regras_das_paginas,
    menu_remover_item,
    menu_versao_padrao,
)
from apps.core.mapa_ia import mapa_ia_arquivo, mapa_ia_indice
from apps.core.planos_para_ia import plano_publico, planos_indice
from apps.core.painel import painel, painel_arquivo
from apps.core.robos import robos
from apps.core.views import (
    escola,
    escola_admin_promover,
    escola_admin_remover,
    escola_aluno_salvar,
    doc_publico,
    docs_publicos,
    documento_admin,
    documentos_admin,
    escola_alunos,
    escola_alunos_liberados,
    escola_cadastrar,
    escola_jornada,
    escola_decidir,
    escola_prontuario,
    escola_resetar_senha,
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
    # O MAPA DO SITE (`apps/core/mapa_do_site.py`, 30/08/2026) — todo endereço
    # que a plataforma tem, numa página só, em português.
    #
    # FORA do prefixo `painel/`: a rota genérica logo acima engoliria qualquer
    # irmão dele (ela casa `painel/<qualquer coisa>`), e este mapa não é uma
    # peça do painel — é uma tela da área, vizinha da escola e da Caixa.
    #
    # Barra final pela convenção das outras telas; quem chega sem ela é
    # redirecionado pelo APPEND_SLASH, que já está na cadeia.
    path("mapa/", mapa_do_site, name="mapa_do_site"),
    # O MENU DO TOPO (`apps/core/menu.py`, 31/08/2026) — a tela em que o
    # mantenedor decide o que aparece no alto de cada página do site, e em
    # quais páginas não aparece nada.
    #
    # FORA do prefixo `painel/` pelo mesmo motivo do mapa acima: a rota
    # genérica `painel/<qualquer coisa>` engoliria qualquer irmão dela, e esta
    # não é uma peça do painel — é uma tela da área, vizinha do mapa.
    #
    # Barra final pela convenção das outras telas; quem chega sem ela é
    # redirecionado pelo APPEND_SLASH, que já está na cadeia.
    #
    # Os SETE gestos têm rota própria, e isso não é enfeite: com um POST só e
    # um campo escondido dizendo "o que fazer", a auditoria e o CSRF passariam
    # a depender de um valor de formulário, e a leitura deste arquivo deixaria
    # de contar o que a tela faz. Cada rota é um verbo.
    path("menu/", menu_do_topo, name="menu_do_topo"),
    path("menu/versao/criar", menu_criar_versao, name="menu_criar_versao"),
    path("menu/versao/apagar", menu_apagar_versao, name="menu_apagar_versao"),
    path("menu/versao/padrao", menu_versao_padrao, name="menu_versao_padrao"),
    path("menu/item/acrescentar", menu_adicionar_item, name="menu_adicionar_item"),
    path("menu/item/remover", menu_remover_item, name="menu_remover_item"),
    path("menu/item/mover", menu_mover_item, name="menu_mover_item"),
    path("menu/paginas", menu_regras_das_paginas, name="menu_regras_das_paginas"),
    # A ECONOMIA (`apps/core/economia.py`, 31/08/2026) — a tela em que o
    # mantenedor liga e desliga cada regra de pontuacao da escola. Ela existe
    # porque a lei da gamificacao (§10.5) chama de CRITERIO DE MORTE o dia em
    # que ajustar a economia passar a exigir PR de codigo. Duas rotas: a tela e
    # o gesto, com verbo proprio, na mesma gramatica das sete do menu.
    path("economia/", economia, name="economia"),
    path("economia/mudar", economia_mudar, name="economia_mudar"),
    # A segunda metade da mesma tela (01/09/2026): as medalhas e os marcos. Rota
    # PROPRIA e nao um campo a mais no gesto de cima, porque sao duas listas
    # diferentes do outro lado e dois verbos diferentes na auditoria.
    path(
        "economia/mudar-conquista",
        economia_mudar_conquista,
        name="economia_mudar_conquista",
    ),
    # [DEGRAUS] 02/09/2026: o terceiro interruptor, e o unico que nao paga nada.
    path(
        "economia/mudar-degrau",
        economia_mudar_degrau,
        name="economia_mudar_degrau",
    ),
    # O MAPA PARA IA (`apps/core/mapa_ia.py`) — a ÚNICA área desta célula que
    # responde SEM sessão, além de `/healthz` (INV-P14, `CAMINHOS_ISENTOS` em
    # `apps/core/porta.py`). Nasce fora do prefixo `painel/` de propósito: um
    # nome de rota que começa com `painel/` sinaliza "atrás da porta" em todo
    # o resto deste arquivo, e misturar os dois seria o tipo de detalhe que
    # engana quem lê o diff rápido demais.
    # A AREA DE DOCUMENTOS (`DECISAO-a-area-de-documentos.md`, 29/08/2026).
    #
    # DOIS prefixos, e a diferenca entre eles nao e estilo: esta celula roda sob
    # SCRIPT_NAME=/admin e o Django TIRA esse prefixo do `path_info`, entao
    # `/admin/docs/x` e `/docs/x` chegariam com o mesmo caminho interno — e a
    # porta nao teria como distinguir o publico do privado. Com nomes
    # diferentes, cada um tem o seu caminho e a isencao da porta alcanca
    # exatamente um deles.
    #
    #   /docs/…        PUBLICO, isento na porta, serve so `publico: true`
    #   /documentos/…  atras da porta, serve tudo
    #
    # O padrao do nome (`[a-z0-9-]+`) e a primeira cerca: nome com barra ou com
    # ponto nao casa a rota, entao nao ha caminho para escapar da pasta. A
    # segunda cerca esta em `documentos.py::_arquivo`, que resolve e confere.
    path("docs/", docs_publicos, name="docs_publicos"),
    re_path(r"^docs/(?P<nome>[a-z0-9-]+)$", doc_publico, name="doc_publico"),
    path("documentos/", documentos_admin, name="documentos_admin"),
    # AS QUATRO ROTAS DO EDITOR (`DECISAO-o-editor-de-documentos.md`,
    # 31/08/2026): mostrar o formulario vazio, criar, mostrar o formulario
    # cheio, gravar. Quatro verbos e nao um POST com um campo escondido dizendo
    # "o que fazer" — com isso, a auditoria e o CSRF passariam a depender de um
    # valor de formulario, e ler este arquivo deixaria de contar o que a tela
    # faz. Mesma gramatica das sete rotas do menu, acima.
    #
    # A ORDEM E O QUE FAZ FUNCIONAR. `novo` e `criar` casam a rota generica
    # logo abaixo (`[a-z0-9-]+`), entao vem ANTES dela; e como um documento
    # chamado "novo" existiria na lista e nunca abriria, esses dois nomes sao
    # recusados na criacao (`editor_de_documentos.NOMES_RESERVADOS`, medido
    # junto com esta lista por `test_nenhum_endereco_reservado_escapa`).
    path("documentos/novo", documento_novo, name="documento_novo"),
    path("documentos/criar", documento_criar, name="documento_criar"),
    re_path(
        r"^documentos/(?P<nome>[a-z0-9-]+)$", documento_admin, name="documento_admin"
    ),
    # Estas duas nao disputam nada com a generica acima: o `/editar` e o
    # `/salvar` no fim as tornam caminhos diferentes.
    re_path(
        r"^documentos/(?P<nome>[a-z0-9-]+)/editar$",
        documento_editar,
        name="documento_editar",
    ),
    re_path(
        r"^documentos/(?P<nome>[a-z0-9-]+)/salvar$",
        documento_salvar,
        name="documento_salvar",
    ),
    # OS GESTOS QUE MEXEM NO LUGAR DO DOCUMENTO, e nao no texto dele
    # (`DECISAO-o-editor-de-documentos.md` §4). Todos POST: decisao que se
    # aplica por GET e decisao que um pre-carregador de link, um antivirus
    # corporativo ou um crawler autenticado tomam sozinhos — e um deles aqui
    # destroi um texto. Um verbo por rota, como as sete do menu.
    re_path(
        r"^documentos/(?P<nome>[a-z0-9-]+)/arquivar$",
        documento_arquivar,
        name="documento_arquivar",
    ),
    re_path(
        r"^documentos/(?P<nome>[a-z0-9-]+)/desarquivar$",
        documento_desarquivar,
        name="documento_desarquivar",
    ),
    re_path(
        r"^documentos/(?P<nome>[a-z0-9-]+)/apagar$",
        documento_apagar,
        name="documento_apagar",
    ),
    # O HISTORICO (`DECISAO-o-editor-de-documentos.md` §6) — o que entrou no
    # lugar do `git log` que os documentos tinham enquanto moravam no
    # repositorio. Ver e LEITURA, e por isso e GET; voltar atras muda o texto
    # de uma pagina publica, e por isso e POST: decisao que se aplica por GET e
    # decisao que um pre-carregador de link toma sozinho.
    re_path(
        r"^documentos/(?P<nome>[a-z0-9-]+)/versoes$",
        documento_versoes,
        name="documento_versoes",
    ),
    re_path(
        r"^documentos/(?P<nome>[a-z0-9-]+)/restaurar$",
        documento_restaurar,
        name="documento_restaurar",
    ),
    # OS PLANOS PARA IA (`apps/core/planos_para_ia.py`), 31/08/2026 — e as duas
    # linhas vêm ANTES das do mapa, porque a ordem é o que faz funcionar: a rota
    # genérica de baixo (`^mapa-ia/([\w.-]+)$`) casaria `mapa-ia/planos` e
    # tentaria servir um arquivo com esse nome. Com estas duas na frente, o
    # índice responde e a genérica nunca vê o caminho.
    #
    # Mora sob `/mapa-ia/` de propósito: o gateway já roteia esse prefixo
    # (`PathPrefix`), então a área nasceu sem tocar em `infra/` e sem
    # `deploy-infra`. O que ela NÃO herda é a isenção — `/mapa-ia/` continua
    # com a lista exata de `CAMINHOS_ISENTOS`, e estes caminhos têm prefixo
    # próprio na porta (`PREFIXO_PUBLICO_DOS_PLANOS`).
    path("mapa-ia/planos/", planos_indice, name="planos_indice"),
    re_path(
        # O `(\.md)?` no fim e opcional e a segunda diferenca medida contra o
        # `raw.githubusercontent.com` (31/08/2026): os dois enderecos servem o
        # mesmo arquivo, e a view descarta a extensao. O ponto NAO abre caminho
        # para escapar da pasta — so casa a sequencia exata `.md` no fim.
        r"^mapa-ia/planos/(?P<nome>[A-Za-z0-9-]+(?:\.md)?)$",
        plano_publico,
        name="plano_publico",
    ),
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
    # A aba 5 — "Exportar": a Caixa inteira em texto, num campo só, para o
    # mantenedor copiar de uma vez. Nasceu em 02/09/2026, quando ele pediu uma
    # análise das sugestões e o robô esbarrou no que o livro já registrava em
    # 31/08 (`20260831-002`): o conteúdo de uma ideia só se lê atrás do login,
    # e a porta é dele. GET puro, sem escrita, sem nome de aluno no que sai.
    path("caixa/exportar/", exportar, name="caixa_exportar"),
    # A ideia por dentro, e as tres acoes. Elas sao POST de propósito: mudam
    # coisa, e um GET seria disparado por qualquer pre-carregamento de link do
    # navegador. Depois de agir, tudo redireciona de volta para a ideia — e o
    # redirecionamento e o que impede o F5 de repetir a acao.
    path("caixa/ideia/<int:ideia_id>/", ideia, name="caixa_ideia"),
    path("caixa/ideia/<int:ideia_id>/fase", mover_ideia, name="caixa_mover"),
    path("caixa/ideia/<int:ideia_id>/avaliacao", avaliar_ideia, name="caixa_avaliar"),
    path("caixa/ideia/<int:ideia_id>/assinatura", assinar_obra, name="caixa_assinar"),
    # [ARQUIVAR] `DECISAO-arquivar-ideia.md` (29/08/2026): some do quadro do
    # aluno, nada se perde no banco. Mesma gramática das três de cima — POST,
    # redireciona de volta para a ideia dizendo o que aconteceu.
    path("caixa/ideia/<int:ideia_id>/arquivar", arquivar_ideia, name="caixa_arquivar"),
    path(
        "caixa/ideia/<int:ideia_id>/desarquivar",
        desarquivar_ideia,
        name="caixa_desarquivar",
    ),
    # [APAGAR] `DECISAO-apagar-ideia.md` (29/08/2026): sem volta, nem para
    # quem criou. Mesma gramática das outras — POST, redireciona de volta.
    path("caixa/ideia/<int:ideia_id>/apagar", apagar_ideia, name="caixa_apagar"),
    # [CORRIGIR] `DECISAO-corrigir-o-texto-de-uma-ideia.md` (31/08/2026): o erro
    # de digitacao do aluno some, e ele nao ve marca nenhuma. Mesma gramatica
    # das outras — POST, redireciona de volta para a ideia dizendo o que houve.
    path("caixa/ideia/<int:ideia_id>/texto", corrigir_ideia, name="caixa_corrigir"),
    path("escola/", escola, name="escola"),
    # [JORNADA] O mapa, com os numeros de agora
    # (`DECISAO-o-mapa-da-jornada-do-aluno.md`). Vizinho da lista e nao dentro
    # dela: sao perguntas diferentes — "como funciona a escola?" e "quem esta
    # nela?" — e o mapa precisa abrir sem que ninguem role uma lista.
    path("escola/jornada/", escola_jornada, name="escola_jornada"),
    path("escola/alunos/", escola_alunos, name="escola_alunos"),
    # A lista de nomes para colar no grupo, pedida pelo mantenedor em
    # 31/08/2026 — vizinha da lista de gestão, e não dentro dela: uma pergunta
    # sobre o cartão da pessoa ("qual a turma dela?") e uma sobre quem avisar
    # ("quem já pode entrar?") são leituras diferentes da mesma escola.
    path(
        "escola/alunos/liberados",
        escola_alunos_liberados,
        name="escola_alunos_liberados",
    ),
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
    # [SENHA] O reset manual de senha (DECISAO-login-por-senha.md), pelo
    # botao do prontuario. POST-only pelo mesmo motivo dos de cima.
    path(
        "escola/alunos/resetar-senha",
        escola_resetar_senha,
        name="escola_resetar_senha",
    ),
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
