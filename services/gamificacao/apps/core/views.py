"""As views da célula `gamificacao`.

Na gênese existe uma só: a sonda. Tudo o mais — a Base em `/conquistas`, o
Passaporte dos Marcos, a loja de Cristais, o Meu Estúdio — nasce depois da
fundação (`DECISAO-gamificacao.md` §7: modelo de dados e contrato antes de
qualquer tela, como no fórum e na identidade).
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def healthz(request):
    """A sonda do container. Rota de MÁQUINA.

    Ela responde nas DUAS formas de entrada, porque as duas existem em
    produção: `/conquistas/healthz` pela internet (o Traefik **não** remove o
    prefixo) e `/healthz` pelo healthcheck do compose (`armadilhas/029`).

    Quando esta célula ganhar uma porta de autorização, a isenção desta rota
    tem de ser comparada por `request.path_info` — **nunca** `request.path`,
    que pela borda pública contém o prefixo. Guarda:
    `tests/test_healthz_script_name.py`.
    """
    return JsonResponse({"status": "ok"})
