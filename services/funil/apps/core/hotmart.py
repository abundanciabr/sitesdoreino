"""Endpoint estável da Hotmart; a recepção persistente pertence ao admin."""
import httpx
from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_POST

DESTINO = 'https://meshcraft.top/admin/hotmart/webhooks'
LIMITE = 1024 * 1024


def resposta(dados, status):
    r = JsonResponse(dados, status=status)
    r['Cache-Control'] = 'no-store'
    return r


@csrf_exempt
@require_POST
@sensitive_variables()
def webhook(request):
    if request.get_host().split(':')[0].lower() != 'meshcraft.top':
        return resposta({'erro': 'nao_encontrado'}, 404)
    token = request.headers.get('X-Hotmart-Hottok', '')
    if not token or len(token) > 512:
        return resposta({'erro': 'nao_autorizado'}, 401)
    if request.content_type != 'application/json':
        return resposta({'erro': 'envie_json'}, 415)
    try:
        if int(request.META.get('CONTENT_LENGTH') or 0) > LIMITE:
            return resposta({'erro': 'corpo_muito_grande'}, 413)
        corpo = request.body
        if len(corpo) > LIMITE:
            return resposta({'erro': 'corpo_muito_grande'}, 413)
        # Destino fixo HTTPS, sem cookies, sem redirects e sem registrar o corpo.
        r = httpx.post(DESTINO, content=corpo,
                       headers={'Content-Type': 'application/json', 'X-Hotmart-Hottok': token},
                       timeout=8.0, follow_redirects=False, trust_env=False)
        if r.status_code in (200, 400, 401, 413, 415, 503):
            return resposta(r.json(), r.status_code)
    except RequestDataTooBig:
        return resposta({'erro': 'corpo_muito_grande'}, 413)
    except (ValueError, httpx.HTTPError, OSError):
        pass
    return resposta({'erro': 'recepcao_indisponivel'}, 503)
