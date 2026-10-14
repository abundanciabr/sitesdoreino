"""Confirmação de contato; não modifica a decisão nem dá acesso à escola."""
import secrets
from django.db import transaction
from .eventos import emitir
from .tasks import relay_apos_commit


def preparar_confirmacao(linha):
    linha.whatsapp_confirmado_em = None
    linha.whatsapp_pedido_id = None
    linha.whatsapp_confirmacao_codigo = ""
    if linha.whatsapp_avisos:
        evento = emitir("escola.whatsapp-solicitado", {
            "site_id": linha.site_id, "matricula_id": str(linha.pk)})
        linha.whatsapp_pedido_id = evento.event_id
        linha.whatsapp_confirmacao_codigo = secrets.token_hex(5).upper()
        transaction.on_commit(relay_apos_commit)
    linha.save(update_fields=["whatsapp_confirmado_em", "whatsapp_pedido_id", "whatsapp_confirmacao_codigo"])


def preparar_recibo(linha):
    evento = emitir("escola.pedido-recebido", {"site_id": linha.site_id, "matricula_id": str(linha.pk)})
    linha.recibo_event_id = evento.event_id
    linha.save(update_fields=["recibo_event_id"])
    transaction.on_commit(relay_apos_commit)


def token_de_acesso(linha):
    import hashlib, hmac
    from django.conf import settings
    if not linha.aviso_event_id or linha.status != "ativa":
        return ""
    chave = f"{linha.pk}.{linha.aviso_event_id.hex}"
    assinatura = hmac.new(settings.SECRET_KEY.encode(), ("escola-acesso-v1:"+chave+":"+linha.site_id+":"+linha.email+":"+linha.product_id).encode(), hashlib.sha256).hexdigest()
    return chave+"."+assinatura
