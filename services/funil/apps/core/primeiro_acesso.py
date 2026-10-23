"""Observa páginas reais servidas, sem interferir no acesso ou registrar recursos."""
import logging
import os
import httpx

logger = logging.getLogger(__name__)
ORIGEM = 'funil'
_DIAGNOSTICOS = set()

class PrimeiroAcesso:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)
        if request.method == 'GET' and resposta.get('Content-Type', '').startswith('text/html'):
            # Só enumera condições de captura. Nunca guarda identidade, cookie ou caminho.
            destino = request.headers.get('Sec-Fetch-Dest', 'ausente')
            destino = destino if destino in ('document', 'iframe', 'empty', 'ausente') else 'recurso'
            condicoes = (bool(request.COOKIES.get('meshcraft_sessao')),
                         bool(request.COOKIES.get('meshcraft_ver_como')),
                         'prefetch' in (request.headers.get('Purpose', '') + request.headers.get('Sec-Purpose', '')).lower(), destino)
            if condicoes not in _DIAGNOSTICOS:
                _DIAGNOSTICOS.add(condicoes)
                logger.warning('primeiro acesso: condições sessão=%s simulação=%s pré-carga=%s destino=%s', *condicoes)
        if (request.method != 'GET' or not 200 <= resposta.status_code < 300
                or resposta.get('Content-Type', '').split(';')[0] != 'text/html'
                or not request.COOKIES.get('meshcraft_sessao')
                or request.COOKIES.get('meshcraft_ver_como')
                or 'prefetch' in (request.headers.get('Purpose', '') + request.headers.get('Sec-Purpose', '')).lower()
                or request.headers.get('X-Requested-With', '').lower() == 'xmlhttprequest'):
            return resposta
        site = getattr(request, 'site', None)
        site_id = site.get('id') if isinstance(site, dict) else os.environ.get('SITE_ID', '')
        base = (os.environ.get('ALUNOS_API_URL') or '').rstrip('/')
        token = os.environ.get('ALUNOS_API_TOKEN', '')
        if not (site_id and base and token):
            logger.warning('primeiro acesso: ligação com alunos ou site ausente')
            return resposta
        try:
            with httpx.Client(timeout=2.0) as cliente:
                r = cliente.post(base + '/jornada-acesso/observar',
                    json={'site_id': site_id, 'origem': ORIGEM},
                    headers={'Authorization': 'Bearer ' + token,
                             'Cookie': request.META.get('HTTP_COOKIE', '')})
            if r.status_code != 204:
                logger.warning('primeiro acesso: registro não confirmado (HTTP %s)', r.status_code)
        except httpx.HTTPError:
            # Nunca inclui cookie, endereço da pessoa ou corpo no log.
            logger.warning('primeiro acesso: fonte indisponível')
        return resposta
