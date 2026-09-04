"""As views da célula `encomendas` (a Fila do Primeiro Dólar).

Na gênese existe uma só: a sonda. Tudo o mais — a tela do aluno em
`/encomendas` (na fila · oportunidade · em andamento), o cardápio do cliente em
`/encomendas/pedir`, o rastreio e o plantão — nasce depois da fundação
(`DECISAO-fila-do-primeiro-dolar.md` §7: tabelas, motor e porta de máquina
antes de qualquer tela, como no fórum e na gamificação).
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def healthz(request):
    """A sonda do container. Rota de MÁQUINA.

    Ela responde nas DUAS formas de entrada, porque as duas existem em
    produção: `/encomendas/healthz` pela internet (o Traefik **não** remove o
    prefixo) e `/healthz` pelo healthcheck do compose (`armadilhas/029`).

    Quando esta célula ganhar uma porta de autorização, a isenção desta rota
    tem de ser comparada por `request.path_info` — **nunca** `request.path`,
    que pela borda pública contém o prefixo. Guarda:
    `tests/test_healthz_script_name.py`.
    """
    return JsonResponse({"status": "ok"})
