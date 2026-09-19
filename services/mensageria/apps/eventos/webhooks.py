"""Entrada do provedor para devoluções e reclamações."""

from __future__ import annotations

import json
import secrets

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .tasks import marcar_email_como_bloqueado


EVENTOS_PERMANENTES = {
    "hard_bounce",
    "hardbounce",
    "invalid",
    "invalid_email",
    "blocked",
    "spam",
    "complaint",
}
EVENTOS_TRANSITORIOS = {"soft_bounce", "softbounce", "deferred"}


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
    if not isinstance(payload, dict):
        return JsonResponse(
            {"erro": "corpo invalido; envie um objeto JSON com email e event"},
            status=400,
        )

    email = payload.get("email")
    evento = str(payload.get("event", "")).lower().replace("-", "_")
    if not isinstance(email, str) or not email.strip():
        return JsonResponse(
            {"erro": "email ausente; envie o endereco declarado pelo provedor"},
            status=400,
        )
    if evento in EVENTOS_TRANSITORIOS:
        return JsonResponse({"ignorado": evento, "motivo": "transitorio"}, status=202)
    if evento not in EVENTOS_PERMANENTES:
        return JsonResponse(
            {
                "erro": "evento ignorado; envie hard_bounce, invalid_email, blocked ou spam"
            },
            status=400,
        )
    motivo = "reclamacao" if evento in {"spam", "complaint"} else "devolucao"
    bloqueio = marcar_email_como_bloqueado(email, motivo)
    return JsonResponse({"bloqueado": bloqueio.email, "motivo": bloqueio.motivo})
