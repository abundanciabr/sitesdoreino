# tests/test_webhook_endurecimento.py
# Guardas do despacho "webhook-endurecimento": a decisão do webhook depende SÓ
# do que é confiável — o `data.id` do manifesto assinado e uma janela de tempo
# sobre o `ts`; NUNCA o corpo não assinado. Evidência no TRANSPORTE (respx,
# ARMADILHAS §6.9): a consulta GET à API do MP é uma rota mockada e os testes
# afirmam que ela foi (ou não foi) chamada de verdade.
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

import httpx
import pytest
import respx
from django.conf import settings
from django.test import Client

from pagamentos.core.models import Intent, OutboxEvent

pytestmark = pytest.mark.django_db

_URL_CONSULTA = "https://api.mercadopago.com/v1/payments/{id}"


def _criar_intent(method: str, mp_payment_id: str) -> Intent:
    """Intent direto no banco — o alvo destes testes é o WEBHOOK, não a
    criação de intent (que tem guardas próprios em test_transporte_mp_*)."""
    return Intent.objects.create(
        idempotency_key=str(uuid.uuid4()),
        site_id="site-opaco-abc123",
        order_id=f"pedido-endurecimento-{method}",
        method=method,
        status="pending",
        amount_cents=1990,
        customer={"email": "cliente@exemplo.com", "name": "Cliente Teste"},
        provider_payment_id=mp_payment_id,
    )


def _headers_assinados(*, data_id: str, ts: int) -> dict[str, str]:
    """Assinatura HMAC VÁLIDA (mesmo segredo do servidor) com um `ts`
    arbitrário — é assim que se forja o replay: assinatura legítima capturada,
    reapresentada fora da janela."""
    request_id = str(uuid.uuid4())
    manifest = f"id:{data_id.lower()};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(
        settings.MP_WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256
    ).hexdigest()
    return {"x-signature": f"ts={ts},v1={v1}", "x-request-id": request_id}


def _postar_webhook(
    client: Client, *, method: str, data_id: str, body_status: str, ts: int
) -> Any:
    headers = _headers_assinados(data_id=data_id, ts=ts)
    return client.post(
        f"/api/pagamentos/webhooks/mp/{method}?data.id={data_id}",
        data=json.dumps({"data": {"id": data_id, "status": body_status}}),
        content_type="application/json",
        HTTP_X_SIGNATURE=headers["x-signature"],
        HTTP_X_REQUEST_ID=headers["x-request-id"],
    )


# ---------------------------------------------------------------------------
# Proteção 1 — janela de tempo sobre o ts assinado (anti-replay)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("desvio_segundos", [-3600, 3600])
def test_ts_fora_da_janela_e_403_zero_efeito_e_zero_consulta(
    client: Client, desvio_segundos: int
) -> None:
    """HMAC VÁLIDO mas `ts` a 1h de distância (passado OU futuro) ⇒ 403, banco
    intacto, outbox vazia — e NENHUMA chamada à API do MP (o respx está armado
    sem rotas: qualquer chamada estouraria o teste)."""
    mp_payment_id = f"111000{abs(desvio_segundos)}"
    intent = _criar_intent("pix", mp_payment_id)

    with respx.mock:  # sem rotas: chamada de rede aqui = falha do teste
        resp = _postar_webhook(
            client,
            method="pix",
            data_id=mp_payment_id,
            body_status="approved",
            ts=int(time.time()) + desvio_segundos,
        )

    assert resp.status_code == 403
    intent.refresh_from_db()
    assert intent.status == "pending"  # zero efeito colateral [INV-P10]
    assert OutboxEvent.objects.count() == 0


