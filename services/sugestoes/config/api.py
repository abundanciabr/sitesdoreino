# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.api import router as sessao_router
from apps.core.auth import bearerAuth

# `servers` aponta para a REDE INTERNA do Docker, nunca para a borda pública —
# é o endereço que o `funil` põe no env dele. O caminho `/interno` não tem
# router no Traefik de propósito (`infra/traefik/dynamic/plataforma.yml` roteia
# `/forms/sugestoes`, que é a superfície de GENTE desta célula).
#
# Ressalva honesta, para ninguém achar que está mecanizado: como o Traefik
# roteia o prefixo inteiro da Caixa, `…/forms/sugestoes/interno/sessao` TAMBÉM
# resolve pela borda pública. Quem fecha essa porta hoje é o Bearer do par
# (401 sem token, e o conjunto de tokens nasce vazio). A trava de verdade — uma
# regra de negação no gateway — é um degrau acima na Lei 1 e mora em `infra/`,
# fora do alcance de um PR de célula; está registrada como dívida no
# `LICOES.md` desta célula.
api = NinjaAPI(
    title="Caixa de Sugestoes — API interna",
    version="1.0.0",
    description=(
        "Superfície de MÁQUINA da Caixa. Existe por uma razão só: o site\n"
        "(`funil`) precisa saber quem é a pessoa em qualquer página, e o cookie\n"
        "de sessão é assinado e resolvido AQUI (Lei 2, Lei 3 — o banco e o\n"
        "segredo não saem desta célula).\n"
        "\n"
        "Lei do assunto: docs/decisoes/DECISAO-onde-mora-a-sessao.md. A resposta\n"
        "desta API RECONHECE uma pessoa; ela nunca AUTORIZA nada — autorização\n"
        "é fail-closed na célula dona do recurso.\n"
    ),
    servers=[{"url": "http://sugestoes:8000/interno"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", sessao_router)
