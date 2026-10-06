from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from django.test import Client

from pagamentos.core import gateway, models as core_models
from pagamentos.marketplace.models import Charge, Recebivel, WalletEntry, WithdrawalRequest
from pagamentos.marketplace import wallet


BASE = "/api/pagamentos/marketplace"


@pytest.mark.django_db
def test_recarga_compra_credito_aprovacao_aluno_e_saque_idempotentes(monkeypatch, settings):
    settings.MARKETPLACE_API_TOKEN = "internal-test"
    settings.MARKETPLACE_WITHDRAWAL_ADMIN_TOKEN = "admin-test"
    settings.MP_ACCESS_TOKEN = "TEST-local"
    monkeypatch.setattr(core_models, "relay_apos_commit", lambda: None)
    emitted = []
    monkeypatch.setattr(gateway, "criar_pagamento_pix", lambda **kwargs: (
        emitted.append(kwargs) or gateway.ResultadoPix("MP-TOPUP", "qr", "base64", None)))
    client = Client(HTTP_AUTHORIZATION="Bearer internal-test")
    site = "site-a"
    topup = {"site_id": site, "client_id": "cliente-1", "amount_cents": 20000,
             "idempotency_key": str(uuid.uuid4()), "customer_email": "cliente@example.com",
             "customer_name": "Cliente Exemplo", "customer_cpf": "52998224725"}
    response = client.post(BASE + "/wallets/topups", data=topup, content_type="application/json")
    assert response.status_code == 200
    charge_id = response.json()["id"]
    assert response.json()["status"] == "pending"
    assert response.json()["pix"]["qr_code"] == "qr"
    assert response.json()["wallet_owner_id"] == "cliente-1"
    assert emitted[0]["payer_first_name"] == "Cliente"
    assert emitted[0]["payer_last_name"] == "Exemplo"
    assert emitted[0]["payer_identification"] == {"type": "CPF", "number": "52998224725"}
    assert len(emitted) == 1
    assert client.post(BASE + "/wallets/topups", data=topup, content_type="application/json").json()["id"] == charge_id
    assert len(emitted) == 1
    charge = Charge.objects.get(pk=charge_id)
    assert charge.wallet_owner_id == "cliente-1"
    assert not Recebivel.objects.filter(charge=charge).exists()

    provider_status = {"value": "approved"}
    monkeypatch.setattr(gateway, "consultar_status_do_pagamento", lambda **_: gateway.StatusDoPagamento(
        payment_id="MP-TOPUP", status=provider_status["value"], reason_code="",
        external_reference=str(charge.id), transaction_amount=Decimal("200.00"), currency_id="BRL"))
    detail = BASE + "/charges/" + charge_id
    assert client.get(detail, HTTP_X_SITE_ID=site).json()["status"] == "approved"
    assert client.get(detail, HTTP_X_SITE_ID=site).json()["status"] == "approved"
    balance_url = BASE + "/wallets/client/cliente-1"
    assert client.get(balance_url, HTTP_X_SITE_ID=site).json()["credits"] == 200
    assert WalletEntry.objects.filter(kind="topup", charge=charge).count() == 1
    assert core_models.OutboxEvent.objects.filter(event="marketplace.recarga.aprovada",
                                                  payload__charge_id=str(charge.id)).count() == 1
    assert not core_models.OutboxEvent.objects.filter(event="marketplace.pagamento.aprovado",
                                                      payload__charge_id=str(charge.id)).exists()

    order = str(uuid.uuid4())
    spend = {"site_id": site, "client_id": "cliente-1", "order_id": order,
             "order_version": 1, "amount_cents": 12000, "idempotency_key": str(uuid.uuid4())}
    spend_url = BASE + "/wallets/orders"
    assert client.post(spend_url, data=spend, content_type="application/json").json()["balance_cents"] == 8000
    assert client.post(spend_url, data=spend, content_type="application/json").json()["balance_cents"] == 8000
    assert client.post(spend_url, data={**spend, "idempotency_key": str(uuid.uuid4())},
                       content_type="application/json").status_code == 409
    assert WalletEntry.objects.filter(kind="spend", order_id=order).count() == 1
    earn = {"site_id": site, "aluno_id": "aluno-1", "order_id": order,
            "order_version": 1, "amount_cents": 12000, "idempotency_key": str(uuid.uuid4())}
    earn_url = BASE + "/wallets/student-credits"
    assert client.post(earn_url, data=earn, content_type="application/json").json()["balance_cents"] == 12000
    assert client.post(earn_url, data=earn, content_type="application/json").json()["balance_cents"] == 12000
    assert client.get(BASE + "/wallets/students/aluno-1", HTTP_X_SITE_ID=site).json()["credits"] == 120
    assert WalletEntry.objects.filter(kind="earn", order_id=order).count() == 1

    withdrawal = {"site_id": site, "aluno_id": "aluno-1", "amount_cents": 5000,
                  "idempotency_key": str(uuid.uuid4())}
    withdraw_url = BASE + "/wallets/withdrawals"
    result = client.post(withdraw_url, data=withdrawal, content_type="application/json").json()
    assert result["status"] == "requested"
    assert result["balance_cents"] == 7000
    assert client.post(withdraw_url, data=withdrawal, content_type="application/json").json() == result
    request = WithdrawalRequest.objects.get(pk=result["id"])
    assert request.bank_reference == request.proof_reference == ""
    statement = client.get(BASE + "/wallets/students/aluno-1/statement", HTTP_X_SITE_ID=site).json()
    assert statement["withdrawals"][0]["status"] == "requested"
    assert {item["kind"] for item in statement["entries"]} == {"earn", "withdrawal_hold"}
    assert client.get(withdraw_url, HTTP_X_SITE_ID=site).json()["withdrawals"][0]["id"] == result["id"]
    admin = Client(HTTP_AUTHORIZATION="Bearer admin-test")
    confirm_url = withdraw_url + "/" + result["id"] + "/confirm"
    assert admin.post(confirm_url, data={"site_id": site, "authorization_reference": "",
                                         "bank_reference": "B-1", "proof_reference": "P-1"},
                      content_type="application/json").status_code == 409
    assert WithdrawalRequest.objects.get(pk=result["id"]).status == "requested"
    confirmed = admin.post(confirm_url, data={"site_id": site, "authorization_reference": "A-1",
                                              "bank_reference": "B-1", "proof_reference": "P-1"},
                           content_type="application/json").json()
    assert confirmed["status"] == "paid"
    assert confirmed["bank_reference"] == "B-1"
    assert client.post(withdraw_url, data={**withdrawal, "idempotency_key": str(uuid.uuid4()),
                                                "amount_cents": 4900}, content_type="application/json").status_code == 409

    provider_status["value"] = "refunded"
    assert client.get(detail, HTTP_X_SITE_ID=site).json()["status"] == "refunded"
    assert client.get(balance_url, HTTP_X_SITE_ID=site).json()["balance_cents"] == -12000
    assert WalletEntry.objects.filter(kind="topup_reversal", charge=charge).count() == 1


