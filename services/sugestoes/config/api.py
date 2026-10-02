# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.api import router as sessao_router
from apps.core.api_gestao import router as gestao_router
from apps.core.auth import bearerAuth

# `servers` é o endereço da rede interna do Docker que o `funil` usa.
# Pela borda pública, quem fecha `/interno` é o Bearer do par (401 sem token).
api = NinjaAPI(
    title="Caixa de Sugestoes — API interna",
    version="1.0.0",
    description=(
        "Superfície de MÁQUINA da Caixa, com duas metades.\n"
        "\n"
        "A primeira existe por uma razão só: o site (`funil`) precisa saber\n"
        "quem é a pessoa em qualquer página, e o cookie de sessão é assinado e\n"
        "resolvido AQUI (o segredo de assinatura não sai desta\n"
        "célula). Lei do assunto: docs/decisoes/DECISAO-onde-mora-a-sessao.md.\n"
        "\n"
        "A segunda é a GESTÃO das ideias, que desde 28/08/2026 mora em\n"
        "`/admin/caixa/` e não mais nas telas desta célula (decisão do\n"
        "mantenedor: uma porta só). O Admin pergunta e escreve por aqui. A resposta carrega os\n"
        "FATOS de cada ideia — nunca colunas nem ordenação, que são da tela — e\n"
        "nunca o e-mail de quem sugeriu. Lei do assunto:\n"
        "docs/decisoes/DECISAO-a-gestao-da-caixa-mora-no-admin.md.\n"
        "\n"
        "Nenhuma resposta desta API AUTORIZA nada: autorização é fail-closed na\n"
        "célula dona do recurso — e a assinatura de obra continua sendo desta.\n"
    ),
    servers=[{"url": "http://sugestoes:8000/interno"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", sessao_router)
# A gestão entra no mesmo documento e sob o mesmo Bearer (mesma fronteira de máquina).
api.add_router("", gestao_router)
