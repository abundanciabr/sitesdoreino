from __future__ import annotations

import uuid
import hashlib
from decimal import Decimal
from datetime import timedelta

import pytest

from pagamentos.core import gateway, models as core_models
from pagamentos.marketplace import service
from pagamentos.marketplace.models import Charge, Recebivel
from django.utils import timezone
from django.test import Client
import httpx


def test_paypal_so_aprova_captura_concluida_com_mesmo_valor():
    charge = Charge(id=uuid.uuid4(), provider_reference="ORDER-1", amount_cents=1250)
    order = {"id": "ORDER-1", "status": "COMPLETED", "purchase_units": [{
        "custom_id": str(charge.id),
        "amount": {"currency_code": "BRL", "value": "12.50"},
        "payments": {"captures": [{"id": "CAPTURE-1", "status": "COMPLETED",
                                    "amount": {"currency_code": "BRL", "value": "12.50"}}]},
    }]}
    assert service._paypal_capture(order, charge) == ("approved", "CAPTURE-1")
    order["purchase_units"][0]["payments"]["captures"][0]["amount"]["value"] = "12.49"
    with pytest.raises(service.ConflitoDeCobranca):
        service._paypal_capture(order, charge)


def test_paypal_reconhece_captura_devolvida_sem_tratar_como_pendente():
    charge = Charge(id=uuid.uuid4(), provider_reference="ORDER-REF", amount_cents=1250)
    order = {"id": "ORDER-REF", "status": "COMPLETED", "purchase_units": [{
        "custom_id": str(charge.id), "amount": {"currency_code": "BRL", "value": "12.50"},
        "payments": {"captures": [{"id": "CAPTURE-REF", "status": "REFUNDED",
                                   "amount": {"currency_code": "BRL", "value": "12.50"}}]},
    }]}
    assert service._paypal_capture(order, charge) == ("refunded", "CAPTURE-REF")
    order["purchase_units"][0]["payments"]["captures"][0]["status"] = "PARTIALLY_REFUNDED"
    assert service._paypal_capture(order, charge) == ("partially_refunded", "CAPTURE-REF")


@pytest.mark.django_db
def test_pix_aprovado_so_apos_consulta_validada_e_emite_um_evento(monkeypatch, settings):
    settings.MP_ACCESS_TOKEN = "TEST-local"
    monkeypatch.setattr(core_models, "relay_apos_commit", lambda: None)
    called = []

    def create_pix(**kwargs):
        called.append(kwargs)
        return gateway.ResultadoPix("MP-123", "qr-pagavel", "base64", None)

    monkeypatch.setattr(gateway, "criar_pagamento_pix", create_pix)
    key = uuid.uuid4()
    order_id = uuid.uuid4()
    kwargs = dict(idempotency_key=key, site_id="site-a", order_id=order_id,
                  order_version=2, amount_cents=1250, currency="BRL",
                  environment="sandbox", method="pix", customer_email="x@example.com",
                  customer_name="Cliente Exemplo", customer_cpf="52998224725")
    first = service.criar(**kwargs)
    assert first["status"] == "pending"
    assert service.criar(**kwargs)["id"] == first["id"]
    assert len(called) == 1
    charge = Charge.objects.get(pk=first["id"])
    assert not Recebivel.objects.filter(charge=charge).exists()
    monkeypatch.setattr(gateway, "consultar_status_do_pagamento", lambda **_: gateway.StatusDoPagamento(
        payment_id="MP-123", status="approved", reason_code="",
        external_reference=str(charge.id), transaction_amount=Decimal("12.50"), currency_id="BRL"))
    assert service.reconciliar(charge)["status"] == "approved"
    assert service.reconciliar(charge)["status"] == "approved"
    assert Recebivel.objects.filter(charge=charge, status="pendente_definicao").count() == 1
    assert core_models.OutboxEvent.objects.filter(event="marketplace.pagamento.aprovado",
                                               payload__charge_id=str(charge.id)).count() == 1
    vinculo = service.registrar_recebivel(charge_id=charge.id, site_id="site-a",
                                           order_id=order_id, order_version=2,
                                           aluno_id="perfil-1")
    assert vinculo["status"] == "pendente_definicao"
    assert vinculo["valor_liquido_cents"] is None
    assert service.registrar_recebivel(charge_id=charge.id, site_id="site-a",
                                       order_id=order_id, order_version=2,
                                       aluno_id="perfil-1") == vinculo
    with pytest.raises(service.ConflitoDeCobranca):
        service.registrar_recebivel(charge_id=charge.id, site_id="site-a",
                                    order_id=order_id, order_version=2,
                                    aluno_id="outro-perfil")


