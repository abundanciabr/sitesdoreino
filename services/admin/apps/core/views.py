"""O esqueleto da área administrativa — por enquanto, só a sonda.

A célula `admin` nasce vazia de propósito (`DECISAO-celula-admin.md` §6, a
escada de entrega): este PR entrega a casa, o `deploy-celula` e o rollback;
a PORTA (quem entra, e o que acontece quando a `identidade` está fora do ar)
vem no PR 3, com os testes-guarda dela no mesmo PR.

**Nada nesta célula responde a visitante anônimo além do `/healthz`.** Quando a
porta chegar, ela é fail-CLOSED — o inverso do site público — e a lista de
caminhos isentos será enumerada e guardada por igualdade exata, para rota nova
não escapar em silêncio (`DECISAO-celula-admin.md` §3).
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def healthz(request):
    """A sonda do container. Rota de MÁQUINA, e a única pública desta célula.

    Quando o middleware da porta nascer (PR 3), a isenção dele compara
    `request.path_info`, **nunca** `request.path` — pela borda pública o
    Traefik não remove o prefixo, e `request.path` chega como `/admin/healthz`
    (`armadilhas/029`, medido ao vivo em duas células). E a isenção precisa
    valer para as DUAS formas de entrada, porque as duas existem em produção:
    `/admin/healthz` pela internet e `/healthz` pelo healthcheck do compose
    (`tests/test_healthz_script_name.py` trava as duas).
    """
    return JsonResponse({"status": "ok"})
