# apps/core/middleware.py  # [RECEITA:CONV-SITE v1] + resolver de idioma
# (PLANO-I18N §2 D1 — matriz HTTP; site fora do registro = fluxo de hoje).
import re
import time

from django.http import Http404, HttpResponseRedirect
from django.utils import translation

from apps.core.clients import CatalogoClient
from apps.i18n.registro import dados_seo, registro_do_host

_CACHE: dict = {}
TTL_SEGUNDOS = 60

# /healthz é sonda do container e do gateway — chega sem Host de site e não pode
# depender do catálogo estar de pé. Estáticos idem. /sitemap.xml é rota de
# MÁQUINA (D6): sem prefixo de idioma e sem depender do catálogo — a view lê o
# Host direto do registro i18n. A isenção roda ANTES de QUALQUER lógica
# (inclusive a de idioma): rota de máquina nunca se localiza.
CAMINHOS_SEM_SITE = ("/healthz", "/static/", "/sitemap.xml")

# D1/D6: primeiro segmento com FORMA de idioma (2-3 letras ± região, qualquer
# caixa/separador) que NÃO seja código habilitado ⇒ 404 fail-closed — cobre
# /fr/, /PT-BR/, /pt_br/ de uma vez. Caminho sem forma de idioma é "caminho nu".
RE_FORMA_DE_IDIOMA = re.compile(r"[A-Za-z]{2,3}([_-][A-Za-z0-9]{2,8})?\Z")

# O redirect é determinístico por decisão (nunca varia por usuário) ⇒ cacheável;
# max-age curto propaga troca de default em minutos (D1).
CACHE_DO_REDIRECT = "max-age=300"
METODOS_SEGUROS = ("GET", "HEAD")


def limpar_cache_de_sites() -> None:
    _CACHE.clear()


class SiteResolutionMiddleware:
    """[INV-P11] Resolve Host→Site UMA vez por requisição, via catálogo (com cache).
    Host não cadastrado ⇒ 404 — nunca um site padrão. Site cadastrado no
    registro i18n (sites_i18n.yaml) ⇒ resolve também o idioma do prefixo."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # ARMADILHAS §4.10: SEMPRE path_info, nunca path — request.path inclui
        # o script name/prefixo de gateway e a isenção deixaria de casar.
        if request.path_info.startswith(CAMINHOS_SEM_SITE):
            return self.get_response(request)
        host = request.get_host().split(":")[0].lower()
        site = self._resolver(host)
        if site is None:
            raise Http404("site desconhecido")
        request.site = site  # todo o resto da célula lê daqui
        cfg = registro_do_host(host)
        if cfg is None:
            # Site monolíngue (fora do registro): fluxo de hoje, intocado.
            return self.get_response(request)
        return self._com_idioma(request, site, cfg)

    def _resolver(self, host: str):
        hit = _CACHE.get(host)
        if hit and hit[0] > time.time():
            return hit[1]
        site = CatalogoClient().obter_site_por_host(host)
        _CACHE[host] = (time.time() + TTL_SEGUNDOS, site)  # cacheia inclusive o 404
        return site

    def _com_idioma(self, request, site, cfg):
        caminho = request.path_info
        seguro = request.method in METODOS_SEGUROS

        # Raiz: 302 fixo p/ /{default}/ — nunca 301 (301 cacheado travaria a
        # troca de default). Só GET/HEAD; POST perderia o corpo no redirect.
        if caminho == "/":
            if not seguro:
                raise Http404("raiz de site multilíngue não aceita método não-seguro")
            return self._redirect(f"/{cfg['default']}/", request)

        segmento, barra, resto = caminho[1:].partition("/")
        if segmento in cfg["idiomas"]:
            if not barra:  # /en → /en/ (uma forma canônica por página)
                if not seguro:
                    raise Http404("prefixo de idioma sem caminho")
                return self._redirect(f"/{segmento}/", request)
            definicao = cfg["idiomas"][segmento]
            caminho_sem_prefixo = f"/{resto}"
            request.idioma = segmento
            request.i18n = cfg
            request.i18n_seo = dados_seo(site, cfg, segmento, caminho_sem_prefixo)
            # O urlconf da célula continua sem prefixo: o resolver decapa o
            # idioma ANTES da resolução de URL (path_info é o que o Django
            # resolve; request.path segue completo p/ canonical/logs).
            request.path_info = caminho_sem_prefixo
            translation.activate(definicao["tag"])  # D2.4: runtime do Django LIGADO
            try:
                return self.get_response(request)
            finally:
                translation.deactivate()

        if RE_FORMA_DE_IDIOMA.fullmatch(segmento):
            # /fr/…, /PT-BR/…, /pt_br/… — forma de idioma não habilitada:
            # 404 fail-closed, nunca redirect, nunca fallback (D1).
            raise Http404(f"idioma não habilitado para este site: {segmento}")

        # Caminho nu (/cadastro): preserva link curto de marketing via 302;
        # métodos não-seguros ⇒ 404 (redirect converteria POST em GET e
        # descartaria o corpo em silêncio — D1).
        if not seguro:
            raise Http404("caminho sem prefixo de idioma não aceita método não-seguro")
        return self._redirect(f"/{cfg['default']}{caminho}", request)

    @staticmethod
    def _redirect(destino: str, request) -> HttpResponseRedirect:
        query = request.META.get("QUERY_STRING", "")
        if query:
            destino = f"{destino}?{query}"
        resposta = HttpResponseRedirect(destino)
        resposta["Cache-Control"] = CACHE_DO_REDIRECT
        return resposta
