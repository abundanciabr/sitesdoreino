"""Retornos autenticados da instância Evolution."""
import json
import secrets

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.eventos.models import EnvioRegistrado

from .models import ConfiguracaoWhatsApp, EstadoDeProvedor, MensagemWhatsApp


ESTADOS = {
    "PENDING": "aceito", "SERVER_ACK": "enviado", "SENT": "enviado",
    "DELIVERY_ACK": "entregue", "DELIVERED": "entregue",
    "READ": "lido", "READ_ACK": "lido", "PLAYED": "lido",
    "ERROR": "falhou", "FAILED": "falhou",
    1: "aceito", 2: "enviado", 3: "entregue", 4: "lido",
}
ORDEM = {"desconhecido": 0, "aceito": 1, "enviado": 2, "falhou": 2, "entregue": 3, "lido": 4}


@csrf_exempt
@require_POST
def webhook_whatsapp(request):
    esperado = getattr(settings, "WHATSAPP_WEBHOOK_TOKEN", "")
    recebido = request.headers.get("X-Webhook-Token", "")
    if not esperado or not secrets.compare_digest(recebido, esperado):
        return JsonResponse({"erro": "nao autorizado"}, status=403)
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"erro": "JSON invalido"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"erro": "objeto esperado"}, status=400)
    evento = str(payload.get("event") or "").upper().replace(".", "_")
    if evento != "MESSAGES_UPDATE":
        return JsonResponse({"ignorado": True})
    instancia = payload.get("instance")
    config = ConfiguracaoWhatsApp.objects.filter(instancia=instancia).first()
    if config is None:
        return JsonResponse({"erro": "instancia desconhecida"}, status=404)
    dados = payload.get("data")
    itens = dados if isinstance(dados, list) else [dados]
    alteradas = 0
    for item in itens:
        if not isinstance(item, dict):
            continue
        chave = item.get("key") or {}
        identificador = chave.get("id") if isinstance(chave, dict) else None
        identificador = identificador or item.get("id")
        atualizacao = item.get("update") or {}
        estado_cru = (atualizacao.get("status") if isinstance(atualizacao, dict) else None) or item.get("status")
        estado = ESTADOS.get(estado_cru) or ESTADOS.get(str(estado_cru).upper())
        if not isinstance(identificador, str) or not identificador or not estado:
            continue
        with transaction.atomic():
            retorno, _ = EstadoDeProvedor.objects.select_for_update().get_or_create(
                instancia=config.instancia, provider_id=identificador, defaults={"status": estado},
            )
            if estado != "falhou" and ORDEM.get(estado, 0) > ORDEM.get(retorno.status, 0):
                retorno.status = estado
                retorno.save(update_fields=["status", "atualizado_em"])
            elif estado == "falhou" and retorno.status not in ("entregue", "lido"):
                retorno.status = estado
                retorno.save(update_fields=["status", "atualizado_em"])
            msg = MensagemWhatsApp.objects.select_for_update().filter(
                site_id=config.site_id, instancia=config.instancia, provider_id=identificador,
            ).first()
            if msg is None:
                # A resposta HTTP ainda pode estar a caminho. O retorno ficou
                # persistido para ser aplicado quando o provider_id for gravado.
                continue
            if estado == "falhou":
                if msg.status in ("entregue", "lido"):
                    continue
                msg.status = "falhou"
            elif ORDEM.get(estado, 0) > ORDEM.get(msg.status, 0):
                msg.status = estado
            else:
                continue
            msg.erro = "provedor informou falha" if estado == "falhou" else ""
            msg.save(update_fields=["status", "erro", "atualizado_em"])
            if msg.origem == "transacional" and msg.referencia.isdigit():
                EnvioRegistrado.objects.filter(
                    pk=int(msg.referencia), site_id=config.site_id, canal="whatsapp",
                ).update(status="falhou" if msg.status == "falhou" else "enviado",
                         resultado=f"gateway {msg.status}; provider_id={msg.provider_id}")
            alteradas += 1
    return JsonResponse({"atualizadas": alteradas})
