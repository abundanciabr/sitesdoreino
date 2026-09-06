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
# cobre as DOZE operações, o token errado e o conjunto vazio, em vez de
# confiar no roteador.
api = NinjaAPI(
    title="Cursos — API interna",
    version="1.0.0",
    description=(
        "Superficie de MAQUINA da sala de aula da Meshcraft.\n"
        "\n"
        "Existe para que o conteudo do curso tenha UM lugar, o banco desta\n"
        "celula, e para que o editor do Admin leia e grave por aqui, nunca no\n"
        "banco e nunca guardando copia (a lei anti-duplicacao). Sao doze\n"
        "operacoes: as quatro que sabem de CURSO e de PARTE (`listLessons`,\n"
        "`getLesson`, `putLesson`, `publishLesson`), as quatro antigas que\n"
        "resolvem a aula so pelo site (`listSiteLessons`, `getSiteLesson`,\n"
        "`putSiteLesson`, `publishSiteLesson`, vivas porque o editor que ja\n"
        "esta no ar as chama), as tres de instrumento (`listInstruments`,\n"
        "`getInstrument`, `putInstrument`) e a do bloco (`putBlock`). Os\n"
        "verificadores (checkLesson) nascem no degrau 3.1; o placar da fila\n"
        "(getReviewQueue) e o progresso do aluno (getStudentProgress), no 2.1.\n"
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
    ),
    servers=[{"url": "http://cursos:8000/api/cursos"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", cursos_router)
