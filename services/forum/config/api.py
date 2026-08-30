# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.api import router as forum_router
from apps.core.auth import bearerAuth

# `servers` aponta para a REDE INTERNA do Docker — é o endereço que outra célula
# porá no env dela.
#
# ATENÇÃO, E AQUI ESTA CÉLULA É DIFERENTE DA `identidade`: esta porta **é**
# alcançável pela borda pública, em `meshcraft.top/forum/interno/...`. Não
# copie daqui a frase "nada em /interno resolve pela borda" — na `identidade`
# ela é verdadeira, aqui não.
#
# O motivo é mecânico, e foi medido em 30/08/2026: a `identidade` não tem
# `FORCE_SCRIPT_NAME`, então o `/interno` dela mora na raiz e o Traefik nunca
# roteia aquele prefixo para lá. O fórum roda sob `SCRIPT_NAME=/forum`, e o
# handler ASGI do Django faz `path_info = path.removeprefix(script_name)` — é
# exatamente o que faz `meshcraft.top/forum/healthz` responder 200 com o
# `urls.py` declarando `path("healthz", ...)` sem prefixo nenhum. O mesmo
# corte entrega `/forum/interno/areas` a esta API.
#
# ENTÃO QUEM FECHA A PORTA É O BEARER, E SÓ ELE: 401 sem token, e o conjunto de
# tokens nasce VAZIO (`settings.TOKENS_ACEITOS`). Não há segunda camada por
# baixo — a topologia não ajuda aqui como ajuda na `identidade`, e é por isso
# que o guarda de 401 em `tests/test_porta_de_maquina.py` cobre as três
# operações e o caso do env ausente, em vez de confiar no roteador.
api = NinjaAPI(
    title="Forum — API interna",
    version="1.0.0",
    description=(
        "Superficie de MAQUINA do forum da escola. Existe para que o resto da\n"
        "plataforma dependa do CONTRATO e nunca do motor do forum — foi o\n"
        "ponto 4 do veredito da consultoria de 28/08/2026, e e o que mantem\n"
        "aberta a porta de trocar o motor um dia.\n"
        "\n"
        "Lei do assunto: docs/decisoes/DECISAO-forum-da-escola.md.\n"
        "\n"
        "ESTA PORTA SO RESPONDE SOBRE AREA PUBLICA. Nao ha cookie aqui e nao ha\n"
        "pessoa a reconhecer: o Bearer prova QUEM CHAMA, nunca quem e o\n"
        "visitante. Sem pessoa, o unico recorte honesto e o que qualquer um ja\n"
        "veria de graca. Area de aluno e area de turma nao aparecem por aqui —\n"
        "nem o conteudo, nem a contagem, nem a existencia.\n"
        "\n"
        "E nao sai dado pessoal: nem e-mail, nem quem leu o que. O publico\n"
        "desta escola e majoritariamente menor de idade.\n"
    ),
    servers=[{"url": "http://forum:8000/interno"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", forum_router)
