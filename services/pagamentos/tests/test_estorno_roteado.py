"""Estorno por tentativa: uma escrita, confirmação por leitura e sem reversão da duplicada."""

from __future__ import annotations

from decimal import Decimal
from io import StringIO
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.db import connection

from pagamentos.core import gateway
from pagamentos.core.estorno import estornar
from pagamentos.core.gateway import StatusDoPagamento
from pagamentos.core.ledger import registrar_fato, registrar_fato_da_tentativa
from pagamentos.core.models import Intent, OutboxEvent, PaymentAttempt, PaymentOperation
from pagamentos.core.tentativas import ResultadoDoProvedor, fechar_reconciliacao
from pagamentos.supervisao import processar_rodada

pytestmark = pytest.mark.django_db(transaction=True)


def _compra(
    provider: str = "appmax", *, referencia: str = "3531", legado: bool = False
) -> tuple[Intent, PaymentAttempt]:
    intent = Intent.objects.create(
        idempotency_key=str(uuid4()), site_id="site-interno", order_id="pedido-1",
        method="card", amount_cents=2000, customer={"email": "teste@exemplo.com"},
    )
    with patch("pagamentos.core.models.relay_apos_commit"):
        registrar_fato(
            intent, novo_status="approved", evento="pagamento.aprovado",
            dados=(
                {"payment_id": str(intent.pk), "mp_payment_id": referencia}
                if legado else {
                    "payment_id": str(intent.pk), "platform_site_id": intent.site_id,
                    "provider": provider, "provider_reference_id": referencia,
                }
            ),
            version=1 if legado else 2,
        )
    if legado:
        Intent.objects.filter(pk=intent.pk).update(provider_payment_id=referencia)
        intent.refresh_from_db()
    tentativa = PaymentAttempt.objects.create(
        intent=intent, platform_site_id=intent.site_id, provider=provider,
        request_hash="a" * 64, provider_reference_id=referencia,
        external_order_id=referencia if provider == "appmax" else "",
        customer_id="42" if provider == "appmax" else "",
        amount_cents=2000, effective_amount_cents=2000, state="approved",
    )
    if provider == "mercadopago" and not legado:
        PaymentOperation.objects.create(
            attempt=tentativa, platform_site_id=intent.site_id,
            operation_type="payment", request_hash="p" * 64, state="completed",
        )
    return intent, tentativa


def _pedido(status: str, referencia: int = 3531) -> dict:
    return {
        "id": referencia, "status": status, "customer": {"id": 42},
        "total_paid": 2000,
        "amounts": {"sub_total": 2000, "installment_fee": 0},
        "payment": {"installments": 1, "method": "creditcard"},
    }


def _rodada_appmax(pedido: dict) -> Mock:
    sessao = Mock()
    sessao.consultar_pedido.return_value = pedido
    with patch.object(gateway, "nova_sessao_appmax", return_value=sessao), patch(
        "pagamentos.supervisao.relay_outbox", return_value=0
    ):
        processar_rodada()
    return sessao


def test_registro_duravel_antes_do_post_e_comando_repetido_nao_reenvia() -> None:
    intent, tentativa = _compra()
    sessao = Mock()

    def conferir_antes_do_post(*, order_id: int, tipo: str) -> dict:
        assert not connection.in_atomic_block
        tentativa.refresh_from_db()
        operacao = PaymentOperation.objects.get(attempt=tentativa, operation_type="refund")
        assert tentativa.estorno_estado == "solicitado"
        assert tentativa.estorno_solicitado_em is not None
        assert operacao.state == "sending"
        assert operacao.platform_site_id == intent.site_id
        assert order_id == 3531 and tipo == "total"
        return {"id": 1}

    sessao.solicitar_estorno.side_effect = conferir_antes_do_post
    with patch.object(gateway, "nova_sessao_appmax", return_value=sessao):
        call_command("estornar_intent", str(intent.pk), stdout=StringIO())
        call_command("estornar_intent", str(intent.pk), stdout=StringIO())
    assert sessao.solicitar_estorno.call_count == 1
    assert PaymentOperation.objects.filter(attempt=tentativa, operation_type="refund").count() == 1
    assert not OutboxEvent.objects.filter(event="pagamento.reversao_confirmada").exists()

    consulta = _rodada_appmax(_pedido("estornado"))
    assert consulta.consultar_pedido.call_count == 1
    tentativa.refresh_from_db()
    intent.refresh_from_db()
    assert tentativa.estorno_estado == "confirmado"
    assert intent.status == "approved"
    assert OutboxEvent.objects.get(event="pagamento.reversao_confirmada").payload == {
        "platform_site_id": intent.site_id, "provider": "appmax",
        "provider_reference_id": "3531", "motivo": "estorno",
        "order_id": intent.order_id,
    }
    _rodada_appmax(_pedido("estornado"))
    assert OutboxEvent.objects.filter(event="pagamento.reversao_confirmada").count() == 1


