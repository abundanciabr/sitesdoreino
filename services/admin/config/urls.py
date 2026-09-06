from django.urls import path, re_path

from apps.core.diagnostico import diag_json
from apps.core.analise_da_caixa import analise, desfazer_fusao, fundir
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
from apps.core.livro import (
    livro,
    livro_baixar_tudo,
    texto_apagar,
    texto_baixar,
    texto_criar,
    texto_do_livro,
    texto_editar,
    texto_novo,
    texto_restaurar,
    texto_salvar,
    textos_enviar,
)
from apps.core.mapa_do_site import mapa_do_site
from apps.core.economia import (
    economia,
    economia_mudar,
    economia_mudar_conquista,
    economia_mudar_degrau,
)
from apps.core.escola_pontos import escola_pontos
from apps.core.avisos import avisos, avisos_testar
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
from apps.core.perpetuo import perpetuo
from apps.core.ciclo import ciclo
from apps.core.confianca import confianca, confianca_quebrado
from apps.core.coortes import coortes
from apps.core.laboratorio import laboratorio
from apps.core.placar import placar
from apps.core.reuniao import reuniao
from apps.core.robos import robos
from apps.core.aulas import (
    aula,
    aula_publicar,
    aula_salvar,
    aulas,
    instrumento,
    instrumento_salvar,
)
from apps.core.sequencias import (
    sequencia,
    sequencia_ligar,
    sequencia_publicar,
    sequencias,
)
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
    escola_apagar_recusado,
    escola_cadastrar,
    escola_jornada,
    escola_decidir,
    escola_prontuario,
    escola_recusados,
    escola_reconsiderar,
    escola_resetar_senha,
    escola_turmas,
    escola_turmas_conferir,
    escola_turmas_liberar,
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
    # O botao que prova se os avisos na tela do celular estao funcionando
    # (03/09/2026). Nasceu do caso em que o botao de ligar os avisos falhava
    # no navegador do mantenedor com o servidor verde, e nao havia como saber
    # de qual lado sem entrar na VPS. Duas rotas, na mesma gramatica da
    # economia: a tela e o gesto.
    path("avisos/", avisos, name="avisos"),
    path("avisos/testar", avisos_testar, name="avisos_testar"),
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
    # A BIBLIOTECA DO LIVRO (`apps/core/livro.py`), 04/09/2026 — onde o
    # mantenedor guarda os textos do livro que escreve.
    #
    # NENHUMA destas rotas e publica, e isso nao e descuido de configuracao: e
    # a decisao. O repositorio deste projeto e publico, o livro nao esta
    # lancado, e por isso o texto so existe no banco e so abre para quem passa
    # pela porta. Nao ha aqui o par `/docs/` + `/documentos/` das linhas de
    # cima — ha um lado so.
    #
    # As tres primeiras vem ANTES da generica `^livro/<nome>$` pelo motivo de
    # sempre: um texto chamado "novo" existiria na lista e nunca abriria. A
    # `NOMES_RESERVADOS` do modulo fecha o outro lado, impedindo que ele nasca.
    path("livro/", livro, name="livro"),
    path("livro/novo", texto_novo, name="texto_novo"),
    path("livro/criar", texto_criar, name="texto_criar"),
    path("livro/enviar", textos_enviar, name="textos_enviar"),
    path("livro/tudo.md", livro_baixar_tudo, name="livro_baixar_tudo"),
    re_path(r"^livro/(?P<nome>[a-z0-9-]+)$", texto_do_livro, name="texto_do_livro"),
    re_path(r"^livro/(?P<nome>[a-z0-9-]+)/editar$", texto_editar, name="texto_editar"),
    re_path(r"^livro/(?P<nome>[a-z0-9-]+)/salvar$", texto_salvar, name="texto_salvar"),
    # Baixar e LEITURA, e por isso GET. Guardar, editar, restaurar e apagar
    # mudam o que esta escrito, e por isso sao POST — a mesma regra das rotas
    # dos documentos, e pelo mesmo motivo: decisao que se aplica por GET e
    # decisao que um pre-carregador de link toma sozinho.
    re_path(r"^livro/(?P<nome>[a-z0-9-]+)/baixar$", texto_baixar, name="texto_baixar"),
    re_path(
        r"^livro/(?P<nome>[a-z0-9-]+)/restaurar$",
        texto_restaurar,
        name="texto_restaurar",
    ),
    re_path(r"^livro/(?P<nome>[a-z0-9-]+)/apagar$", texto_apagar, name="texto_apagar"),
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
    # A aba 6 — "A análise": a leitura das ideias da turma, com os fatos vivos
    # e o julgamento escrito à mão (apps/core/analise_da_caixa.py). Nasceu em
    # 05/09/2026, quando o mantenedor recebeu essa leitura numa página fora do
    # site e decidiu que entrega dele mora no site
    # (docs/decisoes/DECISAO-onde-mora-o-que-eu-entrego.md).
    path("caixa/analise/", analise, name="caixa_analise"),
    # Juntar ideias e desfazer a junção. POST de propósito, como as demais
    # ações da Caixa: mudam coisa, e um GET seria disparado por qualquer
    # pré-carregamento de link do navegador.
    path("caixa/analise/fundir", fundir, name="caixa_fundir"),
    path(
        "caixa/analise/fusao/<int:fusao_id>/desfazer",
        desfazer_fusao,
        name="caixa_desfazer_fusao",
    ),
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
    # O LANÇAMENTO PERPÉTUO (`apps/core/perpetuo.py`, 02/09/2026) — a área que
    # o mantenedor pediu para reunir "várias coisas sobre o lançamento
    # perpétuo": a máquina que vende todo dia, sem depender de uma data.
    #
    # FORA do prefixo `painel/`, pelo mesmo motivo do mapa e do menu: a rota
    # genérica `painel/<qualquer coisa>` engoliria qualquer irmã dela. Nasce
    # vizinha de `/escola/` e de `/caixa/`, na mesma gramática — e a barra
    # final segue a convenção das outras telas, com o APPEND_SLASH atendendo
    # quem digitar `/admin/perpetuo` sem ela.
    #
    # UMA rota hoje, e a área foi desenhada para ganhar irmãs: cada painel novo
    # entra como `perpetuo/<coisa>/`, e nunca como uma tela solta noutro canto.
    path("perpetuo/", perpetuo, name="perpetuo"),
    # O PLACAR (`apps/core/placar.py`, 03/09/2026) — o andar zero do painel de
    # gestão do negócio (`docs/decisoes/PLANO-PAINEL-DE-GESTAO.md`, degrau 0):
    # a Meta Crucialmente Importante, o número medido, e ganhando ou perdendo.
    # Fora do prefixo `painel/` pelo mesmo motivo do perpétuo: a rota genérica
    # `painel/<qualquer coisa>` engoliria esta.
    path("placar/", placar, name="placar"),
    # O CALENDÁRIO DO CICLO (`apps/core/ciclo.py`, 04/09/2026) — as 12
    # semanas do ano de 12 semanas, mais a de preparação e a de
    # recuperação, com a meta de cada uma e o que aconteceu nela.
    #
    # DENTRO de `placar/`, e não ao lado: é a régua que o placar usa para
    # dizer ganhando ou perdendo, e o menu do topo (`moldura.py`) casa a
    # seção por PREFIXO — assim o item "Placar" continua aceso aqui, que
    # é onde o mantenedor entende que está. Um item novo no menu para uma
    # leitura da mesma meta seria o menu crescendo sem realidade nova.
    path("placar/ciclo/", ciclo, name="ciclo"),
    # A CONFIANÇA (`apps/core/confianca.py`, 05/09/2026) — cobertura, frescor e
    # o que chegou quebrado: o degrau 11 do plano do painel de gestão (§6.6).
    #
    # Sub-rota do placar pela mesma razão do calendário logo acima, e por uma
    # segunda: esta tela não é um assunto novo da administração, é a pergunta
    # "dá para acreditar no que acabei de ler?" feita sobre AQUELES números.
    # Como seção própria do menu ela viveria longe do que julga, e a lista de
    # seções (`moldura.py`) cresceria sem realidade nova.
    path("placar/confianca/", confianca, name="confianca"),
    # A inspeção de UM evento que chegou quebrado. É a única porta desta área
    # que mostra o corpo cru de um envelope, e por isso ela é um endereço
    # separado em vez de um trecho da lista: o contrato esconde o corpo em
    # lote de propósito (ele pode trazer o que esta casa não guarda), e ver um
    # tem de ser um gesto deliberado do mantenedor.
    path(
        "placar/confianca/quebrado/<int:morto_id>/",
        confianca_quebrado,
        name="confianca_quebrado",
    ),
    # O LABORATÓRIO (`apps/core/laboratorio.py`, 05/09/2026) — os experimentos
    # da escola: rodando, passados do prazo, e encerrados com o veredito. É o
    # degrau 12 do plano do painel de gestão.
    #
    # Sub-rota do placar pela mesma razão do calendário e da confiança acima, e
    # por uma terceira, que é a mais forte das três: esta tela É a fonte do 12º
    # número do placar de doze (`aprendizados-validados-no-ciclo`). Como seção
    # própria do menu ela viveria longe do número que produz, e a lista de
    # seções (`moldura.py`) cresceria sem realidade nova — experimento não é
    # assunto novo da administração, é o que se faz para mover aqueles números.
    path("placar/laboratorio/", laboratorio, name="laboratorio"),
    # AS COORTES (`apps/core/coortes.py`, 05/09/2026) — quem entrou em cada mês,
    # e o que a memória da escola sabe sobre cada grupo. É o degrau 10 do plano
    # do painel de gestão (§6.4), na metade que já tem fonte hoje.
    #
    # Sub-rota do placar pela mesma razão das três irmãs acima, e por uma
    # quarta: esta tela é a BARRA DO MÊS guardada. A barra zera no dia 1, e o
    # que ela deixa para trás é exatamente uma linha desta tabela. Como seção
    # própria do menu ela viveria longe do número de que é a memória.
    path("placar/coortes/", coortes, name="coortes"),
    path("reuniao/", reuniao, name="reuniao"),
    path("escola/", escola, name="escola"),
    # [JORNADA] O mapa, com os numeros de agora
    # (`DECISAO-o-mapa-da-jornada-do-aluno.md`). Vizinho da lista e nao dentro
    # dela: sao perguntas diferentes — "como funciona a escola?" e "quem esta
    # nela?" — e o mapa precisa abrir sem que ninguem role uma lista.
    path("escola/jornada/", escola_jornada, name="escola_jornada"),
    # [SEQUENCIAS] A tela onde o mantenedor vê e EDITA as sequências de
    # mensagens da escola (`apps/core/sequencias.py`, degrau 7 do
    # `PLANO-SEQUENCIAS-DE-MENSAGENS.md`, 04/09/2026).
    #
    # Vizinha do `escola_jornada` de cima, e as duas telas são DIFERENTES:
    # aquela é o MAPA da jornada do aluno (por onde uma pessoa passa entre
    # chegar no site e sair da escola, com quantas estão em cada parada); esta é
    # o conteúdo das SEQUÊNCIAS de mensagens automáticas. O plural no endereço
    # separa as duas, e este comentário existe porque a semelhança dos nomes é
    # o tipo de coisa que engana quem lê o diff rápido demais.
    #
    # A ORDEM É O QUE FAZ FUNCIONAR: `ligar` e `publicar` casariam o padrão da
    # rota genérica logo abaixo, então vêm ANTES dela. Os dois são POST-only
    # (`require_POST` na view) e sem barra final, na mesma gramática das quatro
    # rotas do editor de documentos: decisão que se aplica por GET é decisão que
    # um pré-carregador de link, um antivírus corporativo ou um crawler
    # autenticado tomam sozinhos, e aqui uma delas muda o que sai para alunos de
    # verdade. Um verbo por rota, nunca um POST com um campo escondido dizendo
    # "o que fazer": com isso a auditoria e o CSRF passariam a depender de um
    # valor de formulário, e ler este arquivo deixaria de contar o que a tela faz.
    #
    # O alvo vem no CORPO do formulário, junto do CSRF que o protege, e não no
    # caminho — mesma escolha de `escola_decidir` e `escola_reconsiderar`.
    path("escola/jornadas/", sequencias, name="escola_jornadas"),
    path("escola/jornadas/ligar", sequencia_ligar, name="escola_jornada_ligar"),
    path(
        "escola/jornadas/publicar",
        sequencia_publicar,
        name="escola_jornada_publicar",
    ),
    # O padrão do slug (`[a-z0-9-]+`) é a cerca desta ponta: nome com barra ou
    # com ponto não casa a rota, então não há caminho para pedir outra coisa à
    # porta de máquina da `mensageria` por este endereço. A segunda cerca está
    # do outro lado, onde jornada de outro site é 404 mesmo com o slug certo na
    # mão (CONSTITUICAO Lei 9).
    re_path(
        r"^escola/jornadas/(?P<slug>[a-z0-9-]+)/$",
        sequencia,
        name="escola_jornada_sequencia",
    ),
    # [AULAS] O editor de encomendas do curso (`apps/core/aulas.py`, degrau 1.5
    # do `PLANO-CELULA-CURSOS.md`, 05/09/2026). Vizinho das sequências, e na
    # mesma gramática: a lista, a encomenda por dentro, e um verbo por rota
    # para cada gesto (salvar, publicar), POST-only e sem barra final. O texto
    # das aulas mora na `cursos` e entra SÓ por aqui, pela porta de máquina
    # dela ([INV-CUR-C2]): esta célula não guarda cópia de uma linha.
    #
    # O número da aula é curto e fechado ("E00" a "E32" e "EB", vocabulário do
    # contrato); o padrão `[A-Za-z0-9]+` é a cerca desta ponta, e a segunda está
    # do outro lado, onde aula de outro site é 404 mesmo com o número certo
    # (CONSTITUICAO Lei 9). O slug do instrumento segue a cerca das sequências.
    #
    # O CURSO E A PARTE VIAJAM NO ENDEREÇO (05/09/2026, TAR-211). Pedido do
    # mantenedor: "quero que ao compartilhar uma aula o link da mesma seja útil
    # para o aluno entender exatamente em qual parte do curso ele está". O curso
    # é o SLUG, resolvido pelo par site+slug do outro lado, e não mais "o
    # primeiro curso do site", que quebraria calado no dia do segundo curso.
    #
    # O `parte-N` é um trecho OPCIONAL do mesmo padrão, e por isso as quatro
    # rotas continuam sendo quatro, com um nome cada: o `reverse` do Django
    # expande o grupo opcional em dois endereços e escolhe pelo que você passa
    # (com `parte`, o longo; sem, o curto). Duplicar cada rota daria oito nomes,
    # e a metade deles seria escolhida por engano em algum template.
    # `parte` é `[123]` porque o vocabulário é do contrato (`ParteDoCurso`):
    # `parte-9` não chega a virar pedido, é 404 aqui na porta.
    re_path(
        r"^escola/(?P<curso>[a-z0-9-]+)/(?:parte-(?P<parte>[123])/)?aulas/$",
        aulas,
        name="escola_aulas",
    ),
    re_path(
        r"^escola/(?P<curso>[a-z0-9-]+)/(?:parte-(?P<parte>[123])/)?"
        r"aulas/(?P<numero>[A-Za-z0-9]+)/$",
        aula,
        name="escola_aula",
    ),
    re_path(
        r"^escola/(?P<curso>[a-z0-9-]+)/(?:parte-(?P<parte>[123])/)?"
        r"aulas/(?P<numero>[A-Za-z0-9]+)/salvar$",
        aula_salvar,
        name="escola_aula_salvar",
    ),
    re_path(
        r"^escola/(?P<curso>[a-z0-9-]+)/(?:parte-(?P<parte>[123])/)?"
        r"aulas/(?P<numero>[A-Za-z0-9]+)/publicar$",
        aula_publicar,
        name="escola_aula_publicar",
    ),
    re_path(
        r"^escola/instrumentos/(?P<slug>[a-z0-9_-]+)/$",
        instrumento,
        name="escola_instrumento",
    ),
    re_path(
        r"^escola/instrumentos/(?P<slug>[a-z0-9_-]+)/salvar$",
        instrumento_salvar,
        name="escola_instrumento_salvar",
    ),
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
    # [RECUSADOS] Quem voce recusou, e o botao de voltar atras (02/09/2026,
    # pedido do mantenedor). Vizinha da lista e nao dentro dela, pelo mesmo
    # motivo dos "liberados" acima: aquela tela responde "quem esta esperando e
    # quem ja e aluno?", e esta responde "quem eu deixei de fora?" — leituras
    # diferentes da mesma escola, e reconsiderar e raro perto do trabalho
    # diario que aquela pagina serve.
    path("escola/alunos/recusados", escola_recusados, name="escola_recusados"),
    # O gesto de aceitar quem tinha sido recusado. POST-only pelo mesmo motivo
    # de todas as escritas desta celula, e sem id no caminho: o alvo vem no
    # corpo do formulario, junto do CSRF que o protege.
    path(
        "escola/alunos/reconsiderar",
        escola_reconsiderar,
        name="escola_reconsiderar",
    ),
    # [APAGAR-RECUSADO] Apagar de vez um pedido recusado (03/09/2026,
    # `DECISAO-apagar-recusado-definitivamente.md`). POST-only e sem id no
    # caminho, na mesma gramática de `escola_reconsiderar` acima: o alvo vem
    # no corpo do formulário, junto do CSRF que o protege — e é irreversível,
    # o que torna o CSRF ainda mais importante aqui do que ali.
    path(
        "escola/alunos/recusados/apagar",
        escola_apagar_recusado,
        name="escola_apagar_recusado",
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
    # [TURMAS] Liberar em lote pela lista de WhatsApp das turmas (02/09/2026,
    # pedido do mantenedor). Vizinha de `escola/alunos/`, e nao dentro dela: a
    # tela de alunos responde "quem esta esperando?", esta responde "quem da
    # minha lista ja chegou?" — perguntas diferentes, e uma caixa de colar no
    # meio da lista empurraria para baixo o que ele abre aquela tela para ver.
    path("escola/turmas/", escola_turmas, name="escola_turmas"),
    # A conferencia e POST mesmo sendo LEITURA, e a excecao e deliberada: a
    # lista nao caberia numa querystring, e um telefone nao tem por que passar
    # pela barra de enderecos, pelo historico do navegador e pelo log de acesso.
    path(
        "escola/turmas/conferir", escola_turmas_conferir, name="escola_turmas_conferir"
    ),
    # A escrita em lote. POST-only pelo mesmo motivo de todas as outras.
    path("escola/turmas/liberar", escola_turmas_liberar, name="escola_turmas_liberar"),
    # [QUADRO DE PONTOS] A turma ordenada por XP, com nivel, titulo, medalhas,
    # marcos e quem parou (03/09/2026, pedido do mantenedor). Vizinha de
    # `escola/alunos/` e de `escola/turmas/`, e nao dentro de nenhuma: aquela
    # responde "quem esta na escola?", esta responde "quem esta jogando, e
    # quem parou?" — a gamificacao e a matricula sao duas celulas diferentes,
    # e esta tela e o unico lugar que cruza as duas.
    path("escola/pontos/", escola_pontos, name="escola_pontos"),
    path("escola/admin/promover", escola_admin_promover, name="escola_admin_promover"),
    path("escola/admin/remover", escola_admin_remover, name="escola_admin_remover"),
    path("", visao_geral, name="visao_geral"),
]
