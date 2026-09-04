"""As views da célula `metricas` (o livro de fatos da plataforma).

Na gênese existe uma só: a sonda. A recepção de eventos e a API de leitura
nascem nos degraus 7.3 e 7.4 da escada do plano do painel de gestão
(`docs/decisoes/PLANO-PAINEL-DE-GESTAO.md` §6.2), depois da tabela do evento
imutável (7.2) — tabelas e motor antes de qualquer porta, como no fórum, na
gamificação e nas encomendas.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def healthz(request):
    """A sonda do container. Rota de MÁQUINA.

    Ela responde nas DUAS formas de entrada, porque as duas existem em
    produção: `/healthz` pelo healthcheck do compose e, se um dia esta célula
    ganhar borda pública, `/metricas/healthz` pela internet (o Traefik **não**
    remove o prefixo — `armadilhas/029`).

    Quando a porta de autorização nascer (degrau 7.3), a isenção desta rota
    tem de ser comparada por `request.path_info` — **nunca** `request.path`,
    que pela borda pública contém o prefixo. Guarda:
    `tests/test_healthz_script_name.py`.
    """
    return JsonResponse({"status": "ok"})
