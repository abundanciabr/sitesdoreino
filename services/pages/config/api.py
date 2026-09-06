# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.auth import bearerAuth
from apps.portfolio.api import router as portfolio_router

# `servers` aponta para a REDE INTERNA do Docker: é o endereço que outra célula
# porá no env dela. O valor congela em `contracts/pages.openapi.yaml`; depois
# disso, mudá-lo é Rito (RITOS.md §3), nunca edição aqui.
#
# ATENÇÃO, E AQUI ESTA CÉLULA É COMO O `forum` E A `cursos`, E DIFERENTE DA
# `identidade`: esta porta **é** alcançável pela borda pública, em
# `meshcraft.top/pages/interno/...`. A célula roda sob `SCRIPT_NAME=/pages` e o
# handler ASGI do Django faz `path_info = path.removeprefix(script_name)`; é o
# mesmo corte que faz `meshcraft.top/pages/healthz` responder 200 com o
# `urls.py` declarando `path("healthz", ...)` sem prefixo nenhum
# (`armadilhas/186`; a premissa está fixada em
# `tests/test_healthz_script_name.py`).
#
# ENTÃO QUEM FECHA A PORTA É O BEARER, E SÓ ELE: 401 sem token, e o conjunto de
# tokens nasce VAZIO (`settings.TOKENS_ACEITOS`). Não há segunda camada por
# baixo, e é por isso que o guarda de `tests/test_porta_de_maquina.py` cobre o
# sem-token, o token errado e o conjunto vazio, em vez de confiar no roteador.
api = NinjaAPI(
    title="Pages — API interna",
    version="1.0.0",
    description=(
        "Superficie de MAQUINA da casa das Paginas do aluno.\n"
        "\n"
        "Existe porque a lei desta obra diz que a peca tem UMA casa: o\n"
        "portfolio nao guarda copia de medalha, a gamificacao nao guarda copia\n"
        "de peca, e a tela que precisa das duas pergunta por HTTP com falha\n"
        "ABERTA (PLANO-PORTFOLIO-DO-ALUNO.md secao 4). Sem esta porta, a\n"
        "primeira tela que precisasse do selo guardaria uma segunda copia\n"
        "dele, e no dia em que as duas discordassem ninguem saberia qual esta\n"
        "certa.\n"
        "\n"
        "UMA OPERACAO SO, e essa estreiteza foi decidida: nada mais entra\n"
        "porque nada mais tem consumidor declarado hoje. O contrato desta casa\n"
        "cresce de graca e encolhe com autorizacao explicita, entao nascer\n"
        "largo seria congelar operacao que ninguem chama e depois precisar de\n"
        "um Rito de Contrato para tira-la.\n"
        "\n"
        "O Bearer prova QUEM CHAMA, nunca quem e a pessoa: nao chega cookie\n"
        "aqui, e esta celula nao assina sessao (INV-P12). So id opaco sai:\n"
        "nem link, nem legenda, nem apelido, nem e-mail, nem nome.\n"
        "\n"
        "O selo tambem viaja como EVENTO, `pages.portfolio.conferido.v1`, para\n"
        "quem prefere ser avisado a perguntar.\n"
        "\n"
        "Lei do assunto: docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md e o\n"
        "corredor docs/changespecs/CS-PAGES-0001.md.\n"
    ),
    servers=[{"url": "http://pages:8000/interno"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", portfolio_router)
