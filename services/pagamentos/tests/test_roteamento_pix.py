"""Casos de roteamento Pix: uma cobrança por tentativa, troca e fatos únicos."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import RequestFactory
from django.utils import timezone
from ninja.errors import HttpError

from pagamentos.core import gateway
from pagamentos.core.models import Intent, OutboxEvent, PaymentAttempt
from pagamentos.methods.pix.service import (
    aplicar_status_mp,
    completar_intent_pix,
    criar_intent_pix,
    reconciliar_intent_pix,
)
from pagamentos.methods.pix.webhook import processar_webhook_pix

pytestmark = pytest.mark.django_db(transaction=True)
SITE = "site-pix-f7"
_NUMERO = 1000000


def _config(settings, *, lista=True, nome="Cliente Teste", email="cliente@exemplo.com"):
    settings.APPMAX_PIX_FALLBACK_SITES = frozenset({SITE}) if lista else frozenset()
    settings.APPMAX_API_URL = "https://api.sandboxappmax.com.br"
    settings.MP_ACCESS_TOKEN = "TEST-token"
    settings.PROVA_SEGUNDA_EMPRESA_EMAILS = frozenset()
    settings.PAGAMENTOS_PUBLIC_BASE_URL = "https://meshcraft.top"
    return {
        "name": nome,
        "email": email,
        "phone": "11999999999",
        "document_number": "40827365144",
        "ip": "127.0.0.1",
    }


def _metadata():
    return {
        "product_id": "produto",
        "pagina_url": "https://meshcraft.top/checkout/pedido/pix/pix/",
        "items": [{"product_id": "produto", "name": "Produto", "price_cents": 990}],
    }


def _novo(
    settings,
    *,
    lista=True,
    nome="Cliente Teste",
    email="cliente@exemplo.com",
    resposta=None,
):
    global _NUMERO
    _NUMERO += 1
    cliente = _config(settings, lista=lista, nome=nome, email=email)
    resultado = resposta or gateway.ResultadoPix(
        str(_NUMERO), "CODIGO-MP", "aW1hZ2Vt", timezone.now() + timedelta(minutes=30)
    )
    with patch(
        "pagamentos.core.gateway.criar_pagamento_pix", return_value=resultado
    ) as mp:
        intent = criar_intent_pix(
            idempotency_key=str(uuid.uuid4()),
            site_id=SITE,
            order_id=f"pedido-{_NUMERO}",
            amount_cents=990,
            currency="BRL",
            customer=cliente,
            metadata=_metadata(),
        )
    return intent, mp


def _tentativa(intent, provider="mercadopago"):
    return PaymentAttempt.objects.get(intent=intent, provider=provider)


def _eventos(nome):
    return list(OutboxEvent.objects.filter(event=nome))


def _aviso(payment_id, status, motivo=""):
    request = RequestFactory().post(f"/?data.id={payment_id}")
    tentativa = PaymentAttempt.objects.filter(
        provider="mercadopago", provider_reference_id=payment_id
    ).first()
    consulta = gateway.StatusDoPagamento(
        payment_id=payment_id,
        status=status,
        reason_code=motivo,
        external_reference=str(tentativa.operation_id) if tentativa else "",
        transaction_amount=Decimal("9.90"),
        currency_id="BRL",
    )
    with patch(
        "pagamentos.methods.pix.webhook.assinatura_valida", return_value=True
    ), patch(
        "pagamentos.methods.pix.webhook.consultar_status_do_pagamento",
        return_value=consulta,
    ):
        return processar_webhook_pix(request)


def test_01_mp_pendente_mostra_qr_sem_appmax(settings):
    intent, mp = _novo(settings)
    assert intent.pix_qr_code == "CODIGO-MP"
    assert _tentativa(intent).state == "pending"
    assert not PaymentAttempt.objects.filter(intent=intent, provider="appmax").exists()
    assert mp.call_count == 1
    assert mp.call_args.kwargs["order_id"] == str(_tentativa(intent).operation_id)


def test_02_risco_na_criacao_desvia_sem_evento_de_troca(settings):
    _config(settings)
    with patch(
        "pagamentos.core.gateway.criar_pagamento_pix",
        side_effect=gateway.RecusaAntifraude(
            payment_id="1002", status_detail="cc_rejected_high_risk"
        ),
    ):
        intent = criar_intent_pix(
            idempotency_key=str(uuid.uuid4()),
            site_id=SITE,
            order_id="pedido-risco",
            amount_cents=990,
            currency="BRL",
            customer=_config(settings),
            metadata=_metadata(),
        )
    assert intent.provider_payment_id.startswith("sim-")
    assert _tentativa(intent).state == "rejected"
    assert _tentativa(intent, "appmax").state == "pending"
    assert not _eventos("pagamento.recusado") and not _eventos("pix.codigo_trocado")


def test_03_recusa_comum_nao_desvia(settings):
    with patch("pagamentos.core.gateway.MercadoPagoClient") as mp:
        mp.return_value.criar_pagamento_pix.return_value = {
            "id": 1003,
            "status": "rejected",
            "status_detail": "other",
        }
        with pytest.raises(gateway.FalhaNoProvedor):
            criar_intent_pix(
                idempotency_key=str(uuid.uuid4()),
                site_id=SITE,
                order_id="pedido-comum",
                amount_cents=990,
                currency="BRL",
                customer=_config(settings),
                metadata=_metadata(),
            )
    assert not PaymentAttempt.objects.filter(provider="appmax").exists()


def test_04_timeout_replay_usa_mesma_chave_e_tentativa(settings):
    cliente = _config(settings)
    chave = str(uuid.uuid4())
    with patch(
        "pagamentos.core.gateway.criar_pagamento_pix",
        side_effect=gateway.FalhaNoProvedor("timeout", ambiguo=True),
    ) as mp:
        with pytest.raises(gateway.FalhaNoProvedor):
            criar_intent_pix(
                idempotency_key=chave,
                site_id=SITE,
                order_id="pedido-timeout",
                amount_cents=990,
                currency="BRL",
                customer=cliente,
                metadata=_metadata(),
            )
    intent = Intent.objects.get(idempotency_key=chave)
    tentativa = _tentativa(intent)
    assert tentativa.state == "reconciliation_required"
    with patch(
        "pagamentos.core.gateway.criar_pagamento_pix",
        return_value=gateway.ResultadoPix(
            "1004", "CODIGO-MP", "", timezone.now() + timedelta(minutes=30)
        ),
    ) as mp:
        completar_intent_pix(intent)
    assert mp.call_args.kwargs["idempotency_key"] == str(tentativa.operation_id)
    assert PaymentAttempt.objects.filter(intent=intent).count() == 1


def test_05_rejected_com_qr_nunca_e_exposto(settings):
    with patch("pagamentos.core.gateway.MercadoPagoClient") as mp:
        mp.return_value.criar_pagamento_pix.return_value = {
            "id": 1005,
            "status": "rejected",
            "status_detail": "other",
            "point_of_interaction": {"transaction_data": {"qr_code": "QR-ENGANOSO"}},
        }
        with pytest.raises(gateway.FalhaNoProvedor):
            criar_intent_pix(
                idempotency_key=str(uuid.uuid4()),
                site_id=SITE,
                order_id="pedido-qr-rec",
                amount_cents=990,
                currency="BRL",
                customer=_config(settings),
                metadata=_metadata(),
            )
    assert not Intent.objects.get(order_id="pedido-qr-rec").pix_qr_code


def test_06_repeticao_depois_do_desvio_nao_cobra_novamente(settings):
    intent, _ = _novo(settings, nome="RISCO SANDBOX")
    with patch(
        "pagamentos.core.gateway.criar_pagamento_pix",
        side_effect=AssertionError("MP repetido"),
    ), patch(
        "pagamentos.core.gateway.nova_sessao_appmax",
        side_effect=AssertionError("Appmax repetida"),
    ):
        completar_intent_pix(intent)
    assert PaymentAttempt.objects.filter(intent=intent).count() == 2


def test_07_fora_da_lista_nao_desvia_risco(settings):
    with patch(
        "pagamentos.core.gateway.criar_pagamento_pix",
        side_effect=gateway.RecusaAntifraude(
            payment_id="1007", status_detail="cc_rejected_high_risk"
        ),
    ):
        with pytest.raises(gateway.FalhaNoProvedor):
            criar_intent_pix(
                idempotency_key=str(uuid.uuid4()),
                site_id=SITE,
                order_id="pedido-fora",
                amount_cents=990,
                currency="BRL",
                customer=_config(settings, lista=False),
                metadata=_metadata(),
            )
    assert not PaymentAttempt.objects.filter(provider="appmax").exists()


@pytest.mark.parametrize(
    "status,motivo,via_aviso",
    [
        ("pending", "pending_waiting_transfer", False),
        ("pending", "pending_waiting_transfer", True),
        ("cancelled", "expired", False),
    ],
)
def test_08_mp_vencido_por_consulta_pending_emite_uma_vez(
    settings, status, motivo, via_aviso
):
    intent, _ = _novo(settings)
    Intent.objects.filter(pk=intent.pk).update(
        pix_expires_at=timezone.now() - timedelta(minutes=1)
    )
    intent.refresh_from_db()
    mp = _tentativa(intent)
    if via_aviso:
        _aviso(mp.provider_reference_id, status, motivo)
        _aviso(mp.provider_reference_id, status, motivo)
    else:
        aplicar_status_mp(mp, status, motivo)
        aplicar_status_mp(mp, status, motivo)
    intent.refresh_from_db()
    assert intent.status == "expired"
    assert len(_eventos("pix.expirado")) == 1


def test_09_id_mp_nao_casa_com_intent_appmax(settings):
    intent, _ = _novo(settings, nome="RISCO SANDBOX")
    # O número externo da Appmax pode coincidir com data.id do MP: o provedor
    # da tentativa é parte obrigatória da procura.
    Intent.objects.filter(pk=intent.pk).update(provider_payment_id="23258")
    PaymentAttempt.objects.filter(intent=intent, provider="appmax").update(
        provider_reference_id="23258"
    )
    assert _aviso("23258", "approved") == {"ignorado": True}
    assert intent.status == "pending"


def test_10_aviso_mp_antigo_depois_do_desvio_nao_recusa(settings):
    from django.core.management import call_command

    intent, _ = _novo(settings, nome="RISCO SANDBOX")
    mp = _tentativa(intent)
    _aviso(mp.provider_reference_id, "rejected", "cc_rejected_high_risk")
    intent.refresh_from_db()
    assert intent.status == "pending" and intent.provider_payment_id.startswith("sim-")
    assert not _eventos("pagamento.recusado")
    call_command("pagar_pix_simulado", pedido=intent.order_id)
    assert len(_eventos("pagamento.aprovado")) == 1


def test_11_mp_estornado_emite_reversao_v2(settings):
    intent, chamada_mp = _novo(settings)
    mp = _tentativa(intent)
    assert chamada_mp.call_args.kwargs["order_id"] == str(mp.operation_id)
    _aviso(mp.provider_reference_id, "approved", "accredited")
    _aviso(mp.provider_reference_id, "refunded", "")
    evento = _eventos("pagamento.reversao_confirmada")
    assert len(evento) == 1 and evento[0].payload["provider"] == "mercadopago"


def test_12_sem_ip_do_js_usa_ip_do_servidor(settings):
    intent, _ = _novo(settings, nome="RISCO SANDBOX")
    assert intent.customer["ip"] == "127.0.0.1"
    assert _tentativa(intent, "appmax").state == "pending"


def test_13_aprovacao_tardia_apos_expiracao(settings, caplog):
    intent, _ = _novo(settings)
    mp = _tentativa(intent)
    Intent.objects.filter(pk=intent.pk).update(
        pix_expires_at=timezone.now() - timedelta(minutes=1)
    )
    mp.intent.refresh_from_db()
    aplicar_status_mp(mp, "pending", "")
    aplicar_status_mp(mp, "approved", "accredited")
    intent.refresh_from_db()
    assert intent.status == "approved"
    assert "aprovacao_tardia" in caplog.text


def test_14_email_de_prova_vai_direto_appmax(settings):
    _config(settings)
    settings.PROVA_SEGUNDA_EMPRESA_EMAILS = frozenset({"prova@exemplo.com"})
    cliente = _config(settings, email="prova@exemplo.com")
    settings.PROVA_SEGUNDA_EMPRESA_EMAILS = frozenset({"prova@exemplo.com"})
    with patch(
        "pagamentos.core.gateway.criar_pagamento_pix",
        side_effect=AssertionError("MP indevido"),
    ):
        intent = criar_intent_pix(
            idempotency_key=str(uuid.uuid4()),
            site_id=SITE,
            order_id="pedido-prova",
            amount_cents=990,
            currency="BRL",
            customer=cliente,
            metadata=_metadata(),
        )
    assert intent.provider_payment_id.startswith("sim-")
    assert not PaymentAttempt.objects.filter(
        intent=intent, provider="mercadopago"
    ).exists()


def test_15_fora_da_lista_sem_vencimento_novo(settings):
    intent, mp = _novo(settings, lista=False)
    assert mp.call_args.kwargs["date_of_expiration"] is None


def test_16_webhook_risco_tardio_troca_uma_vez(settings):
    intent, _ = _novo(settings)
    mp = _tentativa(intent)
    _aviso(mp.provider_reference_id, "rejected", "cc_rejected_high_risk")
    intent.refresh_from_db()
    assert intent.provider_payment_id.startswith("sim-")
    assert (
        timedelta(minutes=29)
        < intent.pix_expires_at - timezone.now()
        <= timedelta(minutes=30)
    )
    assert len(_eventos("pix.codigo_trocado")) == 1
    assert not _eventos("pagamento.recusado")


def test_17_consulta_risco_tardio_sandbox_troca(settings):
    intent, _ = _novo(settings, nome="RISCO TARDIO SANDBOX")
    mp = _tentativa(intent)
    with patch(
        "pagamentos.core.gateway.consultar_status_do_pagamento",
        return_value=gateway.StatusDoPagamento(
            payment_id=mp.provider_reference_id,
            status="pending",
            reason_code="pending_waiting_transfer",
            external_reference=str(mp.operation_id),
            transaction_amount=Decimal("9.90"),
            currency_id="BRL",
        ),
    ):
        reconciliar_intent_pix(intent)
    intent.refresh_from_db()
    assert intent.provider_payment_id.startswith("sim-")
    assert len(_eventos("pix.codigo_trocado")) == 1


def test_18_aviso_repetido_gera_so_uma_appmax(settings):
    intent, _ = _novo(settings)
    mp = _tentativa(intent)
    _aviso(mp.provider_reference_id, "rejected", "cc_rejected_high_risk")
    _aviso(mp.provider_reference_id, "rejected", "cc_rejected_high_risk")
    assert PaymentAttempt.objects.filter(intent=intent, provider="appmax").count() == 1
    assert len(_eventos("pix.codigo_trocado")) == 1


def test_19_recusa_comum_depois_do_qr_e_final(settings):
    intent, _ = _novo(settings)
    aplicar_status_mp(_tentativa(intent), "rejected", "other")
    intent.refresh_from_db()
    assert intent.status == "rejected"
    assert len(_eventos("pagamento.recusado")) == 1
    assert not _eventos("pix.codigo_trocado")


def test_20_risco_fora_da_lista_e_recusa_final(settings):
    intent, _ = _novo(settings, lista=False)
    aplicar_status_mp(_tentativa(intent), "rejected", "cc_rejected_high_risk")
    intent.refresh_from_db()
    assert intent.status == "rejected"
    assert not PaymentAttempt.objects.filter(intent=intent, provider="appmax").exists()


def test_21_falha_appmax_na_troca_recusa_final(settings):
    intent, _ = _novo(settings)
    settings.APPMAX_API_URL = "https://api.appmax.com.br"
    with patch(
        "pagamentos.core.gateway.nova_sessao_appmax",
        side_effect=gateway.FalhaNoProvedor("fora"),
    ):
        with pytest.raises(gateway.FalhaNoProvedor):
            aplicar_status_mp(_tentativa(intent), "rejected", "cc_rejected_high_risk")
    intent.refresh_from_db()
    assert intent.status == "rejected"
    evento = _eventos("pagamento.recusado")
    assert len(evento) == 1 and evento[0].payload["provider"] == "appmax"
    assert not _eventos("pix.codigo_trocado")


def test_22_aprovacao_mp_depois_da_troca_e_duplicada(settings):
    intent, _ = _novo(settings)
    mp = _tentativa(intent)
    aplicar_status_mp(mp, "rejected", "cc_rejected_high_risk")
    aplicar_status_mp(mp, "approved", "accredited")
    intent.refresh_from_db()
    assert _tentativa(intent).state == "approved_duplicate"
    assert intent.provider_payment_id.startswith("sim-")
    assert not _eventos("pagamento.aprovado")
    _aviso(mp.provider_reference_id, "refunded", "")
    assert not _eventos("pagamento.reversao_confirmada")


def test_23_appmax_simulada_aprova_codigo_novo(settings):
    from django.core.management import call_command

    intent, _ = _novo(settings)
    aplicar_status_mp(_tentativa(intent), "rejected", "cc_rejected_high_risk")
    call_command("pagar_pix_simulado", pedido=intent.order_id)
    intent.refresh_from_db()
    assert intent.status == "approved"
    evento = _eventos("pagamento.aprovado")
    assert len(evento) == 1 and evento[0].payload["provider"] == "appmax"


def test_24_simulado_nunca_chama_api_pix_appmax(settings):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    with patch(
        "pagamentos.core.gateway.nova_sessao_appmax",
        side_effect=AssertionError("API Appmax sandbox"),
    ):
        intent, _ = _novo(settings, nome="RISCO SANDBOX")
    assert _tentativa(intent, "appmax").provider_reference_id.startswith("sim-")
    assert intent.pix_qr_code.startswith("PIX-SIMULADO-")
    settings.APPMAX_API_URL = "https://api.appmax.com.br"
    with pytest.raises(CommandError, match="sandbox"):
        call_command("pagar_pix_simulado", pedido=intent.order_id)
    intent.refresh_from_db()
    assert intent.status == "pending"


def test_25_evento_codigo_trocado_tem_dados_sem_cpf(settings):
    intent, _ = _novo(settings)
    aplicar_status_mp(_tentativa(intent), "rejected", "cc_rejected_high_risk")
    evento = _eventos("pix.codigo_trocado")[0]
    assert evento.version == 1
    assert evento.payload["pix"]["qr_code"].startswith("PIX-SIMULADO-")
    assert evento.payload["pagina_url"] == _metadata()["pagina_url"]
    assert evento.payload["customer"]["phone"] == "11999999999"
    assert "40827365144" not in str(evento.payload)


def test_26_pix_simulado_vence_sem_chamar_a_appmax(settings):
    from pagamentos.methods.pix.appmax import reconciliar as reconciliar_pix_appmax

    with patch(
        "pagamentos.core.gateway.nova_sessao_appmax",
        side_effect=AssertionError("API Appmax sandbox"),
    ):
        intent, _ = _novo(settings, nome="RISCO SANDBOX")
        assert _tentativa(intent, "appmax").provider_reference_id.startswith("sim-")
        reconciliar_pix_appmax(intent)
        intent.refresh_from_db()
        assert intent.status == "pending"
        depois = intent.pix_expires_at + timedelta(days=1, minutes=1)
        with patch("pagamentos.methods.pix.appmax.timezone.now", return_value=depois):
            reconciliar_pix_appmax(intent)
    intent.refresh_from_db()
    assert intent.status == "expired"
    assert _tentativa(intent, "appmax").state not in {"pending", "sending"}
    assert len(_eventos("pix.expirado")) == 1


@pytest.mark.parametrize("status", ["approved", "refunded"])
@pytest.mark.parametrize(
    "campo,valor",
    [
        ("external_reference", "operacao-alheia"),
        ("currency_id", "USD"),
        ("transaction_amount", None),
        ("transaction_amount", Decimal("9.89")),
    ],
)
def test_get_pix_divergente_nao_aplica_dinheiro_e_responde_502(
    settings, status, campo, valor
):
    intent, _ = _novo(settings)
    tentativa = _tentativa(intent)
    if status == "refunded":
        aplicar_status_mp(tentativa, "approved", "accredited")
        intent.refresh_from_db()
        assert intent.status == "approved"
    campos = {
        "payment_id": tentativa.provider_reference_id,
        "status": status,
        "reason_code": "accredited",
        "external_reference": str(tentativa.operation_id),
        "transaction_amount": Decimal("9.90"),
        "currency_id": "BRL",
    }
    campos[campo] = valor
    request = RequestFactory().post(f"/?data.id={tentativa.provider_reference_id}")
    with patch(
        "pagamentos.methods.pix.webhook.assinatura_valida", return_value=True
    ), patch(
        "pagamentos.methods.pix.webhook.consultar_status_do_pagamento",
        return_value=gateway.StatusDoPagamento(**campos),
    ) as consulta:
        with pytest.raises(HttpError) as erro:
            processar_webhook_pix(request)
    assert erro.value.status_code == 502
    consulta.assert_called_once_with(payment_id=tentativa.provider_reference_id)
    intent.refresh_from_db()
    assert intent.status == ("approved" if status == "refunded" else "pending")
    assert not _eventos("pagamento.reversao_confirmada")
    if status == "approved":
        assert not _eventos("pagamento.aprovado")


def test_consulta_pix_divergente_nao_aprova_pela_reconciliacao(settings):
    intent, _ = _novo(settings)
    tentativa = _tentativa(intent)
    with patch(
        "pagamentos.core.gateway.consultar_status_do_pagamento",
        return_value=gateway.StatusDoPagamento(
            payment_id=tentativa.provider_reference_id,
            status="approved",
            reason_code="accredited",
            external_reference="operacao-alheia",
            transaction_amount=Decimal("9.90"),
            currency_id="BRL",
        ),
    ):
        with pytest.raises(gateway.FalhaNoProvedor, match="não confirma"):
            reconciliar_intent_pix(intent)
    intent.refresh_from_db()
    assert intent.status == "pending"
    assert not _eventos("pagamento.aprovado")
