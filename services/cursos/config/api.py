# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.api import router as cursos_router
from apps.core.auth import bearerAuth

# `servers` aponta para a REDE INTERNA do Docker: é o endereço que a célula
# `admin` (o editor, degrau 1.5) porá no env dela. O valor congela em
# `contracts/cursos.openapi.yaml` no degrau 1.4 (Rito de Contrato, RITOS.md §3);
# depois disso, mudá-lo é Rito, nunca edição aqui.
#
# ATENÇÃO, E AQUI ESTA CÉLULA É COMO O `forum` E A `gamificacao`, E DIFERENTE
# DA `identidade`: esta porta **é** alcançável pela borda pública, em
# `meshcraft.top/cursos/api/cursos/...`. A célula roda sob `SCRIPT_NAME=/cursos`
# e o handler ASGI do Django faz `path_info = path.removeprefix(script_name)`;
# é o mesmo corte que faz `meshcraft.top/cursos/healthz` responder 200 com o
# `urls.py` declarando `path("healthz", ...)` sem prefixo nenhum
# (`armadilhas/186`; a premissa está fixada em `tests/test_healthz_script_name.py`).
#
# ENTÃO QUEM FECHA A PORTA É O BEARER, E SÓ ELE: 401 sem token, e o conjunto de
# tokens nasce VAZIO (`settings.TOKENS_ACEITOS`). Não há segunda camada por
# baixo, e é por isso que o guarda de 401 em `tests/test_porta_exige_bearer.py`
# cobre as DEZESSETE operações, o token errado e o conjunto vazio, em vez de
# confiar no roteador.
api = NinjaAPI(
    title="Cursos — API interna",
    version="1.0.0",
    description=(
        "Superficie de MAQUINA da sala de aula da Meshcraft.\n"
        "\n"
        "Existe para que o conteudo do curso tenha UM lugar, o banco desta\n"
        "celula, e para que o editor do Admin leia e grave por aqui, nunca no\n"
        "banco e nunca guardando copia (a lei anti-duplicacao). Sao dezessete\n"
        "operacoes: as quatro que sabem de CURSO e de PARTE (`listLessons`,\n"
        "`getLesson`, `putLesson`, `publishLesson`), as quatro antigas que\n"
        "resolvem a aula so pelo site (`listSiteLessons`, `getSiteLesson`,\n"
        "`putSiteLesson`, `publishSiteLesson`, vivas porque o editor que ja\n"
        "esta no ar as chama), as tres de instrumento (`listInstruments`,\n"
        "`getInstrument`, `putInstrument`), a do bloco (`putBlock`), a do\n"
        "Revisor de coerencia (`checkLesson`, degrau 3.1) e as quatro do\n"
        "CURSO (`listCourses`, `createCourse`, `putCourse`,\n"
        "`putCourseStructure`). O placar da fila\n"
        "(getReviewQueue) e o progresso do aluno (getStudentProgress) AINDA\n"
        "NAO EXISTEM nesta porta: o degrau 2.1 pousou sem os dois, e o degrau\n"
        "em que eles nascem ainda nao esta marcado. Quem precisar deles hoje\n"
        "nao os encontra aqui.\n"
        "\n"
        "A SALA SERVE VARIOS CURSOS DESDE 07/09/2026, e cada um nasce por esta\n"
        "porta: `createCourse` cria o curso com o apelido, o nome, a regra de\n"
        "avanco (`por_laudo`, a do livro, ou `livre`, em que a proxima aula\n"
        "abre quando o aluno conclui a anterior) e o produto do catalogo a que\n"
        "ele aponta; `putCourse` altera esses tres; `listCourses` os lista; e\n"
        "`putCourseStructure` grava os blocos e as aulas de qualquer curso,\n"
        "reconciliando com o que ja existe do mesmo jeito que o semeador do\n"
        "livro: escreve estrutura, nunca toca obra, e nao apaga aula por onde\n"
        "algum aluno ja passou. O texto de cada aula continua entrando so por\n"
        "`putLesson`.\n"
        "\n"
        "O REVISOR DE COERENCIA ENTROU EM 07/09/2026, e ele e CODIGO, nao\n"
        "inteligencia artificial: `checkLesson` le uma aula e devolve a lista\n"
        "de defeitos, ja em portugues, sem gravar nada. E as duas operacoes de\n"
        "publicar passaram a RECUSAR com 422 a aula cuja peca manda o aluno\n"
        "para uma encomenda que nao existe no curso ([INV-CUR-C1]); as outras\n"
        "cinco conferencias sao aviso e nao impedem publicar.\n"
        "\n"
        "Lei do assunto: docs/decisoes/PLANO-CELULA-CURSOS.md (secoes 4 e 5).\n"
        "\n"
        "O TEXTO DAS AULAS E OBRA NAO LANCADA DO MANTENEDOR: entra por esta\n"
        "porta e so por ela; nunca por migracao, nunca por arquivo no\n"
        "repositorio, que e publico.\n"
        "\n"
        "O TITULO DA ENCOMENDA E O BLOCO ENTRAM DESDE 06/09/2026. Ate essa\n"
        "data, sete campos eram 422 no corpo de `putLesson`: numero, ordem,\n"
        "titulo, bloco, estado, versao e data de publicacao. O titulo saiu\n"
        "dessa lista, e e o unico que sai, porque e o unico dos sete que e OBRA\n"
        "e nao ESTRUTURA: os outros seis sao fatos publicos do livro, escritos\n"
        "pela instalacao do curso, e o titulo e a frase que o cliente diz na\n"
        "encomenda e a primeira coisa que o aluno le. Ele e opcional, e ausente\n"
        "significa nao mexer, para que a tela que nao o conhece nao apague o\n"
        "que a outra escreveu. O nome do bloco e o titulo do Boss dele entram\n"
        "por `putBlock`, que e operacao propria porque doze blocos servem\n"
        "trinta e quatro encomendas e nenhum deles e de uma aula so.\n"
        "\n"
        "O `site_id` e obrigatorio em toda operacao de aula (uma fabrica, N\n"
        "lojas): esta celula nao tem middleware de site, e a porta nao adivinha\n"
        "de qual escola e a encomenda. Os instrumentos sao de plataforma\n"
        "inteira, de proposito: os 13 cartoes sao os mesmos em toda escola.\n"
        "\n"
        "O CURSO E O SLUG, e a PARTE e conferida (05/09/2026): o endereco da\n"
        "sala de aula carrega os dois para que o aluno saiba onde esta. Nas\n"
        "quatro operacoes de `/cursos/{curso}/aulas`, o curso sai do par\n"
        "site+slug (nunca `o primeiro curso do site`) e `parte` que nao casa\n"
        "com o bloco da aula RECUSA com 404 em vez de devolver a aula: um\n"
        "endereco que aponta certo para a aula errada e pior do que um\n"
        "endereco quebrado.\n"
        "\n"
        "A VIDEO-AULA EM TEXTO ENTRA DESDE 06/09/2026, e ela e a decima nona\n"
        "peca, nunca a decima setima. Cada encomenda passou a ter um segundo\n"
        "texto, a mesma aula contada como numa video-aula, e o aluno chega nele\n"
        "por um botao embaixo do capitulo, num modal. Vem e vai como PECA\n"
        "(`videoaula_em_texto`) para herdar o editor, o historico de versoes, a\n"
        "restricao de uma por aula e a renderizacao em Markdown que as outras ja\n"
        "tem. Ela fica FORA da sequencia das 16 da anatomia, que e lei da celula\n"
        "e nao cresce: quem consome esta porta mostra as 16 em ordem e esta uma\n"
        "so a pedido, e NAO desenha botao quando o texto dela vem vazio.\n"
        "\n"
        "O GUARDIAO DE FIDELIDADE ENTROU EM 07/09/2026 (degrau 3.2), e ele e\n"
        "IA. Ele nao ganhou operacao propria: e o parametro `modo` de\n"
        "`checkLesson`, que vale `coerencia` (o padrao, identico ao de antes)\n"
        "ou `fidelidade`. Em `fidelidade` ele compara cada peca DERIVADA (o\n"
        "roteiro, o guia do mentor, a video-aula em texto e a peca onde mora o\n"
        "Cartao de 1 pagina) com a FONTE de que ela deriva, e aponta onde o\n"
        "sentido mudou, no mesmo formato de defeito. Ele APONTA E NUNCA VETA:\n"
        "`impede_publicar` e sempre falso neste modo. Encomenda sem peca\n"
        "derivada escrita e 422, IA fora do ar e 503, e nada e gravado em\n"
        "nenhum dos dois casos.\n"
    ),
    servers=[{"url": "http://cursos:8000/api/cursos"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", cursos_router)
