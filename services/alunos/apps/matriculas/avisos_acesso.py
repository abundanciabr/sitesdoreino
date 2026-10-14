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