@pytest.mark.django_db
def test_pix_de_outro_valor_nao_confirma(monkeypatch, settings):
    settings.MP_ACCESS_TOKEN = "TEST-local"
    monkeypatch.setattr(core_models, "relay_apos_commit", lambda: None)
    monkeypatch.setattr(gateway, "criar_pagamento_pix", lambda **_: gateway.ResultadoPix("MP-124", "qr", "base64", None))
    info = service.criar(idempotency_key=uuid.uuid4(), site_id="site-a", order_id=uuid.uuid4(),
                         order_version=1, amount_cents=1250, currency="BRL", environment="sandbox",
                         method="pix", customer_email="x@example.com",
                         customer_name="Cliente Exemplo", customer_cpf="52998224725")
    charge = Charge.objects.get(pk=info["id"])
    monkeypatch.setattr(gateway, "consultar_status_do_pagamento", lambda **_: gateway.StatusDoPagamento(
        payment_id="MP-124", status="approved", reason_code="", external_reference=str(charge.id),
        transaction_amount=Decimal("12.49"), currency_id="BRL"))
    with pytest.raises(service.ConflitoDeCobranca):
        service.reconciliar(charge)
    charge.refresh_from_db()
    assert charge.status == "pending"
    assert not core_models.OutboxEvent.objects.filter(event="marketplace.pagamento.aprovado",
                                                   payload__charge_id=str(charge.id)).exists()


@pytest.mark.django_db
def test_pix_vencido_preserva_prazo_e_pagamento_tardio_confirmado(monkeypatch, settings):
    settings.MP_ACCESS_TOKEN = "TEST-local"
    monkeypatch.setattr(core_models, "relay_apos_commit", lambda: None)
    expires_at = timezone.now() + timedelta(minutes=15)
    monkeypatch.setattr(gateway, "criar_pagamento_pix", lambda **_: gateway.ResultadoPix(
        "MP-EXP", "qr-pagavel", "base64", expires_at))
    kwargs = dict(idempotency_key=uuid.uuid4(), site_id="site-a", order_id=uuid.uuid4(),
                  order_version=1, amount_cents=1250, currency="BRL", environment="sandbox",
                  method="pix", customer_email="x@example.com",
                  customer_name="Cliente Exemplo", customer_cpf="52998224725")
    first = service.criar(**kwargs)
    assert first["pix"]["expires_at"] == expires_at.isoformat()
    charge = Charge.objects.get(pk=first["id"])
    assert charge.pix_expires_at == expires_at

    provider_status = {"value": "expired"}
    monkeypatch.setattr(gateway, "consultar_status_do_pagamento", lambda **_: gateway.StatusDoPagamento(
        payment_id="MP-EXP", status=provider_status["value"], reason_code="",
        external_reference=str(charge.id), transaction_amount=Decimal("12.50"), currency_id="BRL"))
    assert service.reconciliar(charge)["status"] == "rejected"
    assert not Recebivel.objects.filter(charge=charge).exists()
    provider_status["value"] = "approved"
    assert service.reconciliar(charge)["status"] == "approved"
    assert service.reconciliar(charge)["status"] == "approved"
    assert Recebivel.objects.filter(charge=charge, status="pendente_definicao").count() == 1
    assert core_models.OutboxEvent.objects.filter(event="marketplace.pagamento.aprovado",
                                               payload__charge_id=str(charge.id)).count() == 1


@pytest.mark.django_db
def test_pix_devolvido_apos_aprovacao_avisa_uma_vez_e_reverte_recebivel(monkeypatch):
    monkeypatch.setattr(core_models, "relay_apos_commit", lambda: None)
    charge = Charge.objects.create(
        idempotency_key=uuid.uuid4(), site_id="site-a", order_id=uuid.uuid4(),
        order_version=1, amount_cents=1250, currency="BRL", environment="sandbox",
        method="pix", customer_email="x@example.test", status="approved",
        provider_reference="MP-REFUND", capture_reference="MP-REFUND",
    )
    Recebivel.objects.create(charge=charge, site_id=charge.site_id, order_id=charge.order_id)
    monkeypatch.setattr(gateway, "consultar_status_do_pagamento", lambda **_: gateway.StatusDoPagamento(
        payment_id="MP-REFUND", status="refunded", reason_code="",
        external_reference=str(charge.id), transaction_amount=Decimal("12.50"), currency_id="BRL"))
    assert service.reconciliar(charge)["status"] == "refunded"
    assert service.reconciliar(charge)["status"] == "refunded"
    assert Recebivel.objects.get(charge=charge).status == "revertido"
    aviso = core_models.OutboxEvent.objects.get(event="marketplace.pagamento.revertido")
    assert aviso.payload["status"] == "refunded"
    assert aviso.payload["order_id"] == str(charge.order_id)


