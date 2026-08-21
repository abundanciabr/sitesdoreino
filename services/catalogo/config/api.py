# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.api import router as catalogo_router
from apps.core.auth import bearerAuth

api = NinjaAPI(
    title="Catalogo API",
    version="1.0.0",
    description=(
        "Fonte da verdade de SITES, produtos, ofertas e bumps. API INTERNA (rede Docker;\n"
        "sem rota pública no gateway). Consumida por funil, quiz, checkout e alunos via\n"
        "Bearer dedicado por par. Multissítio: o catálogo é o registro canônico de sites;\n"
        "as células públicas resolvem Host→Site aqui (middleware CONV-SITE, cache 60s).\n"
    ),
    servers=[{"url": "http://catalogo:8000/api/catalogo"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", catalogo_router)
# golpe4: comentario trivial e reversivel para teste de orcamento
