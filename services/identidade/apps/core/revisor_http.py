"""Candidate transport view to be installed in the identity provider itself.

This is NOT imported by Revisor. The provider remains the owner of session data.
"""
import hmac
import os
from django.conf import settings
from django.http import JsonResponse


def revisor_session(request):
    # Use the actual socket peer, never client-controlled forwarded headers.
    peer = os.environ.get('REVISOR_GATEWAY_IP', '')
    if not peer or request.META.get('REMOTE_ADDR') != peer:
        return JsonResponse({'error': 'private_transport'}, status=403)
    if request.method != 'GET':
        return JsonResponse({'error': 'method_denied'}, status=405)
    token = os.environ.get('TOKENS_ACEITOS_REVISOR', '')
    if (not token or not hmac.compare_digest(request.headers.get('Authorization', ''), 'Bearer '+token)
            or token not in settings.TOKENS_ACEITOS or token not in settings.TOKENS_COMPLETOS):
        return JsonResponse({'error': 'unauthorized'}, status=401)
    from .api import sessao_completa
    request.auth = token
    response = JsonResponse(sessao_completa(request))
    response['Cache-Control'] = 'no-store'
    return response