def test_timeout_ambiguo_so_consulta_sem_repetir_post() -> None:
    _, tentativa = _compra()
    sessao = Mock()
    sessao.solicitar_estorno.side_effect = gateway.FalhaNoProvedor("timeout", ambiguo=True)
    with patch.object(gateway, "nova_sessao_appmax", return_value=sessao):
        assert estornar(tentativa, "teste").estorno_estado == "ambiguo"
        assert estornar(tentativa, "teste").estorno_estado == "ambiguo"
    assert sessao.solicitar_estorno.call_count == 1
    assert PaymentOperation.objects.get(attempt=tentativa, operation_type="refund").state == "reconciliation_required"
    _rodada_appmax(_pedido("aprovado"))
    tentativa.refresh_from_db()
    assert tentativa.estorno_estado == "ambiguo"
    assert not OutboxEvent.objects.filter(event="pagamento.reversao_confirmada").exists()
    _rodada_appmax(_pedido("estornado"))
    tentativa.refresh_from_db()
    assert tentativa.estorno_estado == "confirmado"


def test_mp_usa_chave_da_operacao_e_confirma_por_get_com_identidade() -> None:
    intent, tentativa = _compra("mercadopago", referencia="91234")
    tentativa.effective_amount_cents = 2300
    tentativa.installments = 3
    tentativa.save(update_fields=["effective_amount_cents", "installments"])
    def conferir_post(*, payment_id: str, idempotency_key: str) -> dict:
        assert not connection.in_atomic_block
        operacao = PaymentOperation.objects.get(attempt=tentativa, operation_type="refund")
        assert payment_id == "91234"
        assert operacao.operation_id != tentativa.operation_id
        assert idempotency_key == f"estorno:{tentativa.operation_id}"
        return {"id": 7}
    with patch.object(gateway, "estornar_pagamento", side_effect=conferir_post) as post:
        estornar(tentativa, "devolucao")
        estornar(tentativa, "devolucao")
    assert post.call_count == 1
    def consulta(*, payment_id: str) -> StatusDoPagamento:
        return StatusDoPagamento(
            payment_id=payment_id, status="refunded", reason_code="",
            external_reference=str(tentativa.operation_id),
            transaction_amount=Decimal("20.00"), installments=3,
            currency_id="BRL", total_paid_amount=Decimal("23.00"),
        )
    with patch.object(gateway, "consultar_status_do_pagamento", side_effect=consulta), patch(
        "pagamentos.supervisao.relay_outbox", return_value=0
    ):
        processar_rodada()
    tentativa.refresh_from_db()
    intent.refresh_from_db()
    assert tentativa.estorno_estado == "confirmado"
    assert intent.status == "approved"
    assert OutboxEvent.objects.get(event="pagamento.reversao_confirmada").payload["provider"] == "mercadopago"


@pytest.mark.parametrize("campo,valor", [
    ("external_reference", "pedido-1"),  # referência legada não vale para tentativa nova
    ("transaction_amount", Decimal("23.00")),
    ("total_paid_amount", Decimal("20.00")),
    ("installments", 1),
    ("currency_id", "USD"),
])
def test_mp_get_divergente_nao_confirma_estorno(campo: str, valor: object) -> None:
    _, tentativa = _compra("mercadopago", referencia="91234")
    tentativa.effective_amount_cents = 2300
    tentativa.installments = 3
    tentativa.save(update_fields=["effective_amount_cents", "installments"])
    with patch.object(gateway, "estornar_pagamento", return_value={"id": 1}):
        estornar(tentativa, "devolucao")
    dados = {
        "payment_id": "91234", "status": "refunded", "reason_code": "",
        "external_reference": str(tentativa.operation_id),
        "transaction_amount": Decimal("20.00"), "total_paid_amount": Decimal("23.00"),
        "installments": 3, "currency_id": "BRL",
    }
    dados[campo] = valor
    with patch.object(
        gateway, "consultar_status_do_pagamento",
        return_value=StatusDoPagamento(**dados),
    ), patch("pagamentos.supervisao.relay_outbox", return_value=0):
        processar_rodada()
    tentativa.refresh_from_db()
    assert tentativa.estorno_estado == "solicitado"
    assert not OutboxEvent.objects.filter(event="pagamento.reversao_confirmada").exists()


