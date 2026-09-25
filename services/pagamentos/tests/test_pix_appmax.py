"""O Pix Appmax preserva o pedido e só aprova após consulta autenticada."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest

from pagamentos.core.gateway import FalhaNoProvedor
from pagamentos.core.models import (
    AppmaxWebhookInbox,
    Intent,
    OutboxEvent,
    PaymentAttempt,
    PaymentOperation,
)
from pagamentos.methods.pix.appmax import reconciliar
from pagamentos.methods.pix.service import completar_intent_pix, criar_intent_pix
from pagamentos.supervisao import processar_rodada

pytestmark = pytest.mark.django_db(transaction=True)
SITE = "site-appmax"


def _cliente() -> Mock:
    cliente = Mock()
    cliente.criar_cliente.return_value = {"id": "42"}
    cliente.criar_pedido.return_value = {"id": "3531", "status": "pendente"}
    cliente.criar_pagamento_pix.return_value = {
        "qr_code_base64": "aW1hZ2Vt",
        "qr_code": "00020126-copia-e-cola",
        "expires_at": "2099-09-25 15:30:00",
    }
    cliente.consultar_pedido.return_value = {
        "id": 3531,
        "status": "pendente",
        "customer": {"id": 42},
        "total_paid": 0,
        "amounts": {"sub_total": 1005},
        "payment": {"method": "pix"},
    }
    return cliente


def _criar(settings: Any, cliente: Mock) -> Intent:
    settings.APPMAX_PIX_ENABLED_SITES = frozenset({SITE})
    with patch(
        "pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente
    ), patch(
        "pagamentos.core.gateway.criar_pagamento_pix",
        side_effect=AssertionError("Pix Appmax chamou Mercado Pago"),
    ):
        return criar_intent_pix(
            idempotency_key=str(uuid.uuid4()),
            site_id=SITE,
            order_id="pedido-interno",
            amount_cents=1005,
            currency="BRL",
            customer={
                "name": "Cliente Teste",
                "email": "cliente@exemplo.com",
                "phone": "11999999999",
                "document_number": "12345678909",
                "ip": "127.0.0.1",
            },
            metadata={
                "product_id": "produto-1",
                "items": [
                    {
                        "product_id": "produto-1",
                        "name": "Produto Teste",
                        "price_cents": 1005,
                        "kind": "principal",
                    }
                ],
            },
        )


def test_pix_gera_qr_uma_vez_com_cliente_pedido_e_tentativa_persistida(
    settings: Any,
) -> None:
    cliente = _cliente()
    intent = _criar(settings, cliente)
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="appmax")
    assert tentativa.state == "pending"
    assert tentativa.external_order_id == "3531"
    assert PaymentOperation.objects.filter(attempt=tentativa).count() == 3
    assert intent.provider_payment_id == "3531"
    assert intent.pix_qr_code == "00020126-copia-e-cola"
    assert intent.pix_qr_code_base64 == "aW1hZ2Vt"
    assert intent.pix_expires_at is not None
    assert (
        cliente.criar_pedido.call_args.kwargs["body"]["products"][0]["unit_value"]
        == 1005
    )
    pagamento_enviado = cliente.criar_pagamento_pix.call_args.kwargs["body"]
    assert pagamento_enviado["order_id"] == 3531
    pix_enviado = pagamento_enviado["payment_data"]["pix"]
    assert pix_enviado["document_number"] == "12345678909"
    vencimento = datetime.fromisoformat(pix_enviado["expiration_date"]).replace(
        tzinfo=ZoneInfo("America/Sao_Paulo")
    )
    assert timedelta(minutes=29) < vencimento - datetime.now(
        ZoneInfo("America/Sao_Paulo")
    )
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        assert completar_intent_pix(intent).pk == intent.pk
    assert cliente.criar_pagamento_pix.call_count == 1


def test_pix_recusado_preserva_diagnostico_sanitizado_na_tentativa(
    settings: Any,
) -> None:
    cliente = _cliente()
    cliente.criar_pagamento_pix.side_effect = FalhaNoProvedor(
        "Appmax pagamento Pix: requisição recusada (HTTP 400); "
        "diagnostico=campo_expiration_date"
    )
    with pytest.raises(FalhaNoProvedor, match="em confirmação"):
        _criar(settings, cliente)

    tentativa = PaymentAttempt.objects.get(provider="appmax")
    assert tentativa.state == "reconciliation_required"
    assert tentativa.reason.endswith("diagnostico_campo_expiration_date")
    assert cliente.criar_pagamento_pix.call_count == 1


def test_consulta_aprova_uma_vez_sem_confiar_no_aviso(settings: Any) -> None:
    cliente = _cliente()
    intent = _criar(settings, cliente)
    cliente.consultar_pedido.return_value["status"] = "aprovado"
    cliente.consultar_pedido.return_value["total_paid"] = 1005
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        reconciliar(intent)
        reconciliar(intent)
    intent.refresh_from_db()
    assert intent.status == "approved"
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 1


def test_valor_pago_divergente_nao_aprova(settings: Any) -> None:
    cliente = _cliente()
    intent = _criar(settings, cliente)
    cliente.consultar_pedido.return_value["status"] = "aprovado"
    cliente.consultar_pedido.return_value["total_paid"] = 1004
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        with pytest.raises(FalhaNoProvedor, match="Valor pago"):
            reconciliar(intent)
    intent.refresh_from_db()
    assert intent.status == "pending"
    assert not OutboxEvent.objects.filter(event="pagamento.aprovado").exists()


def test_pix_cancelado_sem_total_pago_fecha_tentativa_uma_vez(settings: Any) -> None:
    cliente = _cliente()
    intent = _criar(settings, cliente)
    cliente.consultar_pedido.return_value.pop("total_paid")
    cliente.consultar_pedido.return_value["status"] = "cancelado"
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        reconciliar(intent)
    intent.refresh_from_db()
    assert intent.status == "rejected"
    assert OutboxEvent.objects.filter(event="pagamento.recusado").count() == 1


def test_pix_pendente_sem_total_pago_nao_emite_aprovacao(settings: Any) -> None:
    cliente = _cliente()
    intent = _criar(settings, cliente)
    cliente.consultar_pedido.return_value.pop("total_paid")
    cliente.consultar_pedido.return_value.pop("payment")
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        reconciliar(intent)
    intent.refresh_from_db()
    assert intent.status == "pending"
    assert not OutboxEvent.objects.exists()


def test_aviso_pix_forjado_nao_aprova_sem_consulta_autenticada(settings: Any) -> None:
    cliente = _cliente()
    intent = _criar(settings, cliente)
    AppmaxWebhookInbox.objects.create(
        app_id="1888",
        appmax_site_id="loja-sandbox",
        platform_site_id=SITE,
        event="order_approved",
        event_type="order",
        external_order_id="3531",
        payload={"data": {"order_id": 3531, "status": "aprovado"}},
    )
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        processar_rodada()
    intent.refresh_from_db()
    assert intent.status == "pending"
    assert cliente.consultar_pedido.call_count == 1
    assert not OutboxEvent.objects.filter(event="pagamento.aprovado").exists()
