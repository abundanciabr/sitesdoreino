# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.api import router as notificacoes_router
from apps.core.auth import bearerAuth

# `servers` aponta para a REDE INTERNA do Docker (o par consumidor vive nela),
# nunca para a borda pública — esta célula não tem rota no Traefik (Lei 2 da
# CONSTITUICAO: API interna não tem rota pública).
api = NinjaAPI(
    title="Notificações API",
    version="1.0.0",
    description=(
        "A porta de consulta da caixa central de avisos. Fase 4 do sininho (Rito de\n"
        "Contrato de 27/08/2026, docs/decisoes/DECISAO-fase-4-do-sininho.md). Serve\n"
        "dois consumidores: o `funil` (o sininho ao lado do nome, em toda página) e\n"
        "a própria `sugestoes` (a tela de avisos da Caixa, que aposenta a leitura\n"
        "local — DECISAO-fase-2-do-sininho.md §3).\n"
        "\n"
        "A notificação é DADO, nunca frase pronta (DECISAO-notificacoes §5.1): esta\n"
        "API devolve tipo + parâmetros, e quem lê monta a frase no idioma de quem\n"
        "está lendo. Nenhuma rota aqui devolve e-mail — o destinatário é sempre o id\n"
        "da PLATAFORMA (DECISAO-EVO-01 §3).\n"
        "\n"
        'Toda rota exige `site_id` (CONSTITUICAO.md Lei 9 — "site_id acompanha toda\n'
        'entidade pública"; decisão confirmada em 27/08/2026, na mesma sessão da\n'
        "Fase 4): os avisos de uma pessoa são sempre os do site de onde a chamada\n"
        "vem, nunca um apanhado de todo site que ela já tiver tocado. `notificacao.\n"
        "devida.v1` já carrega `site_id` no fato desde a Fase 2 — esta rota só\n"
        "passa a exigir, na leitura, o mesmo dado que a escrita já grava.\n"
    ),
    servers=[{"url": "http://notificacoes:8000/api/notificacoes"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", notificacoes_router)
