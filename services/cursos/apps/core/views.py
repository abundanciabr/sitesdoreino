"""As views da célula `cursos` (a sala de aula da Meshcraft).

Na gênese existe uma só: a sonda. Tudo o mais — o mapa das portas em
`/cursos`, a aula em `/cursos/<numero>`, o laudo recebido, o plantão da
professora com o botão "Rascunhar laudo" — nasce depois da fundação
(`PLANO-CELULA-CURSOS.md` §10: tabelas de conteúdo, porta de máquina e editor
antes de qualquer tela do aluno, como nas encomendas e na gamificação).
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def healthz(request):
    """A sonda do container. Rota de MÁQUINA.

    Ela responde nas DUAS formas de entrada, porque as duas existem em
    produção: `/cursos/healthz` pela internet (o Traefik **não** remove o
    prefixo) e `/healthz` pelo healthcheck do compose (`armadilhas/029`).

    Quando esta célula ganhar uma porta de autorização, a isenção desta rota
    tem de ser comparada por `request.path_info` — **nunca** `request.path`,
    que pela borda pública contém o prefixo. Guarda:
    `tests/test_healthz_script_name.py`.
    """
    return JsonResponse({"status": "ok"})
