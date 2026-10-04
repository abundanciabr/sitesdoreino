"""Retornos da WhatsApp Cloud API: estado das mensagens e dos modelos.

Endereço: /webhooks/whatsapp/cloud. A Meta confirma a assinatura com GET
(hub.verify_token) e assina cada POST com X-Hub-Signature-256 usando o segredo
do app. Sem esses dois valores no ambiente, o retorno é recusado.
Mensagens recebidas (`messages`) não são tratadas aqui: são das conversas.
"""
import hashlib
import hmac
import json
import secrets

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .modelos import aplicar_status, atualizar_estado_de_modelo


def _assinatura_valida(request) -> bool:
    segredo = str(getattr(settings, "WHATSAPP_CLOUD_APP_SECRET", "") or "")
    recebida = request.headers.get("X-Hub-Signature-256", "")
    if not segredo or not recebida.startswith("sha256="):
        return False
    esperada = hmac.new(segredo.encode("utf-8"), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(recebida[7:], esperada)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook_cloud(request):
    if request.method == "GET":
        esperado = str(getattr(settings, "WHATSAPP_CLOUD_VERIFY_TOKEN", "") or "")
        recebido = request.GET.get("hub.verify_token", "")
        if (request.GET.get("hub.mode") == "subscribe" and esperado
                and secrets.compare_digest(recebido, esperado)):
            return HttpResponse(request.GET.get("hub.challenge", ""), content_type="text/plain")
        return JsonResponse({"erro": "nao autorizado"}, status=403)
    if not _assinatura_valida(request):
        return JsonResponse({"erro": "nao autorizado"}, status=403)
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"erro": "JSON invalido"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"erro": "objeto esperado"}, status=400)
    alterados = 0
    for entrada in payload.get("entry") or []:
        if not isinstance(entrada, dict):
            continue
        for mudanca in entrada.get("changes") or []:
            if not isinstance(mudanca, dict) or not isinstance(mudanca.get("value"), dict):
                continue
            valor = mudanca["value"]
            if mudanca.get("field") == "message_template_status_update":
                alterados += int(atualizar_estado_de_modelo(valor))
                continue
            for status in valor.get("statuses") or []:
                alterados += int(aplicar_status(status))
    return JsonResponse({"atualizados": alterados})
