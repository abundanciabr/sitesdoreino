"""Retornos autenticados do WhatsApp: Evolution e WhatsApp Business Platform (Cloud API)."""
import hashlib
import hmac
import json
import logging
import secrets

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

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
    if evento not in ("MESSAGES_UPDATE", "MESSAGES_UPSERT"):
        return JsonResponse({"ignorado": True})
    instancia = payload.get("instance")
    config = ConfiguracaoWhatsApp.objects.filter(instancia=instancia).first()
    if config is None:
        return JsonResponse({"erro": "instancia desconhecida"}, status=404)
    dados = payload.get("data")
    itens = dados if isinstance(dados, list) else [dados]
    if evento == "MESSAGES_UPSERT":
        recebidas = _receber_evolution(config, itens)
        # Nota de voz do lead: depois da conversa, guarda o áudio para o admin
        # transcrever, ligado à mensagem da conversa.
        from apps.audio.webhook import receber_audios

        receber_audios(payload)
        return JsonResponse({"recebidas": recebidas})
    alteradas = 0
    for item in itens:
        if not isinstance(item, dict):
            continue
        chave = item.get("key") or {}
        identificador = chave.get("id") if isinstance(chave, dict) else None
        identificador = identificador or item.get("keyId") or item.get("id")
        atualizacao = item.get("update") or {}
        estado_cru = (atualizacao.get("status") if isinstance(atualizacao, dict) else None) or item.get("status")
        estado = ESTADOS.get(estado_cru) or ESTADOS.get(str(estado_cru).upper())
        if not isinstance(identificador, str) or not identificador or not estado:
            continue
        alteradas += aplicar_estado(config, identificador, estado)
    return JsonResponse({"atualizadas": alteradas})


def aplicar_estado(config: ConfiguracaoWhatsApp, identificador: str, estado: str) -> int:
    """Aplica um retorno de entrega sem regredir estado. Volta 1 se alterou."""
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
            # Resposta em voz (apps.audio) ou resposta HTTP ainda a caminho: o
            # retorno ficou persistido para quando o provider_id for gravado.
            from apps.audio.servico import atualizar_estado_de_voz

            return atualizar_estado_de_voz(config.instancia, identificador, estado)
        if estado == "falhou":
            if msg.status in ("entregue", "lido"):
                return 0
            msg.status = "falhou"
        elif ORDEM.get(estado, 0) > ORDEM.get(msg.status, 0):
            msg.status = estado
        else:
            return 0
        msg.erro = "provedor informou falha" if estado == "falhou" else ""
        msg.save(update_fields=["status", "erro", "atualizado_em"])
        if msg.origem == "transacional" and msg.referencia.isdigit():
            EnvioRegistrado.objects.filter(
                pk=int(msg.referencia), site_id=config.site_id, canal="whatsapp",
            ).update(status="falhou" if msg.status == "falhou" else "enviado",
                     resultado=f"gateway {msg.status}; provider_id={msg.provider_id}")
        if msg.origem == "conversa":
            from apps.conversas.models import MensagemDaConversa

            MensagemDaConversa.objects.filter(mensagem_whatsapp=msg).update(
                estado_envio=msg.status, id_externo=msg.provider_id, erro=msg.erro,
            )
        return 1
    return 0


logger = logging.getLogger(__name__)


def _receber_evolution(config: ConfiguracaoWhatsApp, itens: list) -> int:
    from apps.conversas.entrada import de_evolution, receber

    novas = 0
    for item in itens:
        if not isinstance(item, dict):
            continue
        recebida = de_evolution(site_id=config.site_id, instancia=config.instancia, item=item)
        if recebida is None:
            continue
        _, nova = receber(recebida)
        novas += int(nova)
    return novas


ESTADOS_CLOUD = {"sent": "enviado", "delivered": "entregue", "read": "lido", "failed": "falhou"}


def _assinatura_valida(request) -> bool:
    segredo = getattr(settings, "WHATSAPP_CLOUD_APP_SECRET", "")
    recebida = request.headers.get("X-Hub-Signature-256", "")
    if not segredo or not recebida.startswith("sha256="):
        return False
    esperada = hmac.new(segredo.encode("utf-8"), request.body, hashlib.sha256).hexdigest()
    return secrets.compare_digest(recebida[len("sha256="):].lower(), esperada)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook_whatsapp_cloud(request):
    """Formato oficial da Meta: verificação hub.challenge e X-Hub-Signature-256.

    O número do WhatsApp Business (phone_number_id) é a `instancia` configurada
    para o site; número sem configuração é ignorado sem erro, para a Meta não
    repetir a entrega indefinidamente.
    """
    if request.method == "GET":
        esperado = getattr(settings, "WHATSAPP_CLOUD_VERIFY_TOKEN", "")
        recebido = request.GET.get("hub.verify_token", "")
        if (request.GET.get("hub.mode") == "subscribe" and esperado
                and secrets.compare_digest(recebido, esperado)):
            return HttpResponse(request.GET.get("hub.challenge", ""), content_type="text/plain")
        return HttpResponse("nao autorizado", status=403, content_type="text/plain")
    if not _assinatura_valida(request):
        return JsonResponse({"erro": "assinatura invalida"}, status=403)
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"erro": "JSON invalido"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"erro": "objeto esperado"}, status=400)
    from apps.conversas.entrada import de_cloud, receber

    recebidas = atualizadas = ignoradas = 0
    for entrada in payload.get("entry") or []:
        for mudanca in (entrada.get("changes") or []) if isinstance(entrada, dict) else []:
            if not isinstance(mudanca, dict) or mudanca.get("field") != "messages":
                continue
            valor = mudanca.get("value") if isinstance(mudanca.get("value"), dict) else {}
            metadados = valor.get("metadata") if isinstance(valor.get("metadata"), dict) else {}
            numero_id = str(metadados.get("phone_number_id") or "")
            config = ConfiguracaoWhatsApp.objects.filter(instancia=numero_id).first() if numero_id else None
            if config is None:
                ignoradas += 1
                continue
            for item in valor.get("messages") or []:
                if not isinstance(item, dict):
                    continue
                recebida = de_cloud(site_id=config.site_id, numero_id=numero_id, item=item)
                if recebida is not None:
                    _, nova = receber(recebida)
                    recebidas += int(nova)
            for item in valor.get("statuses") or []:
                if not isinstance(item, dict):
                    continue
                estado = ESTADOS_CLOUD.get(str(item.get("status") or ""))
                identificador = item.get("id")
                if estado and isinstance(identificador, str) and identificador:
                    atualizadas += aplicar_estado(config, identificador, estado)
    return JsonResponse({"recebidas": recebidas, "atualizadas": atualizadas, "ignoradas": ignoradas})
