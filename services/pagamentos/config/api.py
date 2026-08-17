# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from pagamentos.api.auth import bearerAuth
from pagamentos.api.intents import router as intents_router
from pagamentos.api.webhooks import router as webhooks_router

api = NinjaAPI(
    title="Pagamentos API",
    version="1.0.0",
    description=(
        "Única célula da plataforma com credenciais Mercado Pago (INV-P8).\n"
        "Consumida exclusivamente pelo checkout, via token Bearer dedicado por par.\n"
        "CONGELÁVEL: após ratificação, qualquer mudança exige o Rito de Contrato (RITOS.md §3).\n"
        "Rotas públicas via gateway: SOMENTE /webhooks/mp/*. Todo o resto vive na rede interna Docker.\n"
    ),
    servers=[{"url": "http://pagamentos:8000/api/pagamentos"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", intents_router)
api.add_router("/webhooks", webhooks_router, auth=None)
