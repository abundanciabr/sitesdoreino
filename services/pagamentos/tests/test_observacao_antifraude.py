"""Observação das primeiras semanas: AC11 (MP Pix) e AC13 (Appmax risco).

Cada ponto do caminho guarda o que a empresa respondeu, sem mudar a rota.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from django.test import Client, RequestFactory
from django.utils import timezone

from pagamentos.api.intents import get_intent
from pagamentos.core import gateway
from pagamentos.core.models import (
    AppmaxWebhookInbox,
    InstalacaoAppmax,
    Intent,
    ObservacaoDoProvedor,
    OutboxEvent,
    PaymentAttempt,
)
from pagamentos.core.observacoes import observar_pedido_appmax
from pagamentos.methods.pix.service import criar_intent_pix
from pagamentos.supervisao import processar_rodada
from test_roteamento_pix import SITE, _aviso, _config, _metadata, _novo

pytestmark = pytest.mark.django_db(transaction=True)


def _observacoes(**filtro):
    return list(
        ObservacaoDoProvedor.objects.filter(**filtro).values_list(
            "origem", "status", "detalhe", "referencia"
        )
    )


def _consulta(tentativa, status, detalhe):
    return gateway.StatusDoPagamento(
        payment_id=tentativa.provider_reference_id,
        status=status,
        reason_code=detalhe,
        external_reference=str(tentativa.operation_id),
        transaction_amount=Decimal("9.90"),
        currency_id="BRL",
    )


# --- AC11: Mercado Pago Pix -------------------------------------------------


def test_recusa_antifraude_na_criacao_fica_observada(settings):
    _config(settings)
    with patch(
        "pagamentos.core.gateway.criar_pagamento_pix",
        side_effect=gateway.RecusaAntifraude(
            payment_id="77001", status_detail="cc_rejected_high_risk"
        ),
    ):
        intent = criar_intent_pix(
            idempotency_key=str(uuid.uuid4()), site_id=SITE, order_id="p-ac11-1",
            amount_cents=990, currency="BRL", customer=_config(settings),
            metadata=_metadata(),
        )
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="mercadopago")
    assert _observacoes(tentativa=tentativa) == [
        ("criacao", "rejected", "cc_rejected_high_risk", "77001")
    ]
    # A rota segue a mesma: a Appmax assumiu o Pix.
    assert PaymentAttempt.objects.filter(intent=intent, provider="appmax").exists()


def test_recusa_comum_na_criacao_guarda_id_e_status_detail(settings):
    with patch("pagamentos.core.gateway.MercadoPagoClient") as mp:
        mp.return_value.criar_pagamento_pix.return_value = {
            "id": 1353009999,
            "status": "rejected",
            "status_detail": "rejected_by_regulations",
        }
        with pytest.raises(gateway.FalhaNoProvedor):
            criar_intent_pix(
                idempotency_key=str(uuid.uuid4()), site_id=SITE,
                order_id="p-ac11-2", amount_cents=990, currency="BRL",
                customer=_config(settings), metadata=_metadata(),
            )
    tentativa = PaymentAttempt.objects.get(provider="mercadopago")
    assert _observacoes(tentativa=tentativa) == [
        ("criacao", "rejected", "rejected_by_regulations", "1353009999")
    ]
    # Sem mudança de rota: recusa que não é antifraude não chama a Appmax.
    assert not PaymentAttempt.objects.filter(provider="appmax").exists()
    assert tentativa.state == "reconciliation_required"


def test_aviso_guarda_uma_vez_e_pending_nao_conta(settings):
    intent, _ = _novo(settings, lista=False)
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="mercadopago")
    _aviso(tentativa.provider_reference_id, "pending", "pending_waiting_transfer")
    assert _observacoes(tentativa=tentativa) == []
    _aviso(tentativa.provider_reference_id, "rejected", "rejected_high_risk")
    _aviso(tentativa.provider_reference_id, "rejected", "rejected_high_risk")
    assert _observacoes(tentativa=tentativa) == [
        ("aviso", "rejected", "rejected_high_risk", tentativa.provider_reference_id)
    ]


def test_get_intent_marca_a_origem(settings):
    intent, _ = _novo(settings, lista=False)
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="mercadopago")
    with patch(
        "pagamentos.core.gateway.consultar_status_do_pagamento",
        return_value=_consulta(tentativa, "rejected", "cc_rejected_other_reason"),
    ):
        corpo = get_intent(RequestFactory().get("/"), str(intent.pk))
    assert corpo["status"] == "rejected"
    assert _observacoes(tentativa=tentativa) == [
        ("get_intent", "rejected", "cc_rejected_other_reason",
         tentativa.provider_reference_id)
    ]


def test_supervisao_marca_a_origem(settings):
    intent, _ = _novo(settings, lista=False)
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="mercadopago")
    with patch(
        "pagamentos.core.gateway.consultar_status_do_pagamento",
        return_value=_consulta(tentativa, "rejected", "rejected_insufficient_data"),
    ), patch("pagamentos.supervisao.relay_outbox", return_value=0):
        processar_rodada()
    assert _observacoes(tentativa=tentativa) == [
        ("supervisao", "rejected", "rejected_insufficient_data",
         tentativa.provider_reference_id)
    ]
    assert OutboxEvent.objects.filter(event="pagamento.recusado").count() == 1


def test_falha_ao_gravar_observacao_nao_derruba_o_aviso(settings):
    intent, _ = _novo(settings, lista=False)
    tentativa = PaymentAttempt.objects.get(intent=intent, provider="mercadopago")
    with patch(
        "pagamentos.core.observacoes.ObservacaoDoProvedor.objects.create",
        side_effect=RuntimeError("banco fora"),
    ):
        _aviso(tentativa.provider_reference_id, "approved", "accredited")
    intent.refresh_from_db()
    assert intent.status == "approved"
    assert _observacoes(tentativa=tentativa) == []


# --- AC13: Appmax, aviso order_refused_by_risk ------------------------------


def _instalacao():
    InstalacaoAppmax.objects.get_or_create(
        app_id="123",
        defaults={
            "appmax_site_id": "site-appmax",
            "alias": "Loja",
            "platform_site_ids": ["site-interno"],
        },
    )


def _tentativa_appmax(state: str, reason: str = "") -> PaymentAttempt:
    _instalacao()
    intent = Intent.objects.create(
        idempotency_key=str(uuid.uuid4()), site_id="site-interno",
        order_id="pedido-risco", method="card", amount_cents=1990,
        customer={"email": "cliente@exemplo.com"},
    )
    tentativa = PaymentAttempt.objects.create(
        intent=intent, platform_site_id=intent.site_id, provider="appmax",
        request_hash=uuid.uuid4().hex.ljust(64, "0"), external_order_id="3531",
        provider_reference_id="3531", customer_id="42", amount_cents=1990,
        effective_amount_cents=1990, state=state, reason=reason,
    )
    PaymentAttempt.objects.filter(pk=tentativa.pk).update(
        updated_at=timezone.now() - timedelta(minutes=10)
    )
    return tentativa


def _aviso_risco() -> AppmaxWebhookInbox:
    return AppmaxWebhookInbox.objects.create(
        app_id="123", appmax_site_id="site-appmax", platform_site_id="site-interno",
        event="order_refused_by_risk", event_type="order",
        external_order_id="3531", payload={"data": {"order_id": 3531}},
    )


def _cliente(status: str) -> Mock:
    cliente = Mock(spec_set=["preparar", "consultar_pedido"])
    cliente.consultar_pedido.return_value = {
        "id": 3531, "status": status, "customer": {"id": 42},
        "total_paid": 1990,
        "amounts": {"sub_total": 1990, "installment_fee": 0},
        "payment": {"installments": 1, "method": "creditcard"},
    }
    return cliente


def test_aviso_de_risco_depois_do_clique_guarda_o_status_do_get():
    tentativa = _tentativa_appmax("rejected", "cancelado")
    aviso = _aviso_risco()
    cliente = _cliente("cancelado")
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente), \
            patch("pagamentos.supervisao.relay_outbox", return_value=0):
        processar_rodada()
    assert _observacoes(tentativa=tentativa) == [
        ("aviso_order_refused_by_risk", "cancelado", "", "3531")
    ]
    cliente.consultar_pedido.assert_called_once_with(order_id=3531)
    # O resto do processamento continua igual ao de antes.
    aviso.refresh_from_db()
    tentativa.refresh_from_db()
    assert aviso.last_error == "tentativa_nao_ativa"
    assert tentativa.state == "rejected" and tentativa.reason == "cancelado"
    assert OutboxEvent.objects.count() == 0


def test_aviso_de_risco_com_tentativa_aberta_observa_e_reconcilia():
    tentativa = _tentativa_appmax("pending", "autorizado")
    aviso = _aviso_risco()
    cliente = _cliente("recusado_por_risco")
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente), \
            patch("pagamentos.supervisao.relay_outbox", return_value=0):
        processar_rodada()
    assert _observacoes(tentativa=tentativa) == [
        ("aviso_order_refused_by_risk", "recusado_por_risco", "", "3531")
    ]
    aviso.refresh_from_db()
    tentativa.refresh_from_db()
    assert aviso.processed_at is not None
    assert tentativa.state == "rejected"
    assert tentativa.reason == "recusado_por_risco"


def test_get_que_falha_fica_marcado_e_e_refeito_uma_vez():
    tentativa = _tentativa_appmax("rejected", "cancelado")
    fora = Mock(spec_set=["preparar", "consultar_pedido"])
    fora.consultar_pedido.side_effect = gateway.FalhaNoProvedor("timeout", ambiguo=True)
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=fora):
        observar_pedido_appmax(tentativa, order_id="3531")
    assert _observacoes(tentativa=tentativa) == [
        ("aviso_order_refused_by_risk", "", "consulta_indisponivel", "3531")
    ]
    cliente = _cliente("cancelado")
    with patch("pagamentos.core.gateway.nova_sessao_appmax", return_value=cliente):
        observar_pedido_appmax(tentativa, order_id="3531")
        observar_pedido_appmax(tentativa, order_id="3531")
    assert _observacoes(tentativa=tentativa) == [
        ("aviso_order_refused_by_risk", "cancelado", "", "3531")
    ]
    assert cliente.consultar_pedido.call_count == 1


# --- Painel: o resumo sai pela leitura do admin ------------------------------


def test_resumo_do_painel_conta_por_site(monkeypatch, settings):
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "token-admin")
    tentativa = _tentativa_appmax("rejected", "cancelado")
    with patch(
        "pagamentos.core.gateway.nova_sessao_appmax", return_value=_cliente("cancelado")
    ):
        observar_pedido_appmax(tentativa, order_id="3531")
    resposta = Client().get(
        "/api/pagamentos/interno/admin/compras/site-interno",
        HTTP_AUTHORIZATION="Bearer token-admin",
    )
    assert resposta.status_code == 200
    linhas = resposta.json()["observacao"]
    assert [
        (x["empresa"], x["origem"], x["status"], x["detalhe"], x["total"])
        for x in linhas
    ] == [("appmax", "aviso_order_refused_by_risk", "cancelado", "", 1)]
    outro = Client().get(
        "/api/pagamentos/interno/admin/compras/site-outro",
        HTTP_AUTHORIZATION="Bearer token-admin",
    )
    assert outro.json()["observacao"] == []


def test_resumo_que_falha_nao_derruba_a_lista_de_compras(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "token-admin")
    with patch(
        "pagamentos.core.observacoes.ObservacaoDoProvedor.objects.filter",
        side_effect=RuntimeError("tabela fora"),
    ):
        resposta = Client().get(
            "/api/pagamentos/interno/admin/compras/site-interno",
            HTTP_AUTHORIZATION="Bearer token-admin",
        )
    assert resposta.status_code == 200
    assert resposta.json()["observacao"] == []
