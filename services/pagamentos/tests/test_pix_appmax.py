"""O Pix Appmax preserva o pedido e só aprova após consulta autenticada."""

from __future__ import annotations

import uuid
from contextlib import nullcontext
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from pagamentos.core.gateway import FalhaNoProvedor
from pagamentos.core.models import (
    ESTADOS_EM_ABERTO,
    AppmaxWebhookInbox,
    Intent,
    OutboxEvent,
    PaymentAttempt,
    PaymentOperation,
)
from pagamentos.methods.pix.appmax import completar as completar_pix_appmax, reconciliar
from pagamentos.methods.pix.service import completar_intent_pix
from pagamentos.supervisao import processar_rodada

pytestmark = pytest.mark.django_db(transaction=True)
SITE = "site-appmax"


def _cliente() -> Mock:
    cliente = Mock()
    cliente.registrar_resposta_pix.side_effect = lambda _id: nullcontext()
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
    # O Pix público sempre começa no MP. Estes testes exercitam diretamente a
    # segunda tentativa Appmax com o cliente de produção substituído por mock.
    settings.APPMAX_API_URL = "https://api.appmax.com.br"
    settings.APPMAX_PIX_FALLBACK_SITES = frozenset({SITE})
    with patch(
        "pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente
    ), patch(
        "pagamentos.core.gateway.criar_pagamento_pix",
        side_effect=AssertionError("Pix Appmax chamou Mercado Pago"),
    ):
        intent = Intent.objects.create(
            idempotency_key=str(uuid.uuid4()),
            site_id=SITE,
            order_id="pedido-interno",
            method="pix",
            status="pending",
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
                "recovery_url": "https://meshcraft.top/checkout/recuperar",
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
        return completar_pix_appmax(intent)


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


def test_pix_vincula_log_da_resposta_ao_operation_id_da_tentativa(
    settings: Any,
) -> None:
    cliente = _cliente()
    intent = _criar(settings, cliente)
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="appmax")
    cliente.registrar_resposta_pix.assert_called_once_with(str(tentativa.operation_id))


def test_pix_recusado_preserva_diagnostico_sanitizado_na_tentativa(
    settings: Any,
) -> None:
    cliente = _cliente()
    cliente.criar_pagamento_pix.side_effect = FalhaNoProvedor(
        "Appmax pagamento Pix: requisição recusada (HTTP 400); "
        "consulte o diagnóstico antes de qualquer novo envio; "
        "diagnostico=campo_expiration_date",
        diagnostico="campo_expiration_date",
    )
    with pytest.raises(FalhaNoProvedor, match="em confirmação"):
        _criar(settings, cliente)

    tentativa = PaymentAttempt.objects.get(provider="appmax")
    assert tentativa.state == "reconciliation_required"
    assert tentativa.reason == "appmax_pix_diagnostico_campo_expiration_date"
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


# guarda: services/pagamentos/pagamentos/methods/pix/appmax.py:323
def test_pix_pendente_integracao_aprova_uma_vez(settings: Any) -> None:
    """pendente_integracao é um dos 7 status do catálogo Appmax
    (ci/operacoes_vps.py:STATUS_APPMAX_PEDIDO) e nunca tinha teste próprio
    no Pix: hoje ele aprova, junto com aprovado/integrado."""
    cliente = _cliente()
    intent = _criar(settings, cliente)
    cliente.consultar_pedido.return_value["status"] = "pendente_integracao"
    cliente.consultar_pedido.return_value["total_paid"] = 1005
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        reconciliar(intent)
    intent.refresh_from_db()
    assert intent.status == "approved"
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 1


# guarda: services/pagamentos/pagamentos/methods/pix/appmax.py:325
def test_pix_recusado_por_risco_fecha_tentativa_uma_vez(settings: Any) -> None:
    """recusado_por_risco é um dos 7 status do catálogo Appmax e nunca
    tinha teste próprio no Pix: hoje ele recusa, junto com cancelado."""
    cliente = _cliente()
    intent = _criar(settings, cliente)
    cliente.consultar_pedido.return_value.pop("total_paid")
    cliente.consultar_pedido.return_value["status"] = "recusado_por_risco"
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        reconciliar(intent)
    intent.refresh_from_db()
    assert intent.status == "rejected"
    assert OutboxEvent.objects.filter(event="pagamento.recusado").count() == 1


def test_pix_status_desconhecido_levanta_falha_no_provedor(settings: Any) -> None:
    """Um status Pix fora dos 7 do catálogo (ci/operacoes_vps.py:
    STATUS_APPMAX_PEDIDO) não é terminal conhecido: reconciliar() levanta
    FalhaNoProvedor ambígua, a Intent fica pendente e nenhum evento de
    aprovação ou recusa é emitido."""
    cliente = _cliente()
    intent = _criar(settings, cliente)
    cliente.consultar_pedido.return_value["status"] = "em_analise_manual"
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        with pytest.raises(FalhaNoProvedor, match="desconhecido") as excinfo:
            reconciliar(intent)
    assert excinfo.value.ambiguo is True
    intent.refresh_from_db()
    assert intent.status == "pending"
    assert not OutboxEvent.objects.filter(
        event__in=["pagamento.aprovado", "pagamento.recusado"]
    ).exists()


def test_aviso_pix_forjado_nao_aprova_sem_consulta_autenticada(settings: Any) -> None:
    from pagamentos.core.models import InstalacaoAppmax

    cliente = _cliente()
    intent = _criar(settings, cliente)
    InstalacaoAppmax.objects.create(
        app_id="1888",
        appmax_site_id="loja-sandbox",
        alias="Teste",
        platform_site_ids=[SITE],
    )
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


