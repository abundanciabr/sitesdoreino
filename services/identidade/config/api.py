# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.api import router as sessao_router
from apps.core.auth import bearerAuth

# `servers` aponta para a REDE INTERNA do Docker, nunca para a borda pública —
# é o endereço que `funil` e `sugestoes` põem no env delas. O caminho
# `/interno` não tem router no Traefik de propósito (o Traefik roteia
# `/entrar`, que é a superfície de GENTE desta célula).
#
# Ressalva honesta, herdada da Caixa: nada em `/interno` resolve pela borda
# pública AQUI (o Traefik só manda `/entrar/*` para esta célula), mas quem
# fecha a porta em qualquer topologia futura é o Bearer do par — 401 sem
# token, e o conjunto de tokens nasce vazio.
api = NinjaAPI(
    title="Identidade — API interna",
    version="1.0.0",
    description=(
        "Superfície de MÁQUINA da identidade do site. Existe por uma razão só:\n"
        "qualquer célula precisa saber quem é a pessoa em qualquer página, e o\n"
        "cookie de sessão é assinado e resolvido AQUI (Lei 2, Lei 3 — o banco e\n"
        "o segredo não saem desta célula).\n"
        "\n"
        "Lei do assunto: docs/decisoes/DECISAO-celula-de-identidade.md. A\n"
        "resposta desta API RECONHECE uma pessoa; ela nunca AUTORIZA nada —\n"
        "autorização é fail-closed na célula dona do recurso.\n"
    ),
    servers=[{"url": "http://identidade:8000/interno"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", sessao_router)
