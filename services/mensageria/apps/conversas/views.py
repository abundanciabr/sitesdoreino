"""Respostas de e-mail recebidas (inbound do provedor)."""
from __future__ import annotations

import json
import secrets

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import enderecos, leads
from .entrada import Recebida, receber
from .models import MensagemDaConversa


def _token_valido(request) -> bool:
    esperado = getattr(settings, "EMAIL_ENTRADA_TOKEN", "") or getattr(settings, "EMAIL_WEBHOOK_TOKEN", "")
    recebido = request.headers.get("X-Webhook-Token", "")
    autorizacao = request.headers.get("Authorization", "")
    if not recebido and autorizacao.startswith("Bearer "):
        recebido = autorizacao[len("Bearer "):]
    return bool(esperado) and secrets.compare_digest(recebido, esperado)


def _texto(valor) -> str:
    return valor if isinstance(valor, str) else ""


def _endereco(valor) -> str:
    if isinstance(valor, list):
        valor = valor[0] if valor else ""
    if isinstance(valor, dict):
        valor = valor.get("Address") or valor.get("address") or valor.get("email") or ""
    return _texto(valor)


def _normalizar(item: dict) -> dict:
    """Aceita o formato simples e o inbound do Brevo (chaves com maiúscula)."""
    return {
        "from": _endereco(item.get("from") or item.get("From")),
        "to": _endereco(item.get("to") or item.get("To")),
        "subject": _texto(item.get("subject") or item.get("Subject")),
        "text": _texto(item.get("text") or item.get("RawTextBody") or item.get("ExtractedMarkdownMessage")),
        "message_id": _texto(item.get("message_id") or item.get("message-id") or item.get("MessageId")),
        "in_reply_to": _texto(item.get("in_reply_to") or item.get("in-reply-to") or item.get("InReplyTo")),
        "site_id": _texto(item.get("site_id")),
    }


def _site(dados: dict, site_url: str, remetente: str) -> str:
    """Site da URL, do corpo, da conversa respondida ou do único lead com o e-mail."""
    if site_url or dados["site_id"]:
        return (site_url or dados["site_id"])[:100]
    if dados["in_reply_to"]:
        anterior = MensagemDaConversa.objects.filter(
            direcao="saida", id_externo=dados["in_reply_to"].strip(), conversa__canal="email",
        ).select_related("conversa").first()
        if anterior is not None:
            return anterior.conversa.site_id
    ligacao = leads.procurar(site_id="", canal="email", endereco=remetente)
    return ligacao.site_id if ligacao.ligacao in ("ligada", "ambigua") else ""


@csrf_exempt
@require_POST
def email_recebido(request, site_id: str = ""):
    if not _token_valido(request):
        return JsonResponse({"erro": "nao autorizado"}, status=403)
    try:
        payload = json.loads(request.body or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"erro": "JSON invalido"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"erro": "objeto esperado"}, status=400)
    itens = payload.get("items") if isinstance(payload.get("items"), list) else [payload]
    recebidas = ignoradas = 0
    for item in itens:
        if not isinstance(item, dict):
            ignoradas += 1
            continue
        dados = _normalizar(item)
        remetente = enderecos.email(dados["from"])
        if not remetente or not (dados["text"].strip() or dados["subject"].strip()):
            ignoradas += 1
            continue
        site = _site(dados, site_id.strip(), remetente)
        _, nova = receber(Recebida(
            site_id=site, canal="email", endereco=remetente, texto=dados["text"],
            assunto=dados["subject"], id_externo=dados["message_id"].strip(),
            em_resposta_a=dados["in_reply_to"].strip(), caixa=enderecos.email(dados["to"]),
        ))
        recebidas += int(nova)
    if recebidas == 0 and ignoradas == len(itens):
        return JsonResponse({"erro": "sem remetente ou conteudo", "ignoradas": ignoradas}, status=400)
    return JsonResponse({"recebidas": recebidas, "ignoradas": ignoradas})