def _criar_pix(settings: Any, cliente: Mock, *, com_qr: bool) -> Intent:
    if com_qr:
        return _criar(settings, cliente)
    cliente.criar_pagamento_pix.side_effect = FalhaNoProvedor(
        "Appmax pagamento Pix: requisição recusada (HTTP 400)",
        diagnostico="campo_expiration_date",
    )
    with pytest.raises(FalhaNoProvedor, match="em confirmação"):
        _criar(settings, cliente)
    return Intent.objects.get(site_id=SITE)


def _envelhecer(
    intent: Intent, *, criada_ha: timedelta, qr_venceu_ha: timedelta | None = None
) -> None:
    antes = timezone.now() - criada_ha
    PaymentAttempt.objects.filter(intent=intent).update(
        created_at=antes, updated_at=antes
    )
    if qr_venceu_ha is not None:
        Intent.objects.filter(pk=intent.pk).update(
            pix_expires_at=timezone.now() - qr_venceu_ha
        )


def _rodadas_so_de_consulta(cliente: Mock, quantas: int) -> list[dict[str, Any]]:
    """Roda a supervisão e reprova qualquer chamada à Appmax além da consulta."""
    cliente.reset_mock()
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        rodadas = [processar_rodada() for _ in range(quantas)]
    assert {nome for nome, _, _ in cliente.method_calls} <= {
        "preparar",
        "consultar_pedido",
    }
    return rodadas


@pytest.mark.parametrize(
    ("com_qr", "criada_ha", "qr_venceu_ha"),
    [
        pytest.param(False, timedelta(days=2), None, id="sem-qr-criado-ha-2-dias"),
        pytest.param(
            True, timedelta(days=2), timedelta(hours=25), id="qr-vencido-ha-25h"
        ),
    ],
)
def test_pix_vencido_ha_mais_de_um_dia_encerra_uma_vez_so_por_consulta(
    settings: Any,
    caplog: pytest.LogCaptureFixture,
    com_qr: bool,
    criada_ha: timedelta,
    qr_venceu_ha: timedelta | None,
) -> None:
    cliente = _cliente()
    intent = _criar_pix(settings, cliente, com_qr=com_qr)
    _envelhecer(intent, criada_ha=criada_ha, qr_venceu_ha=qr_venceu_ha)

    # guarda: services/pagamentos/pagamentos/methods/pix/appmax.py:328
    # guarda: services/pagamentos/pagamentos/methods/pix/appmax.py:379
    primeira, segunda = _rodadas_so_de_consulta(cliente, 2)

    tentativa = PaymentAttempt.objects.get(intent=intent)
    intent.refresh_from_db()
    assert (tentativa.state, tentativa.reason) == ("rejected", "pix_vencido")
    assert intent.status == "expired"
    assert (primeira["reconciliadas"], segunda["reconciliadas"]) == (1, 0)
    assert cliente.consultar_pedido.call_count == 1
    assert list(OutboxEvent.objects.values_list("event", "version")) == [
        ("pix.expirado", 1)
    ]
    assert "fato pagamento.recusado ignorado" not in caplog.text
    evento = OutboxEvent.objects.get()
    assert set(evento.payload) == {
        "site_id",
        "payment_id",
        "order_id",
        "amount_cents",
        "customer",
        "recovery_url",
    }
    assert evento.payload["site_id"] == SITE
    assert evento.payload["order_id"] == intent.order_id
    assert evento.payload["amount_cents"] == intent.amount_cents


@pytest.mark.parametrize(
    ("com_qr", "criada_ha", "qr_venceu_ha", "status"),
    [
        pytest.param(
            False,
            timedelta(days=1, minutes=29),
            None,
            "pendente",
            id="sem-qr-dentro-da-margem",
        ),
        pytest.param(
            True,
            timedelta(days=2),
            timedelta(hours=23),
            "pendente",
            id="qr-vencido-dentro-da-margem",
        ),
        pytest.param(
            False, timedelta(days=2), None, "autorizado", id="autorizado-fica-aberto"
        ),
    ],
)
def test_pix_dentro_da_margem_ou_autorizado_continua_aberto(
    settings: Any,
    com_qr: bool,
    criada_ha: timedelta,
    qr_venceu_ha: timedelta | None,
    status: str,
) -> None:
    cliente = _cliente()
    cliente.consultar_pedido.return_value["status"] = status
    intent = _criar_pix(settings, cliente, com_qr=com_qr)
    status_antes = intent.status
    _envelhecer(intent, criada_ha=criada_ha, qr_venceu_ha=qr_venceu_ha)

    # guarda: services/pagamentos/pagamentos/methods/pix/appmax.py:354
    _rodadas_so_de_consulta(cliente, 1)

    intent.refresh_from_db()
    assert cliente.consultar_pedido.call_count == 1
    assert PaymentAttempt.objects.get(intent=intent).state in ESTADOS_EM_ABERTO
    assert intent.status == status_antes
    assert not OutboxEvent.objects.exists()


def test_pix_expirado_nao_gera_cobranca_nova_no_replay(settings: Any) -> None:
    cliente = _cliente()
    intent = _criar_pix(settings, cliente, com_qr=False)
    _envelhecer(intent, criada_ha=timedelta(days=2))
    _rodadas_so_de_consulta(cliente, 1)
    intent.refresh_from_db()

    # guarda: services/pagamentos/pagamentos/methods/pix/appmax.py:144
    with patch(
        "pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente
    ), pytest.raises(FalhaNoProvedor, match="venceu"):
        completar_intent_pix(intent)

    intent.refresh_from_db()
    assert intent.status == "expired"
    assert PaymentAttempt.objects.filter(intent=intent).count() == 1
    assert {nome for nome, _, _ in cliente.method_calls} <= {
        "preparar",
        "consultar_pedido",
    }