def test_mp_replica_confirma_com_referencia_da_principal_sem_reversao() -> None:
    intent, principal = _compra("mercadopago", referencia="91234")
    replica = PaymentAttempt.objects.create(
        intent=intent, platform_site_id=intent.site_id, provider="mercadopago",
        request_hash="d" * 64, provider_reference_id="91235",
        external_order_id=str(principal.operation_id),
        amount_cents=2000, effective_amount_cents=2000,
        state="approved_duplicate",
    )
    PaymentOperation.objects.create(
        attempt=replica, platform_site_id=intent.site_id,
        operation_type="payment", request_hash="d" * 64, state="completed",
    )
    with patch.object(gateway, "estornar_pagamento", return_value={"id": 1}) as post:
        estornar(replica, "cobranca_duplicada")
    post.assert_called_once()
    consulta = StatusDoPagamento(
        payment_id="91235", status="refunded", reason_code="",
        external_reference=str(principal.operation_id),
        transaction_amount=Decimal("20.00"), total_paid_amount=Decimal("20.00"),
        installments=1, currency_id="BRL",
    )
    with patch.object(
        gateway, "consultar_status_do_pagamento", return_value=consulta
    ), patch("pagamentos.supervisao.relay_outbox", return_value=0):
        processar_rodada()
    replica.refresh_from_db()
    principal.refresh_from_db()
    assert replica.estorno_estado == "confirmado"
    assert principal.estorno_estado is None
    assert not OutboxEvent.objects.filter(event="pagamento.reversao_confirmada").exists()


def test_mp_replica_com_referencia_sem_principal_nao_confirma() -> None:
    intent, _ = _compra("mercadopago", referencia="91234")
    referencia_alheia = str(uuid4())
    replica = PaymentAttempt.objects.create(
        intent=intent, platform_site_id=intent.site_id, provider="mercadopago",
        request_hash="e" * 64, provider_reference_id="91235",
        external_order_id=referencia_alheia,
        amount_cents=2000, effective_amount_cents=2000,
        state="approved_duplicate",
    )
    with patch.object(gateway, "estornar_pagamento", return_value={"id": 1}):
        estornar(replica, "cobranca_duplicada")
    consulta = StatusDoPagamento(
        payment_id="91235", status="refunded", reason_code="",
        external_reference=referencia_alheia,
        transaction_amount=Decimal("20.00"), total_paid_amount=Decimal("20.00"),
        installments=1, currency_id="BRL",
    )
    with patch.object(
        gateway, "consultar_status_do_pagamento", return_value=consulta
    ), patch("pagamentos.supervisao.relay_outbox", return_value=0):
        processar_rodada()
    replica.refresh_from_db()
    assert replica.estorno_estado == "solicitado"
    assert not OutboxEvent.objects.filter(event="pagamento.reversao_confirmada").exists()


def test_aprovacao_duplicada_estorna_so_a_tentativa_sem_reversao() -> None:
    intent, correta = _compra("mercadopago", referencia="91234")
    duplicada = PaymentAttempt.objects.create(
        intent=intent, platform_site_id=intent.site_id, provider="appmax",
        request_hash="b" * 64, provider_reference_id="3531", external_order_id="3531",
        customer_id="42", amount_cents=2000, effective_amount_cents=2000,
        state="rejected",
    )
    sessao = Mock()
    registrar_resultado = Mock()
    with patch.object(gateway, "nova_sessao_appmax", return_value=sessao):
        # A tentativa antiga já estava rejected; a outra, aprovada. A
        # reconciliação tardia atravessa _fechar sem violar o índice parcial.
        fechada = fechar_reconciliacao(
            duplicada,
            resultado=ResultadoDoProvedor(
                aprovada=True, provider_reference_id="3531",
                external_order_id="3531",
            ),
            registrar_resultado=registrar_resultado,
        )
        assert fechada.state == "approved_duplicate"
        assert registrar_fato_da_tentativa(
            "appmax", "3531", novo_status="approved", evento="pagamento.aprovado",
            dados={"platform_site_id": intent.site_id},
        ) == "approved_duplicate"
    duplicada.refresh_from_db()
    correta.refresh_from_db()
    assert duplicada.state == "approved_duplicate"
    assert duplicada.estorno_estado == "solicitado"
    assert correta.estorno_estado is None
    assert sessao.solicitar_estorno.call_count == 1
    registrar_resultado.assert_not_called()
    _rodada_appmax(_pedido("estornado"))
    duplicada.refresh_from_db()
    intent.refresh_from_db()
    assert duplicada.estorno_estado == "confirmado"
    assert intent.status == "approved"
    assert not OutboxEvent.objects.filter(event="pagamento.reversao_confirmada").exists()


