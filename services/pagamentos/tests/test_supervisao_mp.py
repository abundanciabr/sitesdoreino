"""Recuperação periódica do MP e das trocas interrompidas."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import RequestFactory
from django.utils import timezone

from pagamentos.api.intents import get_intent
from pagamentos.core import gateway
from pagamentos.core.models import (
    AppmaxWebhookInbox, InstalacaoAppmax, Intent, OutboxEvent, PaymentAttempt,
)
from pagamentos.methods.pix.service import completar_intent_pix, criar_intent_pix
from pagamentos.supervisao import processar_rodada


pytestmark = pytest.mark.django_db(transaction=True)
SITE = "site-f9"


def _intent(method="pix", **campos):
    dados = dict(
        idempotency_key=str(uuid.uuid4()), site_id=SITE,
        order_id=str(uuid.uuid4()), method=method, status="pending",
        amount_cents=990, currency="BRL",
        customer={"email": "cliente@exemplo.com", "name": "Cliente Teste",
                  "phone": "11999999999", "document_number": "40827365144",
                  "ip": "127.0.0.1"},
        metadata={"items": [{"product_id": "produto", "name": "Produto",
                             "price_cents": 990}]},
    )
    dados.update(campos)
    return Intent.objects.create(**dados)


def _attempt(intent, provider="mercadopago", state="pending", **campos):
    dados = dict(
        intent=intent, platform_site_id=intent.site_id, provider=provider,
        state=state, request_hash=uuid.uuid4().hex.ljust(64, "0"),
        provider_reference_id=str(uuid.uuid4()),
        amount_cents=intent.amount_cents, effective_amount_cents=intent.amount_cents,
    )
    dados.update(campos)
    return PaymentAttempt.objects.create(**dados)


def _mp_status(tentativa, status="pending", reason=""):
    return gateway.StatusDoPagamento(
        payment_id=tentativa.provider_reference_id, status=status,
        reason_code=reason, external_reference=str(tentativa.operation_id),
        transaction_amount=Decimal("9.90"), currency_id="BRL",
    )


def test_get_intent_consulta_pix_mp_e_fecha_vencido():
    intent = _intent(pix_expires_at=timezone.now() - timedelta(minutes=1),
                     pix_qr_code="CODIGO-MP", provider_payment_id="mp-1")
    tentativa = _attempt(intent, provider_reference_id="mp-1")
    with patch("pagamentos.core.gateway.consultar_status_do_pagamento",
               return_value=_mp_status(tentativa)) as consulta:
        resposta = get_intent(RequestFactory().get("/"), str(intent.pk))
    intent.refresh_from_db()
    assert consulta.call_count == 1
    assert resposta["status"] == intent.status == "expired"
    assert PaymentAttempt.objects.get(pk=tentativa.pk).state == "rejected"
    assert OutboxEvent.objects.filter(event="pix.expirado").count() == 1


def test_duas_consultas_apos_timeout_nao_reenviam_pix_sem_referencia(settings):
    settings.APPMAX_PIX_FALLBACK_SITES = frozenset()
    chave = str(uuid.uuid4())
    with patch("pagamentos.core.gateway.criar_pagamento_pix",
               side_effect=gateway.FalhaNoProvedor("timeout", ambiguo=True)) as envio:
        with pytest.raises(gateway.FalhaNoProvedor):
            criar_intent_pix(
                idempotency_key=chave, site_id=SITE, order_id="pedido-timeout-f9",
                amount_cents=990, currency="BRL",
                customer={"name": "Cliente Teste", "email": "cliente@exemplo.com"},
                metadata={},
            )
    intent = Intent.objects.get(idempotency_key=chave)
    tentativa = PaymentAttempt.objects.get(intent=intent)
    primeira_chave = envio.call_args.kwargs["idempotency_key"]
    assert primeira_chave == str(tentativa.operation_id)
    with patch("pagamentos.core.gateway.criar_pagamento_pix") as novo_envio:
        for _ in range(2):
            resposta = get_intent(RequestFactory().get("/"), str(intent.pk))
            assert resposta["status"] == "pending"
            assert "pix" not in resposta
    novo_envio.assert_not_called()
    assert PaymentAttempt.objects.filter(intent=intent).count() == 1
    with patch("pagamentos.core.gateway.criar_pagamento_pix",
               return_value=gateway.ResultadoPix(
                   "mp-recuperado", "CODIGO-MP", "",
                   timezone.now() + timedelta(minutes=30),
               )) as replay:
        completar_intent_pix(intent)
    assert replay.call_args.kwargs["idempotency_key"] == primeira_chave
    assert replay.call_args.kwargs["order_id"] == primeira_chave
    assert replay.call_args.kwargs["amount_cents"] == envio.call_args.kwargs["amount_cents"]
    assert PaymentAttempt.objects.filter(intent=intent).count() == 1


def test_supervisao_consulta_pix_pendente_antes_do_vencimento_e_troca(settings):
    settings.APPMAX_PIX_FALLBACK_SITES = frozenset({SITE})
    settings.APPMAX_API_URL = "https://api.sandboxappmax.com.br"
    settings.MP_ACCESS_TOKEN = "TEST-token"
    intent = _intent(pix_expires_at=timezone.now() + timedelta(minutes=20),
                     pix_qr_code="CODIGO-MP", provider_payment_id="mp-2")
    tentativa = _attempt(intent, provider_reference_id="mp-2")
    with patch("pagamentos.core.gateway.consultar_status_do_pagamento",
               return_value=_mp_status(tentativa, "rejected", "cc_rejected_high_risk")) as consulta:
        processar_rodada()
        processar_rodada()
    intent.refresh_from_db()
    assert consulta.call_count == 1
    assert intent.status == "pending"
    assert intent.pix_qr_code.startswith("PIX-SIMULADO-")
    assert PaymentAttempt.objects.filter(intent=intent, provider="appmax").count() == 1
    assert not OutboxEvent.objects.filter(event="pagamento.recusado").exists()


def test_supervisao_consulta_cartao_mp_em_analise_sem_esperar_timeout():
    intent = _intent(method="card")
    tentativa = _attempt(intent, state="pending", reason="in_process",
                         provider_reference_id="mp-card")
    consulta = gateway.StatusDoPagamento(
        payment_id="mp-card", status="approved", reason_code="accredited",
        external_reference=str(tentativa.operation_id),
        transaction_amount=Decimal("9.90"), total_paid_amount=Decimal("9.90"),
        installments=1, currency_id="BRL",
    )
    with patch("pagamentos.core.gateway.consultar_status_do_pagamento",
               return_value=consulta) as mp:
        processar_rodada()
    intent.refresh_from_db()
    assert mp.call_count == 1
    assert intent.status == "approved"
    assert OutboxEvent.objects.filter(event="pagamento.aprovado", version=2).count() == 1


def test_lote_limitado_reveza_pix_pendentes_em_rodadas_seguidas():
    primeiro = _intent(pix_expires_at=timezone.now() + timedelta(minutes=20),
                       pix_qr_code="CODIGO-1", provider_payment_id="mp-1")
    segundo = _intent(pix_expires_at=timezone.now() + timedelta(minutes=20),
                      pix_qr_code="CODIGO-2", provider_payment_id="mp-2")
    um = _attempt(primeiro, provider_reference_id="mp-1")
    dois = _attempt(segundo, provider_reference_id="mp-2")
    por_id = {"mp-1": um, "mp-2": dois}
    with patch("pagamentos.core.gateway.consultar_status_do_pagamento",
               side_effect=lambda payment_id: _mp_status(por_id[payment_id])) as mp:
        processar_rodada(limite=1)
        processar_rodada(limite=1)
    assert [chamada.kwargs["payment_id"] for chamada in mp.call_args_list] == ["mp-1", "mp-2"]


def test_supervisao_resgata_pix_apos_queda_uma_vez(settings):
    settings.APPMAX_PIX_FALLBACK_SITES = frozenset({SITE})
    settings.APPMAX_API_URL = "https://api.sandboxappmax.com.br"
    settings.MP_ACCESS_TOKEN = "TEST-token"
    intent = _intent(pix_qr_code="CODIGO-MP", provider_payment_id="mp-3")
    _attempt(intent, state="rejected", provider_reference_id="mp-3",
             reason="cc_rejected_high_risk")
    with patch("pagamentos.core.gateway.consultar_status_do_pagamento") as consulta:
        processar_rodada()
        processar_rodada()
    assert consulta.call_count == 0
    assert PaymentAttempt.objects.filter(intent=intent, provider="appmax").count() == 1


def test_supervisao_fecha_risco_appmax_orfao_sem_chamar_mp():
    intent = _intent(method="card")
    tentativa = _attempt(intent, provider="appmax", state="rejected",
                         reason="recusado_por_risco", provider_reference_id="3531",
                         external_order_id="3531")
    PaymentAttempt.objects.filter(pk=tentativa.pk).update(
        updated_at=timezone.now() - timedelta(minutes=6)
    )
    with patch("pagamentos.core.gateway.consultar_status_do_pagamento") as mp:
        processar_rodada()
    intent.refresh_from_db()
    assert mp.call_count == 0
    assert intent.status == "rejected"
    assert OutboxEvent.objects.filter(event="pagamento.recusado", version=2).count() == 1


def test_risco_appmax_achado_pela_supervisao_e_recusa_final_uma_vez():
    intent = _intent(method="card")
    tentativa = _attempt(intent, provider="appmax", state="pending",
                         provider_reference_id="3531", external_order_id="3531",
                         customer_id="42")
    PaymentAttempt.objects.filter(pk=tentativa.pk).update(
        updated_at=timezone.now() - timedelta(minutes=6)
    )
    pedido = {
        "id": 3531, "status": "recusado_por_risco", "customer": {"id": 42},
        "amounts": {"sub_total": 990, "installment_fee": 0},
        "total_paid": 990,
    }
    with patch("pagamentos.core.gateway.nova_sessao_appmax") as sessao, patch(
        "pagamentos.core.gateway.consultar_status_do_pagamento"
    ) as mp:
        sessao.return_value.consultar_pedido.return_value = pedido
        processar_rodada()
        processar_rodada()
    intent.refresh_from_db()
    tentativa.refresh_from_db()
    assert mp.call_count == 0
    assert intent.status == "rejected" and tentativa.state == "rejected"
    assert not PaymentAttempt.objects.filter(intent=intent, provider="mercadopago").exists()
    assert OutboxEvent.objects.filter(event="pagamento.recusado", version=2).count() == 1


def test_supervisao_fecha_janela_vencida_sem_chamar_mp():
    intent = _intent(method="card", segunda_opcao_ate=timezone.now() - timedelta(seconds=1))
    _attempt(intent, provider="appmax", state="rejected", reason="recusado_por_risco")
    with patch("pagamentos.core.gateway.consultar_status_do_pagamento") as mp:
        processar_rodada()
    intent.refresh_from_db()
    assert mp.call_count == 0
    assert intent.status == "rejected"
    assert intent.segunda_opcao_ate is None
    assert OutboxEvent.objects.get(event="pagamento.recusado").payload["reason_code"] == "segunda_opcao_nao_enviada"


def test_aprovacao_tardia_appmax_rejeitada_passa_pelo_ledger_v2():
    intent = _intent(method="card")
    tentativa = _attempt(intent, provider="appmax", state="rejected",
                         reason="recusado_por_risco", provider_reference_id="3531",
                         external_order_id="3531", customer_id="42")
    InstalacaoAppmax.objects.create(app_id="123", appmax_site_id="site-appmax",
                                    alias="Loja", platform_site_ids=[SITE])
    aviso = AppmaxWebhookInbox.objects.create(
        app_id="123", appmax_site_id="site-appmax", platform_site_id=SITE,
        event="order_approved", event_type="order", external_order_id="3531",
        payload={"data": {"order_id": 3531}},
    )
    pedido = {
        "id": 3531, "status": "aprovado", "customer": {"id": 42},
        "amounts": {"sub_total": 990, "installment_fee": 0},
        "total_paid": 990, "payment": {"method": "creditcard", "installments": 1},
    }
    with patch("pagamentos.core.gateway.nova_sessao_appmax") as sessao:
        sessao.return_value.consultar_pedido.return_value = pedido
        processar_rodada()
    intent.refresh_from_db()
    aviso.refresh_from_db()
    assert intent.status == "approved"
    assert aviso.processed_at is not None and aviso.dead_lettered_at is None
    assert OutboxEvent.objects.filter(event="pagamento.aprovado", version=2).count() == 1


def test_aprovacao_tardia_appmax_com_mp_aprovado_estorna_so_duplicada():
    intent = _intent(method="card")
    appmax = _attempt(intent, provider="appmax", state="rejected",
                      reason="recusado_por_risco", provider_reference_id="3531",
                      external_order_id="3531", customer_id="42")
    mp = _attempt(intent, provider="mercadopago", state="approved",
                  provider_reference_id="mp-aprovado")
    Intent.objects.filter(pk=intent.pk).update(status="approved")
    InstalacaoAppmax.objects.create(app_id="123", appmax_site_id="site-appmax",
                                    alias="Loja", platform_site_ids=[SITE])
    aviso = AppmaxWebhookInbox.objects.create(
        app_id="123", appmax_site_id="site-appmax", platform_site_id=SITE,
        event="order_approved", event_type="order", external_order_id="3531",
        payload={"data": {"order_id": 3531}},
    )
    pedido = {
        "id": 3531, "status": "aprovado", "customer": {"id": 42},
        "amounts": {"sub_total": 990, "installment_fee": 0},
        "total_paid": 990, "payment": {"method": "creditcard", "installments": 1},
    }
    with patch("pagamentos.core.gateway.nova_sessao_appmax") as sessao, patch(
        "pagamentos.core.estorno.estornar"
    ) as estornar:
        sessao.return_value.consultar_pedido.return_value = pedido
        processar_rodada()
    appmax.refresh_from_db()
    mp.refresh_from_db()
    intent.refresh_from_db()
    aviso.refresh_from_db()
    assert appmax.state == "approved_duplicate"
    assert mp.state == "approved" and intent.status == "approved"
    assert aviso.processed_at is not None and aviso.dead_lettered_at is None
    assert estornar.call_count == 1
    assert estornar.call_args.args[0].pk == appmax.pk
    assert not OutboxEvent.objects.filter(event="pagamento.reversao_confirmada").exists()
