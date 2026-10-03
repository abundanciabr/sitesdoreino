from __future__ import annotations
import time
import httpx
import pytest
import respx
from django.test import Client
from pagamentos.core.models import OutboxEvent, PaymentAttempt
from test_webhook_endurecimento import _criar_intent, _postar_webhook, _URL_CONSULTA
pytestmark = pytest.mark.django_db

def test_card_corpo_adulterado_decisao_segue_a_api(client: Client) -> None:
    """Mesma lei para o cartão: corpo forjado "approved", API diz "rejected"
    ⇒ recusado, com a rota GET comprovadamente chamada."""
    mp_payment_id = "333000111"
    intent = _criar_intent("card", mp_payment_id)
    tentativa = PaymentAttempt.objects.create(
        intent=intent, platform_site_id=intent.site_id, provider="mercadopago",
        provider_reference_id=mp_payment_id, amount_cents=1990,
        effective_amount_cents=1990, installments=1,
        request_hash="a" * 64, state="pending",
    )

    with respx.mock(assert_all_called=True) as mp:
        rota_consulta = mp.get(_URL_CONSULTA.format(id=mp_payment_id)).mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": int(mp_payment_id),
                    "status": "rejected",
                    "status_detail": "cc_rejected_call_for_authorize",
                    "external_reference": str(tentativa.operation_id),
                    "transaction_amount": 19.9,
                    "currency_id": "BRL",
                },
            )
        )
        resp = _postar_webhook(
            client,
            method="card",
            data_id=mp_payment_id,
            body_status="approved",
            ts=int(time.time()),
        )

    assert resp.status_code == 200
    assert rota_consulta.call_count == 1
    intent.refresh_from_db()
    assert intent.status == "rejected"
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 0
    assert (
        OutboxEvent.objects.get(event="pagamento.recusado").payload["reason_code"]
        == "cc_rejected_call_for_authorize"
    )


