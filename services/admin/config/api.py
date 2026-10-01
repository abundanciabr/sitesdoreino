# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.api import router as interno_router
from apps.core.auth import bearerAuth

# `servers` aponta para a REDE INTERNA do Docker: é o endereço que outra célula
# porá no env dela. O valor congela em `contracts/admin.openapi.yaml`; depois
# disso, mudá-lo é Rito (RITOS.md §3), nunca edição aqui.
#
# ATENÇÃO, E AQUI ESTA CÉLULA É COMO O `forum`, A `cursos` E A `pages`, E
# DIFERENTE DA `identidade`: esta porta **é** alcançável pela borda pública, em
# `meshcraft.top/admin/interno/...`. A célula roda sob `SCRIPT_NAME=/admin` e o
# handler ASGI do Django faz `path_info = path.removeprefix(script_name)`; é o
# mesmo corte que faz `meshcraft.top/admin/healthz` responder 200 com o
# `urls.py` declarando `path("healthz", ...)` sem prefixo nenhum
# (`armadilhas/186`; a premissa está fixada em
# `tests/test_healthz_script_name.py`).
#
# ENTÃO QUEM FECHA A PORTA É O BEARER, E SÓ ELE: 401 sem token, e o conjunto de
# tokens nasce VAZIO (`settings.TOKENS_ACEITOS`). A porta de GENTE desta célula
# (o middleware fail-closed de `apps/core/porta.py`) não vale aqui de propósito
# — máquina não tem cookie de navegador para apresentar, e passá-la por lá
# trocaria o 401 por um 302 para a tela de login. Por isso o guarda de
# `tests/test_porta_de_maquina.py` cobre o sem-token, o token errado e o
# conjunto vazio, em vez de confiar no roteador ou no middleware.
api = NinjaAPI(
    title="Admin - API interna",
    version="1.0.0",
    description=(
        "Porta de máquina da área administrativa. A consulta de administradores "
        "preserva o bearer por par."
    ),
    servers=[{"url": "http://admin:8000/interno"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", interno_router)
