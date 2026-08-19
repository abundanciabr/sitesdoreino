# tests/test_inv_p6_outbox.py  # [RECEITA:R5 v1]
# Nome do arquivo = código do invariante. Um arquivo por invariante.
import json
import uuid
from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client

from pagamentos.core.models import Intent, OutboxEvent, relay_outbox
from pagamentos.core.webhook_signature import assinar
from pagamentos.providers.mercadopago.client import MercadoPagoClient

pytestmark = pytest.mark.django_db

_MP_PAYMENT_ID = "999888777"
_RESPOSTA_PIX_MP = {
    "id": int(_MP_PAYMENT_ID),
    "status": "pending",
    "date_of_expiration": "2026-08-19T00:00:00.000-03:00",
    "point_of_interaction": {
        "transaction_data": {"qr_code": "copia-e-cola", "qr_code_base64": "aGVsbG8="}
    },
}


@pytest.fixture
def token_valido(settings: Any) -> str:
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def _criar_intent_pix(client: Client, token: str) -> Intent:
    with patch.object(
        MercadoPagoClient, "criar_pagamento_pix", return_value=_RESPOSTA_PIX_MP
    ):
        resp = client.post(
            "/api/pagamentos/intents",
            data=json.dumps(
                {
                    "site_id": "site-opaco-abc123",
                    "order_id": "pedido-inv-p6",
                    "amount_cents": 1990,
                    "currency": "BRL",
                    "method": "pix",
                    "customer": {
                        "email": "cliente@exemplo.com",
                        "name": "Cliente Teste",
                    },
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
    assert resp.status_code == 201
    return Intent.objects.get(id=resp.json()["id"])


def _postar_webhook_assinado(client: Client, *, status: str) -> Any:
    request_id = str(uuid.uuid4())
    headers = assinar(data_id=_MP_PAYMENT_ID, request_id=request_id)
    return client.post(
        f"/api/pagamentos/webhooks/mp/pix?data.id={_MP_PAYMENT_ID}",
        data=json.dumps({"data": {"id": _MP_PAYMENT_ID, "status": status}}),
        content_type="application/json",
        HTTP_X_SIGNATURE=headers["x-signature"],
        HTTP_X_REQUEST_ID=headers["x-request-id"],
    )


@pytest.mark.django_db(transaction=True)
def test_aprovacao_grava_outbox_na_mesma_transacao_e_relay_publica(
    client: Client, token_valido: str
) -> None:
    """[INV-P6] Depois do webhook: a Intent já está "approved" E a linha da
    outbox já existe com o payload certo E o relay (chamado via
    transaction.on_commit) já publicou (published_at preenchido) — as duas
    mudanças (estado + evento) nascem juntas, nunca uma sem a outra.

    `transaction=True`: transaction.on_commit só dispara com commit real no
    banco — o `django_db` padrão do módulo embrulha o teste numa transação
    que só faz ROLLBACK (nunca commita), o que faria este teste "passar" por
    engano (on_commit nunca rodaria de verdade)."""
    intent = _criar_intent_pix(client, token_valido)

    resp = _postar_webhook_assinado(client, status="approved")

    assert resp.status_code == 200
    intent.refresh_from_db()
    assert intent.status == "approved"
    evento = OutboxEvent.objects.get(event="pagamento.aprovado")
    assert evento.payload["order_id"] == intent.order_id
    assert evento.payload["site_id"] == intent.site_id
    assert evento.payload["mp_payment_id"] == _MP_PAYMENT_ID
    assert evento.published_at is not None  # relay já publicou no Redis Streams


@pytest.mark.django_db(transaction=True)
def test_falha_do_relay_nao_perde_o_evento_fica_pendente_e_republicavel(
    client: Client, token_valido: str
) -> None:
    """[INV-P6] "falha simulada do relay ⇒ evento permanece pendente e é
    republicado, nunca perdido" (INVARIANTES.md). A transação de estado+outbox
    já commitou ANTES do relay rodar (on_commit) — um Redis fora do ar não
    derruba a resposta do webhook nem perde o evento. `transaction=True`: ver
    docstring do teste anterior."""
    intent = _criar_intent_pix(client, token_valido)

    with patch(
        "pagamentos.core.models.redis.from_url",
        side_effect=RuntimeError("redis fora do ar"),
    ):
        resp = _postar_webhook_assinado(client, status="approved")

    assert resp.status_code == 200  # relay falhou, mas o webhook não quebra
    intent.refresh_from_db()
    assert intent.status == "approved"  # a transição já tinha commitado
    evento = OutboxEvent.objects.get(event="pagamento.aprovado")
    assert evento.published_at is None  # relay falhou: evento fica pendente

    publicados = relay_outbox()  # republicação manual (ex.: próxima chamada)
    assert publicados == 1
    evento.refresh_from_db()
    assert evento.published_at is not None  # nunca perdido


def test_falha_entre_transicao_e_emitir_desfaz_os_dois_estado_sem_evento_impossivel(
    client: Client, token_valido: str
) -> None:
    """[INV-P6] "Estado sem evento e evento sem estado são ambos impossíveis."
    Prova a atomicidade de verdade: uma falha injetada DEPOIS do
    intent.save(status) mas DENTRO do transaction.atomic() (em emitir()) desfaz
    a transição de status também — nunca fica um pagamento "approved" sem o
    evento correspondente na outbox."""
    intent = _criar_intent_pix(client, token_valido)

    with patch(
        "pagamentos.core.models.emitir", side_effect=RuntimeError("boom no emitir")
    ):
        with pytest.raises(RuntimeError):
            _postar_webhook_assinado(client, status="approved")

    intent.refresh_from_db()
    assert intent.status == "pending"  # rollback: NÃO ficou "approved" sem evento
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 0
