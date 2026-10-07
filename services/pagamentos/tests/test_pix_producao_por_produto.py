import hashlib
import hmac
import time
import uuid

import httpx
import pytest
import respx
from django.test import RequestFactory

from pagamentos.core import gateway, ledger
from pagamentos.core.models import Intent, PaymentAttempt
from pagamentos.core.webhook_signature import assinatura_valida
from pagamentos.methods.pix.service import criar_intent_pix

pytestmark = pytest.mark.django_db
SITE = "site-prova"
PRODUCT = "produto-prova-producao"


@pytest.fixture
def production(settings):
    settings.MP_ACCESS_TOKEN = "TEST-credencial-simulada"
    settings.MP_PRODUCTION_ACCESS_TOKEN = "APP_USR-producao-simulada"
    settings.MP_PRODUCTION_ENABLED_SITES = frozenset({SITE})
    settings.MP_PRODUCTION_PRODUCT_IDS = frozenset({PRODUCT})
    settings.APPMAX_PIX_ENABLED_SITES = frozenset()
    settings.APPMAX_PIX_FALLBACK_SITES = frozenset()
    return settings


def intent(site=SITE, product=PRODUCT, **metadata):
    return criar_intent_pix(
        idempotency_key=str(uuid.uuid4()), site_id=site, order_id=str(uuid.uuid4()),
        amount_cents=990, currency="BRL",
        customer={"name": "Pessoa de Teste", "email": "pagador@example.com", "cpf": "52998224725", "phone": "11999999999"},
        metadata={"product_id": product, **metadata},
    )


@pytest.mark.parametrize("site,product,expected", [
    (SITE, PRODUCT, "APP_USR-producao-simulada"),
    ("outro-site", PRODUCT, "TEST-credencial-simulada"),
    (SITE, "outro-produto", "TEST-credencial-simulada"),
])
def test_criacao_consulta_e_estorno_usam_a_mesma_conta(production, site, product, expected):
    with respx.mock(assert_all_called=False) as mp:
        created = mp.post("https://api.mercadopago.com/v1/payments").respond(201, json={
            "id": 12345, "status": "pending", "point_of_interaction": {"transaction_data": {"qr_code": "pix-simulado", "qr_code_base64": "cGl4"}},
        })
        payment = intent(site, product, mp_ambiente="producao", ambiente="sandbox")
        attempt = PaymentAttempt.objects.get(intent=payment)
        assert created.calls.last.request.headers["Authorization"] == "Bearer " + expected
        body = __import__("json").loads(created.calls.last.request.content)
        assert body["payer"] == {"email": "pagador@example.com", "first_name": "Pessoa", "last_name": "de Teste", "identification": {"type": "CPF", "number": "52998224725"}}
        fetched = mp.get("https://api.mercadopago.com/v1/payments/12345").respond(200, json={"id": 12345, "status": "pending"})
        gateway.consultar_status_do_pagamento(payment_id="12345")
        refunded = mp.post("https://api.mercadopago.com/v1/payments/12345/refunds").respond(201, json={"id": 456, "status": "approved"})
        gateway.estornar_pagamento(payment_id="12345", idempotency_key="devolver-prova")
        assert fetched.calls.last.request.headers["Authorization"] == "Bearer " + expected
        assert refunded.calls.last.request.headers["Authorization"] == "Bearer " + expected
        production.MP_PRODUCTION_ENABLED_SITES = frozenset()
        assert gateway._cliente_mp(operation_id=str(attempt.operation_id))._token == expected
        data = ledger.com_referencias_do_pedido({"provider": "mercadopago"}, payment)
        assert (data.get("ambiente") == "sandbox") is (expected.startswith("TEST-"))


def test_assinatura_aceita_ambas_as_contas_sem_aceitar_uma_chave_desconhecida(settings):
    settings.MP_WEBHOOK_SECRET = "segredo-sandbox-simulado"
    settings.MP_PRODUCTION_WEBHOOK_SECRET = "segredo-producao-simulado"
    ts = str(int(time.time()))
    for secret, expected in ((settings.MP_WEBHOOK_SECRET, True), (settings.MP_PRODUCTION_WEBHOOK_SECRET, True), ("outra-chave", False)):
        signature = hmac.new(secret.encode(), f"id:123;request-id:prova;ts:{ts};".encode(), hashlib.sha256).hexdigest()
        request = RequestFactory().post("/?data.id=123", HTTP_X_REQUEST_ID="prova", HTTP_X_SIGNATURE=f"ts={ts},v1={signature}")
        assert assinatura_valida(request) is expected
