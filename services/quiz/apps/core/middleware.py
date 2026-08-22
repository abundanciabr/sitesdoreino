# apps/core/middleware.py  # [RECEITA:CONV-SITE v1] — adaptado: resolução LOCAL
from django.http import Http404

from apps.quiz.models import Site

# /healthz é sonda do container e do gateway — chega sem Host de site. Estáticos idem.
CAMINHOS_SEM_SITE = ("/healthz", "/static/")


class SiteResolutionMiddleware:
    """[INV-P11] Resolve Host→Site UMA vez por requisição.

    Diferente das demais células públicas, aqui a resolução NÃO chama a API do
    catálogo — é uma consulta ao cadastro local de `apps.quiz.models.Site`
    (ver LICOES.md desta célula: AGENTS.quiz.md declara "Consome: nada" e não
    autoriza leitura de contracts/catalogo.openapi.yaml). Por ser uma consulta
    local indexada, dispensa o cache de 60s do TTL usado quando a resolução é
    via HTTP. Host não cadastrado ⇒ 404 — nunca um site padrão.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # [H10.1 / ARMADILHAS §4.10] path_info, NUNCA request.path: com
        # SCRIPT_NAME=/quiz (FORCE_SCRIPT_NAME) o Traefik NÃO remove o prefixo
        # e a borda pública chega como "/quiz/healthz" — request.path inclui o
        # prefixo, a isenção deixa de casar e a sonda morre em 404 na resolução
        # de site (medido ao vivo em 22/08/2026 na basileiatoutheou.org).
        # request.path_info segue "/healthz" independente do prefixo do gateway.
        if request.path_info.startswith(CAMINHOS_SEM_SITE):
            return self.get_response(request)
        host = request.get_host().split(":")[0].lower()
        site = (
            Site.objects.filter(host=host, active=True)
            .values("id", "host", "name")
            .first()
        )
        if site is None:
            raise Http404("site desconhecido")
        request.site = site  # todo o resto da célula lê daqui: request.site["id"]
        return self.get_response(request)
