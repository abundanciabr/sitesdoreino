# apps/core/middleware.py  # [RECEITA:CONV-SITE v1]
import time

from django.http import Http404

from apps.core.clients import CatalogoClient

_CACHE: dict = {}
TTL_SEGUNDOS = 60

# /healthz é sonda do container e do gateway — chega sem Host de site e não pode
# depender do catálogo estar de pé. Estáticos idem.
CAMINHOS_SEM_SITE = ("/healthz", "/static/")


def limpar_cache_de_sites() -> None:
    _CACHE.clear()


class SiteResolutionMiddleware:
    """[INV-P11] Resolve Host→Site UMA vez por requisição, via catálogo (com cache).
    Host não cadastrado ⇒ 404 — nunca um site padrão."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # [H10.1 / ARMADILHAS §4.10] path_info, NUNCA request.path: com
        # SCRIPT_NAME=/checkout (FORCE_SCRIPT_NAME), no Django 5.0.x o
        # request.path vira "/checkout/healthz" e a isenção deixa de casar —
        # a sonda cai na resolução de site e o healthcheck morre em 404.
        # request.path_info segue "/healthz" independente do prefixo do gateway.
        if request.path_info.startswith(CAMINHOS_SEM_SITE):
            return self.get_response(request)
        host = request.get_host().split(":")[0].lower()
        site = self._resolver(host)
        if site is None:
            raise Http404("site desconhecido")
        request.site = site  # todo o resto da célula lê daqui
        return self.get_response(request)

    def _resolver(self, host: str):
        hit = _CACHE.get(host)
        if hit and hit[0] > time.time():
            return hit[1]
        site = CatalogoClient().obter_site_por_host(host)
        _CACHE[host] = (time.time() + TTL_SEGUNDOS, site)  # cacheia inclusive o 404
        return site
