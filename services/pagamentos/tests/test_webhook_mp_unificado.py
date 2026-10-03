import json
import uuid

import pytest
from django.test import Client

from pagamentos.core.models import Intent, MercadoPagoWebhookInbox, PaymentAttempt
from pagamentos.core.webhook_signature import assinar


pytestmark = pytest.mark.django_db
URL = "/api/pagamentos/mp/webhooks"


def _post(client: Client, resource_id: str, body: dict, *, path: str = URL):
    headers = assinar(data_id=resource_id, request_id=str(uuid.uuid4()))
    return client.post(
        f"{path}?data.id={resource_id}",
        data=json.dumps(body),
        content_type="application/json",
        HTTP_X_SIGNATURE=headers["x-signature"],
        HTTP_X_REQUEST_ID=headers["x-request-id"],
    )


@pytest.mark.parametrize("topic", [
    "orders", "order", "mp-connect", "stop_delivery_op_wh",
    "topic_claims_integration_wh", "topic_card_id_wh",
    "topic_merchant_order_wh", "topic_chargebacks_wh",
    "subscription_authorized_payment", "subscription_preapproval",
    "subscription_preapproval_plan", "merchant_order", "claims",
    "chargebacks", "fraudalerts", "applicationlink", "cardupdater",
])
def test_topico_futuro_guarda_so_metadados_idempotentes(client, monkeypatch, topic):
    def sem_consulta(**_kwargs):
        raise AssertionError("topico futuro nao consulta o MP")

    monkeypatch.setattr("pagamentos.core.gateway.consultar_status_do_pagamento", sem_consulta)
    corpo = {"type": topic, "data": {"id": "identificador-privado", "email": "nunca@guardar"}}
    assert _post(client, "identificador-privado", corpo).status_code == 200
    assert _post(client, "identificador-privado", corpo).json()["novo"] is False
    aviso = MercadoPagoWebhookInbox.objects.get(topic=topic)
    assert len(aviso.resource_id_hash) == 64
    assert "identificador-privado" not in aviso.resource_id_hash
    assert "email" not in aviso.__dict__


def test_sem_assinatura_nao_grava_inbox(client):
    resp = client.post(
        URL + "?data.id=42", data=json.dumps({"type": "orders"}),
        content_type="application/json",
    )
    assert resp.status_code == 403
    assert MercadoPagoWebhookInbox.objects.count() == 0


@pytest.mark.parametrize("method", ["pix", "card"])
def test_pagamento_despachado_pelo_metodo_local(client, monkeypatch, method):
    intent = Intent.objects.create(
        idempotency_key=str(uuid.uuid4()), site_id="site-opaco", order_id="pedido",
        method=method, status="pending", amount_cents=1990,
        customer={"email": "cliente@exemplo.com", "name": "Teste"},
    )
    PaymentAttempt.objects.create(
        intent=intent, platform_site_id=intent.site_id, provider="mercadopago",
        provider_reference_id="87654321", amount_cents=1990,
        effective_amount_cents=1990, request_hash="a" * 64, state="pending",
    )
    chamado = []
    monkeypatch.setattr(
        "pagamentos.api.webhooks.processar_webhook_pix",
        lambda _request: chamado.append("pix") or {"recebido": True},
    )
    monkeypatch.setattr(
        "pagamentos.api.webhooks.processar_webhook_card",
        lambda _request: chamado.append("card") or {"recebido": True},
    )
    resp = _post(client, "87654321", {"type": "payment", "data": {"id": "87654321"}})
    assert resp.status_code == 200
    assert chamado == [method]


def test_alias_e_slash_recebem_aviso(client):
    for path in [URL + "/", "/api/pagamentos/mercadopago/webhooks",
                 "/api/pagamentos/mercadopago/webhooks/"]:
        assert _post(client, "recurso-1", {"type": "orders"}, path=path).status_code == 200
    assert MercadoPagoWebhookInbox.objects.count() == 1


def test_payment_desconhecido_nao_consulta_mp(client, monkeypatch):
    def sem_consulta(**_kwargs):
        raise AssertionError("ID desconhecido nao consulta o MP")

    monkeypatch.setattr("pagamentos.core.gateway.consultar_status_do_pagamento", sem_consulta)
    assert _post(client, "123456", {"type": "payment"}).json() == {"ignorado": True}
