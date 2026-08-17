# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.api import router as checkout_router
from apps.core.auth import bearerAuth

api = NinjaAPI(
    title="Checkout API",
    version="1.0.0",
    description=(
        "Sessões de checkout e pedidos com snapshot imutável (INV-P1/P2).\n"
        "O cliente envia INTENÇÃO (bump_ids marcados); o SERVIDOR recalcula tudo do catálogo\n"
        "e congela o snapshot — client-sends-intent / server-validates.\n"
        "Multissítio: o site NUNCA vem no payload — é resolvido do Host da requisição\n"
        "(middleware CONV-SITE); host desconhecido é 404 (INV-P11). Sessão, pedido e\n"
        "eventos carregam o site_id resolvido.\n"
        "Rotas públicas via gateway: as páginas /checkout/*. Esta API JSON é interna\n"
        "(usada pelas próprias páginas da célula) e não é consumida por outras células,\n"
        "exceto GET /pedidos/{id} pela suíte E2E.\n"
    ),
    servers=[{"url": "http://checkout:8000/api/checkout"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", checkout_router)
