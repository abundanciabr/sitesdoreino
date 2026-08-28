# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.api import router as sessao_router
from apps.core.api_gestao import router as gestao_router
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
        "Superfície de MÁQUINA da Caixa, com duas metades.\n"
        "\n"
        "A primeira existe por uma razão só: o site (`funil`) precisa saber\n"
        "quem é a pessoa em qualquer página, e o cookie de sessão é assinado e\n"
        "resolvido AQUI (Lei 2, Lei 3 — o banco e o segredo não saem desta\n"
        "célula). Lei do assunto: docs/decisoes/DECISAO-onde-mora-a-sessao.md.\n"
        "\n"
        "A segunda é a GESTÃO das ideias, que desde 28/08/2026 mora em\n"
        "`/admin/caixa/` e não mais nas telas desta célula (decisão do\n"
        "mantenedor: uma porta só). O Admin pergunta e escreve por aqui porque\n"
        "pela Lei 3 nenhuma célula lê o banco de outra. A resposta carrega os\n"
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
# A gestão entra no MESMO documento e sob o MESMO Bearer: é a mesma fronteira de
# máquina desta célula, e um segundo `NinjaAPI` daria um segundo contrato para
# congelar, com um segundo jeito de as duas metades divergirem.
api.add_router("", gestao_router)