def test_ts_dentro_da_janela_e_aceito(client: Client) -> None:
    """Controle positivo da janela: o MESMO forjador de assinatura dos testes
    acima, com ts atual, passa — prova que o 403 é sobre a JANELA, não sobre
    um defeito no forjador."""
    mp_payment_id = "111000999"
    _criar_intent("pix", mp_payment_id)

    with respx.mock(assert_all_called=True) as mp:
        mp.get(_URL_CONSULTA.format(id=mp_payment_id)).mock(
            return_value=httpx.Response(
                200, json={"id": int(mp_payment_id), "status": "approved"}
            )
        )
        resp = _postar_webhook(
            client,
            method="pix",
            data_id=mp_payment_id,
            body_status="approved",
            ts=int(time.time()),
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Proteção 2 — a decisão segue a API, nunca o corpo não assinado
# ---------------------------------------------------------------------------


def test_pix_corpo_adulterado_decisao_segue_a_api(client: Client) -> None:
    """O ataque do despacho: corpo diz "approved" com assinatura válida (a
    x-signature NÃO cobre o corpo), mas a API do MP diz "rejected". A decisão
    segue a API: a intent vira rejected, o evento é pagamento.recusado (com o
    reason_code DA API, não do corpo) e nenhum pagamento.aprovado existe. A
    rota GET mockada foi chamada de verdade — a prova de que a consulta é o
    que decide."""
    mp_payment_id = "222000111"
    intent = _criar_intent("pix", mp_payment_id)

    with respx.mock(assert_all_called=True) as mp:
        rota_consulta = mp.get(_URL_CONSULTA.format(id=mp_payment_id)).mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": int(mp_payment_id),
                    "status": "rejected",
                    "status_detail": "cc_rejected_high_risk",
                },
            )
        )
        resp = _postar_webhook(
            client,
            method="pix",
            data_id=mp_payment_id,
            body_status="approved",  # ← a mentira do corpo
            ts=int(time.time()),
        )

    assert resp.status_code == 200
    assert rota_consulta.call_count == 1  # a API FOI consultada
    intent.refresh_from_db()
    assert intent.status == "rejected"  # a decisão seguiu a API, não o corpo
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 0
    evento = OutboxEvent.objects.get(event="pagamento.recusado")
    assert evento.payload["reason_code"] == "cc_rejected_high_risk"  # da API


def test_card_corpo_adulterado_decisao_segue_a_api(client: Client) -> None:
    """Mesma lei para o cartão: corpo forjado "approved", API diz "rejected"
    ⇒ recusado, com a rota GET comprovadamente chamada."""
    mp_payment_id = "333000111"
    intent = _criar_intent("card", mp_payment_id)

    with respx.mock(assert_all_called=True) as mp:
        rota_consulta = mp.get(_URL_CONSULTA.format(id=mp_payment_id)).mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": int(mp_payment_id),
                    "status": "rejected",
                    "status_detail": "cc_rejected_call_for_authorize",
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


def test_consulta_indisponivel_e_502_zero_efeito(client: Client) -> None:
    """Fail-closed da consulta: MP fora do ar (500 no GET) ⇒ o webhook responde
    502 (o MP reentrega depois) e NADA transiciona — decidir sem a fonte de
    verdade não existe."""
    mp_payment_id = "444000111"
    intent = _criar_intent("pix", mp_payment_id)

    with respx.mock(assert_all_called=True) as mp:
        mp.get(_URL_CONSULTA.format(id=mp_payment_id)).mock(
            return_value=httpx.Response(500, json={"message": "internal error"})
        )
        resp = _postar_webhook(
            client,
            method="pix",
            data_id=mp_payment_id,
            body_status="approved",
            ts=int(time.time()),
        )

    assert resp.status_code == 502
    intent.refresh_from_db()
    assert intent.status == "pending"  # zero efeito colateral
    assert OutboxEvent.objects.count() == 0


def test_data_id_desconhecido_nao_consulta_a_api(client: Client) -> None:
    """id assinado que não corresponde a nenhuma intent ⇒ ignorado SEM gastar
    chamada à API (respx armado sem rotas: uma chamada estouraria o teste)."""
    with respx.mock:
        resp = _postar_webhook(
            client,
            method="pix",
            data_id="999999999",
            body_status="approved",
            ts=int(time.time()),
        )

    assert resp.status_code == 200
    assert resp.json() == {"ignorado": True}
    assert OutboxEvent.objects.count() == 0
