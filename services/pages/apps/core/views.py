"""As views da célula `pages` (a casa das Páginas do aluno).

Na gênese existe uma só: a sonda. Tudo o mais — a Prancheta do portfólio em
`/pages`, as peças coladas por link, o semáforo, o pedido de conferência, a
fila da equipe e a vitrine em `/estudio/<apelido>` — nasce depois da fundação
(`PLANO-PORTFOLIO-DO-ALUNO.md` §5: tabelas, contrato e provisionamento antes
de qualquer tela, como na `encomendas` e na `cursos`).
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def healthz(request):
    """A sonda do container. Rota de MÁQUINA.

    Ela responde nas DUAS formas de entrada, porque as duas existem em
    produção: `/pages/healthz` pela internet (o Traefik **não** remove o
    prefixo) e `/healthz` pelo healthcheck do compose (`armadilhas/029`).

    Quando esta célula ganhar a porta de autorização do degrau 06, a isenção
    desta rota tem de ser comparada por `request.path_info` — **nunca**
    `request.path`, que pela borda pública contém o prefixo. Guarda:
    `tests/test_healthz_script_name.py`.
    """
    return JsonResponse({"status": "ok"})
