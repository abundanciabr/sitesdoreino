import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import respx
from django.db import connection, connections

from pagamentos.core import gateway
from pagamentos.core.models import OutboxEvent, PaymentAttempt
from pagamentos.core.tentativas import SegundaOpcaoIndisponivel
from pagamentos.methods.card.service import (
    DadosCartaoInvalidos, IntentNaoConfirmavel, criar_intent_card, confirmar_segunda_opcao_card,
)

pytestmark = pytest.mark.django_db(transaction=True)
SITE = "site-producao"
PRODUCT = "produto-producao"


@pytest.fixture
def production(settings, monkeypatch):
    settings.MP_ACCESS_TOKEN = "TEST-simulado"
    settings.MP_PRODUCTION_ACCESS_TOKEN = "APP_USR-producao-simulada"
    settings.MP_PRODUCTION_ENABLED_SITES = frozenset({SITE})
    settings.MP_PRODUCTION_PRODUCT_IDS = frozenset({PRODUCT})
    settings.MP_CARD_FALLBACK_SITES = frozenset()
    settings.APPMAX_CARD_ENABLED_SITES = frozenset()
    monkeypatch.setattr("pagamentos.core.models.relay_outbox", lambda: None)
    return settings


def create(**customer):
    return criar_intent_card(
        idempotency_key=str(uuid.uuid4()), site_id=SITE, order_id=str(uuid.uuid4()),
        amount_cents=990, currency="BRL",
        customer={"name": "Pessoa de Teste", "email": "pagador@example.com", "cpf": "52998224725", "phone": "11999999999", **customer},
        metadata={"product_id": PRODUCT, "items": [{"product_id": PRODUCT, "name": "Teste de compra", "price_cents": 990}]},
    )


def confirm(payment, **changes):
    return confirmar_segunda_opcao_card(payment, **{
        "mp_token": "token-simulado", "mp_payment_method_id": "visa",
        "mp_issuer_id": "123", "mp_device_id": "aparelho-simulado",
        "installments": 1, "holder_name": "Titular de Teste",
        "holder_document_number": "52998224725", **changes,
    })


def test_cartao_direto_sem_appmax_aprova_em_producao_e_devolve_na_mesma_conta(production):
    payment = create()
    assert payment.metadata["mp_ambiente"] == "producao"
    with respx.mock() as mp:
        def approve(request):
            body = json.loads(request.content)
            assert request.headers["Authorization"] == "Bearer APP_USR-producao-simulada"
            assert request.headers["X-meli-session-id"] == "aparelho-simulado"
            assert PaymentAttempt.objects.get(intent=payment).state == "sending"
            assert body["transaction_amount"] == 9.9 and body["installments"] == 1
            assert body["payer"]["first_name"] == "Pessoa"
            assert body["payer"]["last_name"] == "de Teste"
            assert body["payer"]["email"] == "pagador@example.com"
            assert body["payer"]["identification"]["type"] == "CPF"
            return __import__("httpx").Response(201, json={
                "id": 12345, "status": "approved", "external_reference": body["external_reference"],
                "transaction_amount": 9.9, "currency_id": "BRL", "installments": 1,
                "transaction_details": {"total_paid_amount": 9.9},
            })
        charge = mp.post("https://api.mercadopago.com/v1/payments").mock(side_effect=approve)
        confirm(payment)
        payment.refresh_from_db()
        assert payment.status == "approved"
        assert PaymentAttempt.objects.get(intent=payment).provider == "mercadopago"
        assert "ambiente" not in OutboxEvent.objects.get(event="pagamento.aprovado").payload
        with pytest.raises(IntentNaoConfirmavel):
            confirm(payment)
        assert charge.call_count == 1
        refund = mp.post("https://api.mercadopago.com/v1/payments/12345/refunds").respond(201, json={"id": 456, "status": "approved"})
        gateway.estornar_pagamento(payment_id="12345", idempotency_key=str(uuid.uuid4()))
        assert refund.calls.last.request.headers["Authorization"] == "Bearer APP_USR-producao-simulada"


@pytest.mark.parametrize("customer", [{"name": "Pessoa"}, {"cpf": ""}, {"email": ""}])
def test_identificacao_incompleta_nao_envia_cobranca(production, customer):
    payment = create(**customer)
    with respx.mock():
        with pytest.raises(DadosCartaoInvalidos):
            confirm(payment)
    assert not PaymentAttempt.objects.filter(intent=payment).exists()


def test_oferta_desativada_e_parcelamento_nao_enviam_cobranca(production):
    payment = create()
    with pytest.raises(DadosCartaoInvalidos):
        confirm(payment, installments=2)
    production.MP_PRODUCTION_ENABLED_SITES = frozenset()
    with pytest.raises(SegundaOpcaoIndisponivel):
        confirm(payment)
    assert not PaymentAttempt.objects.filter(intent=payment).exists()


def test_metadata_enviado_nao_habilita_producao_em_outros_produtos(production):
    production.MP_PRODUCTION_PRODUCT_IDS = frozenset({"outro-produto"})
    payment = create()
    assert "mp_ambiente" not in payment.metadata and "mp_card_provider" not in payment.metadata
    with pytest.raises(SegundaOpcaoIndisponivel):
        confirm(payment)


def test_duas_abas_do_cartao_direto_enviam_apenas_uma_cobranca(production):
    if connection.vendor != "postgresql":
        pytest.skip("concorrência exige o PostgreSQL usado no site")
    payment = create()
    start = threading.Barrier(2)

    def send():
        try:
            start.wait(timeout=5)
            try:
                confirm(payment)
            except IntentNaoConfirmavel:
                pass
        finally:
            connections.close_all()

    def pending(request):
        attempt = PaymentAttempt.objects.get(intent=payment)
        return __import__("httpx").Response(200, json={
            "id": 12345, "status": "in_process", "external_reference": str(attempt.operation_id),
            "transaction_amount": 9.9, "currency_id": "BRL", "installments": 1,
        })

    with respx.mock(assert_all_called=False) as mp:
        charge = mp.post("https://api.mercadopago.com/v1/payments").mock(side_effect=pending)
        mp.get("https://api.mercadopago.com/v1/payments/12345").mock(side_effect=pending)
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(lambda _: send(), range(2)))
        assert charge.call_count == 1
    assert PaymentAttempt.objects.filter(intent=payment).count() == 1
