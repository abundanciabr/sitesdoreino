# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.api import router as leads_router
from apps.core.auth import bearerAuth
from apps.core.oportunidades import router as oportunidades_router
from apps.core.crm import router as crm_router
from apps.core.perfil import router as perfil_router
from apps.core.quiz_do_lead import router as quiz_do_lead_router

api = NinjaAPI(
    title="Leads API",
    version="1.0.0",
    description=(
        "Pessoas antes do dinheiro: upsert de lead, tags e timeline. API INTERNA.\n"
        "Consumida pelo funil (captura) e alimentada por eventos (quiz, pedido, pagamento).\n"
    ),
    servers=[{"url": "http://leads:8000/api/leads"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", leads_router)
api.add_router("", oportunidades_router)
api.add_router("", crm_router)
api.add_router("", quiz_do_lead_router)
api.add_router("", perfil_router)