@pytest.mark.parametrize("estado_intent,evento", [
    ("rejected", "pagamento.recusado"),
    ("expired", "pix.expirado"),
])
def test_ultima_rejeitada_aprova_tarde_e_emite_fato(
    estado_intent: str, evento: str
) -> None:
    intent = Intent.objects.create(
        idempotency_key=str(uuid4()), site_id="site-interno", order_id="pedido-1",
        method="pix", amount_cents=2000, customer={"email": "teste@exemplo.com"},
    )
    with patch("pagamentos.core.models.relay_apos_commit"):
        registrar_fato(intent, novo_status=estado_intent, evento=evento, dados={})
    tentativa = PaymentAttempt.objects.create(
        intent=intent, platform_site_id=intent.site_id, provider="mercadopago",
        request_hash="r" * 64, provider_reference_id="91234",
        amount_cents=2000, effective_amount_cents=2000, state="rejected",
    )
    chamadas = []
    def registrar(t: PaymentAttempt, resultado: ResultadoDoProvedor) -> None:
        chamadas.append(t.pk)
        registrar_fato(
            intent, novo_status="approved", evento="pagamento.aprovado",
            dados={
                "payment_id": str(intent.pk), "platform_site_id": intent.site_id,
                "provider": "mercadopago", "provider_reference_id": "91234",
            }, version=2,
        )
    with patch("pagamentos.core.models.relay_apos_commit"):
        fechada = fechar_reconciliacao(
            tentativa,
            resultado=ResultadoDoProvedor(aprovada=True, provider_reference_id="91234"),
            registrar_resultado=registrar,
        )
    intent.refresh_from_db()
    assert fechada.state == "approved"
    assert fechada.fechada_agora is True
    assert chamadas == [tentativa.pk]
    assert intent.status == "approved"
    assert not PaymentOperation.objects.filter(attempt=tentativa, operation_type="refund").exists()


def test_reentrega_da_aprovacao_principal_v1_nao_estorna_cobranca_correta() -> None:
    intent, tentativa = _compra("mercadopago", referencia="91234", legado=True)
    # Compras anteriores à outbox v2 têm aprovação válida sem provider na
    # outbox. A reentrega dessa mesma referência não é segunda cobrança.
    with patch.object(gateway, "estornar_pagamento") as post:
        assert registrar_fato_da_tentativa(
            "mercadopago", "91234", novo_status="approved",
            evento="pagamento.aprovado", dados={"platform_site_id": intent.site_id},
        ) == "ignorado"
    tentativa.refresh_from_db()
    assert tentativa.state == "approved"
    assert tentativa.estorno_estado is None
    assert not PaymentOperation.objects.filter(attempt=tentativa, operation_type="refund").exists()
    post.assert_not_called()


def test_fechada_approved_sem_fato_proprio_e_com_outro_vencedor_estorna() -> None:
    intent, tentativa = _compra("mercadopago", referencia="91234", legado=True)
    # O callback do fechamento encontra state=approved, mas a outbox v2 já
    # identifica outra referência como a vencedora da intent.
    OutboxEvent.objects.create(
        event="pagamento.aprovado", version=2,
        payload={
            "payment_id": str(intent.pk), "platform_site_id": intent.site_id,
            "provider": "appmax", "provider_reference_id": "3531",
        },
    )
    with patch.object(gateway, "estornar_pagamento", return_value={"id": 1}) as post:
        assert registrar_fato_da_tentativa(
            "mercadopago", "91234", novo_status="approved",
            evento="pagamento.aprovado", dados={"platform_site_id": intent.site_id},
        ) == "approved_duplicate"
    tentativa.refresh_from_db()
    intent.refresh_from_db()
    assert tentativa.state == "approved_duplicate"
    assert tentativa.estorno_estado == "solicitado"
    assert intent.status == "approved"
    assert post.call_count == 1