@pytest.mark.django_db
def test_pix_aprovado_nao_regride_por_resposta_pendente_ou_recusada(monkeypatch):
    charge = Charge.objects.create(
        idempotency_key=uuid.uuid4(), site_id="site-a", order_id=uuid.uuid4(),
        order_version=1, amount_cents=1250, currency="BRL", environment="sandbox",
        method="pix", customer_email="x@example.test", status="approved",
        provider_reference="MP-LATE", capture_reference="MP-LATE",
    )
    provider_status = {"value": "pending"}
    monkeypatch.setattr(gateway, "consultar_status_do_pagamento", lambda **_: gateway.StatusDoPagamento(
        payment_id="MP-LATE", status=provider_status["value"], reason_code="",
        external_reference=str(charge.id), transaction_amount=Decimal("12.50"), currency_id="BRL"))
    assert service.reconciliar(charge)["status"] == "approved"
    provider_status["value"] = "rejected"
    assert service.reconciliar(charge)["status"] == "approved"
    assert not core_models.OutboxEvent.objects.filter(event="marketplace.pagamento.revertido").exists()


@pytest.mark.django_db
def test_paypal_recupera_criacao_ambigua_com_mesma_chave_e_corpo(monkeypatch, settings):
    settings.PAYPAL_CLIENT_ID = "sandbox-id"
    settings.PAYPAL_CLIENT_SECRET = "sandbox-secret"
    settings.MARKETPLACE_PAYPAL_RETURN_BASE_URL = "https://meshcraft.top/encomendas/cliente/pedidos"
    sent = []

    def paypal(method, path, *, request_id="", data=None):
        sent.append((method, path, request_id, data))
        if len(sent) == 1:
            raise service.CobrançaIndisponivel("timeout")
        return {"id": "ORDER-RECOVERED", "status": "PAYER_ACTION_REQUIRED", "links": [{
            "rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER-RECOVERED"}]}

    monkeypatch.setattr(service, "_paypal", paypal)
    kwargs = dict(idempotency_key=uuid.uuid4(), site_id="site-a", order_id=uuid.uuid4(),
                  order_version=1, amount_cents=1250, currency="BRL",
                  environment="sandbox", method="paypal", customer_email="x@example.test")
    with pytest.raises(service.CobrançaIndisponivel):
        service.criar(**kwargs)
    result = service.criar(**kwargs)
    assert result["status"] == "pending"
    assert result["reference"] == "ORDER-RECOVERED"
    assert result["paypal"]["approve_url"].startswith("https://www.sandbox.paypal.com/")
    assert sent[0][2:] == sent[1][2:]
    assert Charge.objects.filter(site_id="site-a", order_id=kwargs["order_id"]).count() == 1


@pytest.mark.django_db
def test_paypal_captura_ambigua_reconsulta_e_repete_mesma_chave(monkeypatch):
    monkeypatch.setattr(core_models, "relay_apos_commit", lambda: None)
    charge = Charge.objects.create(
        idempotency_key=uuid.uuid4(), site_id="site-a", order_id=uuid.uuid4(),
        order_version=1, amount_cents=1250, currency="BRL", environment="sandbox",
        method="paypal", customer_email="x@example.test", status="pending",
        provider_reference="ORDER-1", approval_url="https://www.sandbox.paypal.com/checkoutnow",
    )
    unit = {"custom_id": str(charge.id), "amount": {"currency_code": "BRL", "value": "12.50"}}
    attempts = []

    def paypal(method, path, *, request_id="", data=None):
        if method == "GET":
            return {"id": "ORDER-1", "status": "APPROVED", "purchase_units": [unit]}
        attempts.append(request_id)
        if len(attempts) == 1:
            raise service.CobrançaIndisponivel("timeout")
        return {"id": "ORDER-1", "status": "COMPLETED", "purchase_units": [{
            **unit, "payments": {"captures": [{"id": "CAPTURE-1", "status": "COMPLETED",
                "amount": {"currency_code": "BRL", "value": "12.50"}}]}}]}

    monkeypatch.setattr(service, "_paypal", paypal)
    with pytest.raises(service.CobrançaIndisponivel):
        service.capturar_paypal(charge)
    Charge.objects.filter(pk=charge.pk).update(updated_at=timezone.now() - timedelta(seconds=30))
    assert service.capturar_paypal(charge)["status"] == "approved"
    assert attempts[0] == attempts[1]
    assert core_models.OutboxEvent.objects.filter(event="marketplace.pagamento.aprovado",
                                               payload__charge_id=str(charge.id)).count() == 1


