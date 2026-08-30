# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.api import router as gamificacao_router
from apps.core.auth import bearerAuth

# `servers` aponta para a REDE INTERNA do Docker — é o endereço que outra célula
# porá no env dela. O valor está CONGELADO em `contracts/gamificacao.openapi.yaml`
# (Sessão B, 30/08/2026); mudá-lo é Rito de Contrato (RITOS.md §3), nunca edição
# aqui.
#
# ENDEREÇO — a divergência conhecida, resolvida a favor do contrato: o
# comentário de `config/urls.py`, escrito na gênese, previa esta porta em
# `/interno/` (o formato de `identidade` e `forum`). O contrato congelou
# `/api/gamificacao/` (o formato de `alunos`, `catalogo` e `notificacoes`), e é
# o contrato que manda. O comentário da gênese foi corrigido no mesmo PR.
#
# ATENÇÃO, E AQUI ESTA CÉLULA É COMO O `forum` E DIFERENTE DA `identidade`:
# esta porta **é** alcançável pela borda pública, em
# `meshcraft.top/conquistas/api/gamificacao/...`. A célula roda sob
# `SCRIPT_NAME=/conquistas` e o handler ASGI do Django faz
# `path_info = path.removeprefix(script_name)` — é o mesmo corte que faz
# `meshcraft.top/conquistas/healthz` responder 200 com o `urls.py` declarando
# `path("healthz", ...)` sem prefixo nenhum (`armadilhas/186`; a premissa está
# fixada em `tests/test_healthz_script_name.py`).
#
# ENTÃO QUEM FECHA A PORTA É O BEARER, E SÓ ELE: 401 sem token, e o conjunto de
# tokens nasce VAZIO (`settings.TOKENS_ACEITOS`). Não há segunda camada por
# baixo — a topologia não ajuda aqui como ajuda na `identidade`, e é por isso
# que o guarda de 401 em `tests/test_porta_de_maquina.py` cobre as DUAS
# operações e o caso do env ausente, em vez de confiar no roteador.
api = NinjaAPI(
    title="Gamificacao — API interna",
    version="1.0.0",
    description=(
        "Superficie de MAQUINA do Sistema de Formacao de Criadores.\n"
        "Existe para que o resto da plataforma dependa do CONTRATO e nunca do\n"
        "motor de XP: quem consome le nivel, titulo e sequencia por aqui, e o\n"
        "motor por baixo pode ser trocado sem ninguem do outro lado saber.\n"
        "\n"
        "Lei do assunto: docs/decisoes/DECISAO-gamificacao.md.\n"
        "\n"
        "NADA DE DADO PESSOAL SAI POR AQUI: nem e-mail, nem nome, nem texto\n"
        "escrito por aluno. Só id opaco, número e slug. O público desta escola é\n"
        "majoritariamente menor de idade.\n"
        "\n"
        "E NADA DE XP DE TERCEIRO: `getPublicProfiles` devolve nivel e titulo;\n"
        "XP so aparece em `getMyStatus`, e so o proprio. Placar de XP entre\n"
        "alunos nao existe nesta plataforma.\n"
    ),
    servers=[{"url": "http://gamificacao:8000/api/gamificacao"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", gamificacao_router)
