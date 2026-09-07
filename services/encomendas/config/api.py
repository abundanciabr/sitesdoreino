# config/api.py
from ninja import NinjaAPI

from apps.core.api import router as encomendas_router
from apps.core.auth import bearerAuth

# `servers` aponta para a REDE INTERNA do Docker: é o endereço que outra célula
# porá no env dela, e é o mesmo que o rascunho em papel do contrato já previa
# (`servers: /api/encomendas`). Este valor entra no congelado do degrau 2.8, e a
# partir de lá mudá-lo é Rito de Contrato (`RITOS.md` §3), nunca edição aqui.
#
# ATENCAO, e aqui esta célula é como o `forum` e a `gamificacao`, e diferente da
# `identidade`: esta porta É alcançável pela borda pública, em
# `meshcraft.top/encomendas/api/encomendas/...` e, o que assusta mais,
# `meshcraft.top/encomendas/api/encomendas/interno/...`. A célula roda sob
# `SCRIPT_NAME=/encomendas` e o handler ASGI do Django faz
# `path_info = path.removeprefix(script_name)`. É o mesmo corte que faz
# `meshcraft.top/encomendas/healthz` responder 200 com o `urls.py` declarando
# `path("healthz", ...)` sem prefixo nenhum (`armadilhas/186`; a premissa está
# fixada em `tests/test_healthz_script_name.py`).
#
# ENTAO QUEM FECHA A PORTA E O BEARER, E SO ELE. Não existe segunda camada por
# baixo, e escrever no comentário que "o interno não resolve pela borda" seria
# copiar da `identidade` uma frase que lá é verdadeira e aqui é falsa. O guarda
# que vale é o teste de 401 em TODAS as operações, mais o teste que mede o
# `/interno` pelo caminho público.
api = NinjaAPI(
    title="Encomendas - API interna",
    version="1.0.0",
    description=(
        "Superficie de maquina da Fila do Primeiro Dolar. Quem consome: o Admin\n"
        "(parametros), a home e o Estudio (fila de uma pessoa, pecas aprovadas),\n"
        "a celula de pagamentos (pagamento confirmado, Fase 3) e o worker de\n"
        "auditoria (resultado, Fase 5).\n"
        "\n"
        "O Bearer prova QUEM CHAMA, nunca quem e a pessoa: nao chega cookie aqui.\n"
        "Por isso nenhuma porta desta superficie ACEITA, PASSA, ENTREGA ou APROVA\n"
        "nada em nome de um aluno ou de um cliente. Esses gestos sao das telas,\n"
        "onde a pessoa esta atras do login.\n"
        "\n"
        "SAO DOIS GRAUS DE CRACHA, e o segundo existe porque esta porta ESCREVE.\n"
        "Ler a fila de alguem (TOKENS_ACEITOS_<PAR>) e mudar um parametro do dono\n"
        "ou confirmar dinheiro (TOKENS_ESCRITA_<PAR>) nao sao o mesmo poder: o par\n"
        "que so desenha tela recebe 403 nas tres operacoes que gravam.\n"
        "\n"
        "Nao sai dado de contato do aluno por porta nenhuma (INV-ENC-S3), e so\n"
        "saem pecas com autorizacao do cliente registrada (INV-ENC-S4).\n"
        "\n"
        "SITE_ID ausente no env desta celula e 503, nunca uma lista vazia com 200.\n"
        "\n"
        "Lei do assunto: docs/decisoes/DECISAO-fila-do-primeiro-dolar.md.\n"
    ),
    servers=[{"url": "http://encomendas:8000/api/encomendas"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", encomendas_router)
