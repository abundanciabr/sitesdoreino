"""Estorno ou contestação feitos direto no painel do provedor, sem aviso."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from django.utils import timezone

from pagamentos.core import gateway
from pagamentos.core.models import Intent, OutboxEvent, PaymentAttempt, PaymentOperation
from pagamentos.supervisao import processar_rodada

pytestmark = pytest.mark.django_db(transaction=True)


def _aprovada(provider: str, *, horas: int = 7, dias: int = 1) -> PaymentAttempt:
    intent = Intent.objects.create(
        idempotency_key=str(uuid4()), site_id="site-interno", order_id=str(uuid4()),
        method="card", amount_cents=2000, customer={"email": "teste@exemplo.com"},
    )
    tentativa = PaymentAttempt.objects.create(
        intent=intent, platform_site_id=intent.site_id, provider=provider,
        request_hash=uuid4().hex.ljust(64, "0"),
        provider_reference_id="3531" if provider == "appmax" else "91234",
        external_order_id="3531" if provider == "appmax" else "",
        customer_id="42" if provider == "appmax" else "",
        amount_cents=2000, effective_amount_cents=2000, state="approved",
    )
    if provider == "mercadopago":
        PaymentOperation.objects.create(
            attempt=tentativa, platform_site_id=intent.site_id,
            operation_type="payment", request_hash="p" * 64, state="completed",
        )
    agora = timezone.now()
    PaymentAttempt.objects.filter(pk=tentativa.pk).update(
        created_at=agora - timedelta(days=dias), updated_at=agora - timedelta(hours=horas)
    )
    return PaymentAttempt.objects.get(pk=tentativa.pk)


def _pedido(status: str) -> dict:
    return {
        "id": 3531, "status": status, "customer": {"id": 42}, "total_paid": 2000,
        "amounts": {"sub_total": 2000, "installment_fee": 0},
        "payment": {"installments": 1, "method": "creditcard"},
    }


def _rodada(*, pedido: dict | None = None, mp: str | None = None,
            tentativa: PaymentAttempt | None = None) -> tuple[Mock, Mock]:
    sessao = Mock()
    sessao.consultar_pedido.return_value = pedido
    consulta_mp = Mock(return_value=gateway.StatusDoPagamento(
        payment_id="91234", status=mp or "approved", reason_code="",
        external_reference=str(tentativa.operation_id) if tentativa else "",
        transaction_amount=Decimal("20.00"), currency_id="BRL", installments=1,
    ))
    with patch.object(gateway, "nova_sessao_appmax", return_value=sessao), patch.object(
        gateway, "consultar_status_do_pagamento", consulta_mp
    ), patch("pagamentos.supervisao.relay_outbox", return_value=0):
        processar_rodada()
    return sessao, consulta_mp


def _reversoes() -> list[dict]:
    return list(
        OutboxEvent.objects.filter(event="pagamento.reversao_confirmada")
        .values_list("payload", flat=True)
    )


@pytest.mark.parametrize(
    ("status", "motivo"),
    [("estornado", "estorno"), ("chargeback_em_tratativa", "contestacao")],
)
def test_appmax_estorno_no_painel_sem_aviso_vira_reversao_uma_vez(status, motivo) -> None:
    tentativa = _aprovada("appmax")
    sessao, _ = _rodada(pedido=_pedido(status))
    assert sessao.consultar_pedido.call_count == 1
    assert _reversoes() == [{
        "platform_site_id": "site-interno", "provider": "appmax",
        "provider_reference_id": "3531", "motivo": motivo,
        "order_id": tentativa.intent.order_id,
    }]
    # Próxima consulta só em 6 h; e, mesmo forçada, não duplica o evento.
    sessao, _ = _rodada(pedido=_pedido(status))
    assert sessao.consultar_pedido.call_count == 0
    PaymentAttempt.objects.filter(pk=tentativa.pk).update(
        updated_at=timezone.now() - timedelta(hours=7)
    )
    _rodada(pedido=_pedido(status))
    assert len(_reversoes()) == 1


@pytest.mark.parametrize(("status", "motivo"), [("refunded", "estorno"), ("charged_back", "contestacao")])
def test_mp_estorno_ou_contestacao_no_painel_sem_aviso(status, motivo) -> None:
    tentativa = _aprovada("mercadopago")
    _, consulta = _rodada(mp=status, tentativa=tentativa)
    assert consulta.call_count == 1
    assert [p["motivo"] for p in _reversoes()] == [motivo]


def test_cobranca_ainda_aprovada_ou_identidade_divergente_nao_reverte() -> None:
    aprovada = _aprovada("appmax")
    sessao, _ = _rodada(pedido=_pedido("aprovado"))
    assert sessao.consultar_pedido.call_count == 1
    assert _reversoes() == []
    aprovada.refresh_from_db()
    assert aprovada.updated_at > timezone.now() - timedelta(minutes=1)

    PaymentAttempt.objects.filter(pk=aprovada.pk).update(
        updated_at=timezone.now() - timedelta(hours=7)
    )
    divergente = _pedido("estornado") | {"total_paid": 1}
    _rodada(pedido=divergente)
    assert _reversoes() == []


def test_recente_antiga_ou_em_estorno_pelo_botao_nao_e_consultada() -> None:
    _aprovada("appmax", horas=1)
    _aprovada("appmax", dias=181)
    em_estorno = _aprovada("appmax")
    PaymentAttempt.objects.filter(pk=em_estorno.pk).update(estorno_estado="confirmado")
    sessao, _ = _rodada(pedido=_pedido("estornado"))
    assert sessao.consultar_pedido.call_count == 0
    assert _reversoes() == []


def test_falha_na_consulta_nao_reverte_e_tenta_de_novo_depois() -> None:
    tentativa = _aprovada("appmax")
    sessao = Mock()
    sessao.consultar_pedido.side_effect = gateway.FalhaNoProvedor("fora do ar")
    with patch.object(gateway, "nova_sessao_appmax", return_value=sessao), patch(
        "pagamentos.supervisao.relay_outbox", return_value=0
    ):
        resultado = processar_rodada()
    assert resultado["reversoes_sem_aviso"] == 0
    assert _reversoes() == []
    tentativa.refresh_from_db()
    assert tentativa.state == "approved"
    assert tentativa.updated_at > timezone.now() - timedelta(minutes=1)
