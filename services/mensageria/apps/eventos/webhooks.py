"""Entrada do provedor para devoluções e reclamações."""

from __future__ import annotations

import json
import secrets

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .tasks import marcar_email_como_bloqueado


@csrf_exempt
@require_POST
def webhook_email(request):
    """Registra o evento do provedor sem permitir efeito sem autenticação."""

    token = settings.EMAIL_WEBHOOK_TOKEN
    recebido = request.headers.get("X-Webhook-Token", "")
    if not token or not secrets.compare_digest(recebido, token):
        return JsonResponse(
            {"erro": "webhook recusado; configure e envie o token correto"},
            status=403,
        )
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"erro": "corpo invalido; envie JSON com email e event"}, status=400
        )

    email = payload.get("email")
    evento = str(payload.get("event", "")).lower()
    if not isinstance(email, str) or not email.strip():
        return JsonResponse(
            {"erro": "email ausente; envie o endereco declarado pelo provedor"},
            status=400,
        )
    if "complaint" in evento or "spam" in evento:
        motivo = "reclamacao"
    elif "bounce" in evento or "blocked" in evento:
        motivo = "devolucao"
    else:
        return JsonResponse(
            {"erro": "evento ignorado; use bounce ou complaint"}, status=400
        )
    bloqueio = marcar_email_como_bloqueado(email, motivo)
    return JsonResponse({"bloqueado": bloqueio.email, "motivo": bloqueio.motivo})
