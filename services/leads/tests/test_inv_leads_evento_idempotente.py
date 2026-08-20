# tests/test_inv_leads_evento_idempotente.py  # [RECEITA:R5 v1]
# Nome do arquivo = o invariante da célula (AGENTS.leads.md): "o mesmo event_id
# processado duas vezes gera uma única entrada de timeline".
import uuid

import pytest

from apps.core.handlers import (
    ao_pagamento_aprovado,
    ao_pagamento_recusado,
    ao_pedido_criado,
    ao_pix_expirado,
    ao_quiz_completado,
    processar_envelope,
)
from apps.core.models import EventoProcessado, Lead, TimelineEvent

pytestmark = pytest.mark.django_db


def _envelope(evento: str, data: dict) -> dict:
    return {
        "event": evento,
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": "2026-08-20T12:00:00Z",
        "data": data,
    }


@pytest.mark.parametrize(
    "evento,handler,data",
    [
        (
            "quiz.completado",
            ao_quiz_completado,
            {
                "site_id": "site-a",
                "quiz_slug": "crivo",
                "result_key": "perfil-1",
                "score": 80,
                "lead": {"email": "ana@example.com", "name": "Ana"},
            },
        ),
        (
            "pedido.criado",
            ao_pedido_criado,
            {
                "site_id": "site-a",
                "order_id": "ord-1",
                "items": [
                    {
                        "product_id": "p1",
                        "name": "Curso",
                        "price_cents": 990,
                        "kind": "principal",
                    }
                ],
                "total_cents": 990,
                "customer": {"email": "ana@example.com", "name": "Ana"},
            },
        ),
        (
            "pagamento.aprovado",
            ao_pagamento_aprovado,
            {
                "site_id": "site-a",
                "payment_id": "pay-1",
                "order_id": "ord-1",
                "amount_cents": 990,
                "method": "pix",
                "mp_payment_id": "mp-1",
                "customer": {"email": "ana@example.com", "name": "Ana"},
            },
        ),
        (
            "pagamento.recusado",
            ao_pagamento_recusado,
            {
                "site_id": "site-a",
                "payment_id": "pay-2",
                "order_id": "ord-2",
                "amount_cents": 990,
                "method": "card",
                "reason_code": "cc_rejected_insufficient_amount",
                "customer": {"email": "ana@example.com", "name": "Ana"},
            },
        ),
        (
            "pix.expirado",
            ao_pix_expirado,
            {
                "site_id": "site-a",
                "payment_id": "pay-3",
                "order_id": "ord-3",
                "amount_cents": 990,
                "customer": {"email": "ana@example.com", "name": "Ana"},
                "recovery_url": "https://site-a.exemplo/recuperar/ord-3",
            },
        ),
    ],
)
def test_evento_reentregue_gera_uma_entrada_de_timeline(evento, handler, data):
    envelope = _envelope(evento, data)

    processar_envelope(envelope, handler)
    processar_envelope(envelope, handler)  # reentrega — mesmo event_id

    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 1
    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert TimelineEvent.objects.filter(lead=lead, event=evento).count() == 1


def test_pessoa_em_varios_eventos_acumula_timeline_sem_perder_historico():
    """[invariante da célula] merge de pessoas preserva timeline integral."""
    quiz = _envelope(
        "quiz.completado",
        {
            "site_id": "site-a",
            "quiz_slug": "crivo",
            "result_key": "perfil-1",
            "score": 80,
            "lead": {"email": "ana@example.com", "name": "Ana"},
        },
    )
    pedido = _envelope(
        "pedido.criado",
        {
            "site_id": "site-a",
            "order_id": "ord-9",
            "items": [
                {
                    "product_id": "p1",
                    "name": "Curso",
                    "price_cents": 990,
                    "kind": "principal",
                }
            ],
            "total_cents": 990,
            "customer": {"email": "ana@example.com", "name": "Ana"},
        },
    )

    processar_envelope(quiz, ao_quiz_completado)
    processar_envelope(pedido, ao_pedido_criado)

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        Lead.objects.filter(email="ana@example.com").count() == 1
    )  # mesma pessoa, um lead
    assert TimelineEvent.objects.filter(lead=lead).count() == 2
    assert set(
        TimelineEvent.objects.filter(lead=lead).values_list("event", flat=True)
    ) == {
        "quiz.completado",
        "pedido.criado",
    }