@pytest.mark.django_db
def test_api_cobranca_exige_token_e_site(settings, monkeypatch):
    settings.MARKETPLACE_API_TOKEN = "token-somente-teste"
    charge = Charge.objects.create(
        idempotency_key=uuid.uuid4(), site_id="site-a", order_id=uuid.uuid4(),
        order_version=1, amount_cents=1250, currency="BRL", environment="sandbox",
        method="pix", customer_email="x@example.test", status="approved",
        provider_reference="MP-1",
    )
    monkeypatch.setattr(gateway, "consultar_status_do_pagamento", lambda **_: gateway.StatusDoPagamento(
        payment_id="MP-1", status="approved", reason_code="", external_reference=str(charge.id),
        transaction_amount=Decimal("12.50"), currency_id="BRL"))
    client = Client()
    url = f"/api/pagamentos/marketplace/charges/{charge.id}"
    assert client.get(url).status_code == 401
    assert client.get(url, HTTP_AUTHORIZATION="Bearer token-somente-teste", HTTP_X_SITE_ID="site-b").status_code == 403
    ok = client.get(url, HTTP_AUTHORIZATION="Bearer token-somente-teste", HTTP_X_SITE_ID="site-a")
    assert ok.status_code == 200
    assert ok.json()["order_id"] == str(charge.order_id)


@pytest.mark.django_db
def test_pix_marketplace_recusa_conta_normal_mesmo_com_fingerprint(monkeypatch, settings):
    token = "APP_USR-conta-normal-de-teste-local"
    settings.MP_ACCESS_TOKEN = token
    settings.MP_TEST_ACCOUNT_TOKEN_SHA256 = hashlib.sha256(token.encode()).hexdigest()
    settings.MARKETPLACE_API_TOKEN = "token-interno-local"
    service._MP_TEST_ACCOUNT_CACHE.clear()
    calls = []
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: (
        calls.append(args[0]) or httpx.Response(200, json={"tags": ["business", "normal"]})
    ))
    monkeypatch.setattr(gateway, "criar_pagamento_pix", lambda **_: pytest.fail("Pix não pode ser criado"))
    client = Client()
    status = client.get("/api/pagamentos/marketplace/status", HTTP_AUTHORIZATION="Bearer token-interno-local")
    assert status.status_code == 200
    assert status.json()["pix_configured"] is False
    response = client.post("/api/pagamentos/marketplace/charges", data={
        "idempotency_key": str(uuid.uuid4()), "site_id": "site-a",
        "order_id": str(uuid.uuid4()), "order_version": 1,
        "amount_cents": 1250, "currency": "BRL", "environment": "sandbox",
        "method": "pix", "customer_email": "x@example.com",
        "customer_name": "Cliente Exemplo", "customer_cpf": "52998224725",
    }, content_type="application/json", HTTP_AUTHORIZATION="Bearer token-interno-local")
    assert response.status_code == 503
    assert Charge.objects.count() == 0
    assert calls == ["https://api.mercadopago.com/users/me"]


@pytest.mark.django_db
def test_pix_marketplace_aceita_app_usr_somente_com_tag_test_user(monkeypatch, settings):
    token = "APP_USR-conta-teste-local"
    settings.MP_ACCESS_TOKEN = token
    settings.MP_TEST_ACCOUNT_TOKEN_SHA256 = hashlib.sha256(token.encode()).hexdigest()
    service._MP_TEST_ACCOUNT_CACHE.clear()
    calls = []
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: (
        calls.append(args[0]) or httpx.Response(200, json={"tags": ["test_user"]})
    ))
    monkeypatch.setattr(gateway, "criar_pagamento_pix", lambda **_: gateway.ResultadoPix("MP-SANDBOX", "qr", "base64", None))
    kwargs = dict(idempotency_key=uuid.uuid4(), site_id="site-a", order_id=uuid.uuid4(),
                  order_version=1, amount_cents=1250, currency="BRL", environment="sandbox",
                  method="pix", customer_email="x@example.com",
                  customer_name="Cliente Exemplo", customer_cpf="52998224725")
    assert service.criar(**kwargs)["status"] == "pending"
    assert service.pix_marketplace_em_teste() is True
    assert calls == ["https://api.mercadopago.com/users/me"]
