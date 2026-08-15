# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.api import router as leads_router
from apps.core.auth import bearerAuth

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
