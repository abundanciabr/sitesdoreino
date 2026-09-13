# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI
from ninja.errors import HttpError, ValidationError

from apps.core.api import SlugDeAulaAvulsaInvalido, router as cursos_router
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
# cobre as VINTE operações, o token errado e o conjunto vazio, em vez de
# confiar no roteador.
api = NinjaAPI(
    title="Cursos — API interna",
    version="1.0.0",
    description="Superficie de MAQUINA da sala de aula da Meshcraft.\n\nExiste para que o conteudo do curso tenha UM lugar, o banco desta\ncelula, e para que o editor do Admin leia e grave por aqui, nunca no\nbanco e nunca guardando copia (a lei anti-duplicacao). Sao vinte\noperacoes: as quatro que sabem de CURSO e de PARTE (`listLessons`,\n`getLesson`, `putLesson`, `publishLesson`), as quatro antigas que\nresolvem a aula so pelo site (`listSiteLessons`, `getSiteLesson`,\n`putSiteLesson`, `publishSiteLesson`, vivas porque o editor que ja\nesta no ar as chama), as tres de instrumento (`listInstruments`,\n`getInstrument`, `putInstrument`), a do bloco (`putBlock`), a do\nRevisor de coerencia (`checkLesson`, degrau 3.1) e as quatro do\nCURSO (`listCourses`, `createCourse`, `putCourse`,\n`putCourseStructure`), e as tres de AULA AVULSA (`listStandaloneLessons`,\n`createStandaloneLesson`, `updateStandaloneLesson`). O placar da fila\n(getReviewQueue) e o progresso do aluno (getStudentProgress) AINDA\nNAO EXISTEM nesta porta: o degrau 2.1 pousou sem os dois, e o degrau\nem que eles nascem ainda nao esta marcado. Quem precisar deles hoje\nnao os encontra aqui.\n\nA SALA SERVE VARIOS CURSOS DESDE 07/09/2026, e cada um nasce por esta\nporta: `createCourse` cria o curso com o apelido, o nome, a regra de\navanco (`por_laudo`, a do livro, ou `livre`, em que a proxima aula\nabre quando o aluno conclui a anterior) e o produto do catalogo a que\nele aponta; `putCourse` altera esses tres; `listCourses` os lista; e\n`putCourseStructure` grava os blocos e as aulas de qualquer curso,\nreconciliando com o que ja existe do mesmo jeito que o semeador do\nlivro: escreve estrutura, nunca toca obra, e nao apaga aula por onde\nalgum aluno ja passou. O texto de cada aula continua entrando so por\n`putLesson`.\n\nA AULA AVULSA ENTRA DESDE 11/09/2026: e uma resposta em video que a\nescola compartilha fora da sequencia de qualquer curso. Ela pertence ao\n`site_id`, nasce publicada com titulo, URL do YouTube e descricao, e o\nservico gera o `slug` imutavel que vira o endereco permanente. O Admin\nnunca manda nem escolhe esse slug. A lista devolve somente aulas publicadas\ndo mesmo site. A pagina publica le seu banco local, sem uma terceira\noperacao interna.\n\nA EDICAO DA AULA AVULSA ENTRA DESDE 11/09/2026: o Admin grava titulo,\nURL do YouTube e descricao pela identidade fixa do endereco. Editar o\ntitulo nunca troca o `slug`, porque o link que ja circulou entre os alunos\ncontinua apontando para a mesma aula.\n\nO REVISOR DE COERENCIA ENTROU EM 07/09/2026, e ele e CODIGO, nao\ninteligencia artificial: `checkLesson` le uma aula e devolve a lista\nde defeitos, ja em portugues, sem gravar nada. E as duas operacoes de\npublicar passaram a RECUSAR com 422 a aula cuja peca manda o aluno\npara uma encomenda que nao existe no curso ([INV-CUR-C1]); as outras\ncinco conferencias sao aviso e nao impedem publicar.\n\nLei do assunto: docs/decisoes/PLANO-CELULA-CURSOS.md (secoes 4 e 5).\n\nO TEXTO DAS AULAS E OBRA NAO LANCADA DO MANTENEDOR: entra por esta\nporta e so por ela; nunca por migracao, nunca por arquivo no\nrepositorio, que e publico.\n\nO TITULO DA ENCOMENDA E O BLOCO ENTRAM DESDE 06/09/2026. Ate essa\ndata, sete campos eram 422 no corpo de `putLesson`: numero, ordem,\ntitulo, bloco, estado, versao e data de publicacao. O titulo saiu\ndessa lista, e e o unico que sai, porque e o unico dos sete que e OBRA\ne nao ESTRUTURA: os outros seis sao fatos publicos do livro, escritos\npela instalacao do curso, e o titulo e a frase que o cliente diz na\nencomenda e a primeira coisa que o aluno le. Ele e opcional, e ausente\nsignifica nao mexer, para que a tela que nao o conhece nao apague o\nque a outra escreveu. O nome do bloco e o titulo do Boss dele entram\npor `putBlock`, que e operacao propria porque doze blocos servem\ntrinta e quatro encomendas e nenhum deles e de uma aula so.\n\nO `site_id` e obrigatorio em toda operacao de aula (uma fabrica, N\nlojas): esta celula nao tem middleware de site, e a porta nao adivinha\nde qual escola e a encomenda. Os instrumentos sao de plataforma\ninteira, de proposito: os 13 cartoes sao os mesmos em toda escola.\n\nO CURSO E O SLUG, e a PARTE e conferida (05/09/2026): o endereco da\nsala de aula carrega os dois para que o aluno saiba onde esta. Nas\nquatro operacoes de `/cursos/{curso}/aulas`, o curso sai do par\nsite+slug (nunca `o primeiro curso do site`) e `parte` que nao casa\ncom o bloco da aula RECUSA com 404 em vez de devolver a aula: um\nendereco que aponta certo para a aula errada e pior do que um\nendereco quebrado.\n\nA VIDEO-AULA EM TEXTO ENTRA DESDE 06/09/2026, e ela e a decima nona\npeca, nunca a decima setima. Cada encomenda passou a ter um segundo\ntexto, a mesma aula contada como numa video-aula, e o aluno chega nele\npor um botao embaixo do capitulo, num modal. Vem e vai como PECA\n(`videoaula_em_texto`) para herdar o editor, o historico de versoes, a\nrestricao de uma por aula e a renderizacao em Markdown que as outras ja\ntem. Ela fica FORA da sequencia das 16 da anatomia, que e lei da celula\ne nao cresce: quem consome esta porta mostra as 16 em ordem e esta uma\nso a pedido, e NAO desenha botao quando o texto dela vem vazio.\n\nO GUARDIAO DE FIDELIDADE ENTROU EM 07/09/2026 (degrau 3.2), e ele e\nIA. Ele nao ganhou operacao propria: e o parametro `modo` de\n`checkLesson`, que vale `coerencia` (o padrao, identico ao de antes)\nou `fidelidade`. Em `fidelidade` ele compara cada peca DERIVADA (o\nroteiro, o guia do mentor, a video-aula em texto e a peca onde mora o\nCartao de 1 pagina) com a FONTE de que ela deriva, e aponta onde o\nsentido mudou, no mesmo formato de defeito. Ele APONTA E NUNCA VETA:\n`impede_publicar` e sempre falso neste modo. Encomenda sem peca\nderivada escrita e 422, IA fora do ar e 503, e nada e gravado em\nnenhum dos dois casos.\n",
    servers=[{"url": "http://cursos:8000/api/cursos"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", cursos_router)


def _e_edicao_de_aula_avulsa(request) -> bool:
    return request.method == "PUT" and "/aulas-avulsas/" in request.path_info


def _resposta_de_erro_da_aula_avulsa(request, status, erro, o_que_fazer):
    return api.create_response(
        request,
        {"erro": erro, "o_que_fazer": o_que_fazer},
        status=status,
    )


@api.exception_handler(HttpError)
def resposta_para_http_error(request, exc):
    if _e_edicao_de_aula_avulsa(request):
        if exc.status_code == 404:
            return _resposta_de_erro_da_aula_avulsa(
                request,
                404,
                "aula_avulsa_nao_encontrada",
                "Confira o endereço da aula ou escolha outra aula publicada.",
            )
        if exc.status_code == 422:
            return _resposta_de_erro_da_aula_avulsa(
                request,
                422,
                "corpo_invalido",
                "Revise os campos da aula e envie somente título, URL do vídeo, descrição e slug.",
            )
    return api.create_response(request, {"detail": str(exc)}, status=exc.status_code)


@api.exception_handler(SlugDeAulaAvulsaInvalido)
def resposta_para_slug_de_aula_avulsa_invalido(request, exc):
    if _e_edicao_de_aula_avulsa(request):
        return _resposta_de_erro_da_aula_avulsa(
            request,
            422,
            "slug_invalido",
            "Informe um endereço com ao menos uma letra ou número.",
        )
    return api.create_response(request, {"detail": str(exc)}, status=422)


@api.exception_handler(ValidationError)
def resposta_para_erro_de_validacao(request, exc):
    if _e_edicao_de_aula_avulsa(request):
        slug_invalido = any(
            erro["loc"][-1] == "slug" and erro["type"] != "string_type"
            for erro in exc.errors
        )
        if slug_invalido:
            return _resposta_de_erro_da_aula_avulsa(
                request,
                422,
                "slug_invalido",
                "Use letras minúsculas sem acentos, números e hífens.",
            )
        return _resposta_de_erro_da_aula_avulsa(
            request,
            422,
            "corpo_invalido",
            "Revise os campos da aula e envie somente título, URL do vídeo, descrição e slug.",
        )
    return api.create_response(request, {"detail": exc.errors}, status=422)