@pytest.mark.django_db
def test_carteira_recusa_gasto_sem_saldo_e_credito_sem_debito(settings):
    settings.MARKETPLACE_API_TOKEN = "internal-test"
    client = Client(HTTP_AUTHORIZATION="Bearer internal-test")
    order = str(uuid.uuid4())
    spend = {"site_id": "site-a", "client_id": "cliente-1", "order_id": order,
             "order_version": 1, "amount_cents": 10000, "idempotency_key": str(uuid.uuid4())}
    assert client.post(BASE + "/wallets/orders", data=spend, content_type="application/json").status_code == 409
    earn = {"site_id": "site-a", "aluno_id": "aluno-1", "order_id": order,
            "order_version": 1, "amount_cents": 10000, "idempotency_key": str(uuid.uuid4())}
    assert client.post(BASE + "/wallets/student-credits", data=earn, content_type="application/json").status_code == 409
    assert WalletEntry.objects.count() == 0


@pytest.mark.django_db
def test_recarga_exige_identidade_completa_e_email_aceito_pelo_provedor(monkeypatch, settings):
    settings.MARKETPLACE_API_TOKEN = "internal-test"
    settings.MP_ACCESS_TOKEN = "TEST-local"
    monkeypatch.setattr(gateway, "criar_pagamento_pix", lambda **_: pytest.fail("não enviar Pix inválido"))
    client = Client(HTTP_AUTHORIZATION="Bearer internal-test")
    body = {"site_id": "site-a", "client_id": "cliente-1", "amount_cents": 10000,
            "idempotency_key": str(uuid.uuid4()), "customer_email": "x@example.test",
            "customer_name": "Cliente Exemplo", "customer_cpf": "52998224725"}
    assert client.post(BASE + "/wallets/topups", data=body, content_type="application/json").status_code == 422
    body["customer_email"] = "cliente@example.com"
    body["customer_cpf"] = "11111111111"
    assert client.post(BASE + "/wallets/topups", data=body, content_type="application/json").status_code == 422
    body["customer_cpf"] = "52998224725"
    body["customer_name"] = "Cliente"
    assert client.post(BASE + "/wallets/topups", data=body, content_type="application/json").status_code == 422
    assert Charge.objects.count() == 0


@pytest.mark.django_db
def test_devolucao_parcial_congela_gasto_sem_descontar_valor_inventado():
    charge = Charge.objects.create(
        idempotency_key=uuid.uuid4(), site_id="site-a", order_id=uuid.uuid4(),
        order_version=1, amount_cents=10000, currency="BRL", environment="sandbox",
        method="pix", customer_email="cliente@example.com", wallet_owner_id="cliente-1",
        status="approved", provider_reference="MP-PARTIAL")
    wallet.creditar_recarga(charge)
    charge.status = "partially_refunded"
    charge.save(update_fields=["status", "updated_at"])
    wallet.reverter_recarga(charge)
    current = wallet.balance(site_id="site-a", owner_kind="client", owner_id="cliente-1")
    assert current["balance_cents"] == 10000
    assert current["frozen"] is True
    with pytest.raises(wallet.WalletConflict):
        wallet.spend(site_id="site-a", client_id="cliente-1", order_id=uuid.uuid4(),
                     order_version=1, amount_cents=100, idempotency_key=uuid.uuid4())
