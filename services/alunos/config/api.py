# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.api import router as alunos_router
from apps.core.auth import bearerAuth

api = NinjaAPI(
    title="Alunos API",
    version="1.0.0",
    description=(
        "Matrícula e acesso. O caminho NORMAL de matrícula é o evento pagamento.aprovado.v1\n"
        "(consumer da célula). Esta API interna existe para reprocesso manual e consulta —\n"
        "e é idempotente pelas mesmas chaves do consumer (INV-P5).\n"
    ),
    servers=[{"url": "http://alunos:8000/api/alunos"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", alunos_router)

from apps.core.jornada_acesso import router as jornada_router
api.add_router("", jornada_router)
from apps.core.medicoes_acesso import router as medicoes_router
api.add_router("", medicoes_router)

from apps.core.registrar_acesso import router as acesso_observado_router
api.add_router('', acesso_observado_router)
