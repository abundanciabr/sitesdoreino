from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from apps.eventos.handlers import ao_pix_codigo_trocado
from apps.eventos.management.commands.consume_eventos import STREAMS, processar_envelope
from apps.eventos.models import EnvioRegistrado

pytestmark = pytest.mark.django_db(transaction=True)


def _dados(pagina_url: str = "https://meshcraft.top/checkout/pedido/123/pix/") -> dict:
    return {
        "site_id": "site-um", "payment_id": str(uuid.uuid4()), "order_id": "pedido-123",
        "amount_cents": 990,
        "customer": {"name": "Cliente Teste", "email": "cliente@exemplo.com", "phone": "11999999999"},
        "pix": {"qr_code": "CODIGO-PIX-NOVO", "qr_code_base64": "aW1hZ2Vt",
                "expires_at": "2026-10-03T19:30:00+00:00"},
        "pagina_url": pagina_url,
    }


def test_evento_envia_um_email_com_codigo_e_link_sem_nome_de_provedor() -> None:
    with patch("apps.eventos.handlers.enviar_notificacao") as enviar:
        ao_pix_codigo_trocado(_dados())
    envio = EnvioRegistrado.objects.get()
    assert (envio.canal, envio.tipo, envio.assunto) == ("email", "pix_codigo_novo", "Seu novo código Pix")
    assert "CODIGO-PIX-NOVO" in envio.corpo
    assert "https://meshcraft.top/checkout/pedido/123/pix/" in envio.corpo
    assert "16:30" in envio.corpo  # UTC -> America/Sao_Paulo
    assert "Appmax" not in envio.assunto + envio.corpo
    assert "Mercado Pago" not in envio.assunto + envio.corpo
    enviar.assert_called_once()


def test_reentrega_nao_manda_outro_email() -> None:
    data = _dados()
    envelope = {"event": "pix.codigo_trocado", "version": 1,
                "event_id": str(uuid.uuid4()), "data": data}
    with patch("apps.eventos.handlers.enviar_notificacao") as enviar:
        assert processar_envelope(envelope, ao_pix_codigo_trocado)
        assert not processar_envelope(envelope, ao_pix_codigo_trocado)
        assert processar_envelope({**envelope, "event_id": str(uuid.uuid4())}, ao_pix_codigo_trocado)
    assert EnvioRegistrado.objects.count() == 1
    enviar.assert_called_once()


def test_sem_pagina_url_omite_linha_do_qr() -> None:
    with patch("apps.eventos.handlers.enviar_notificacao"):
        ao_pix_codigo_trocado(_dados(""))
    assert "Para ver o QR Code" not in EnvioRegistrado.objects.get().corpo


def test_stream_esta_ligado_ao_handler() -> None:
    assert STREAMS["eventos.pix.codigo_trocado"] is ao_pix_codigo_trocado
