# tests/test_eventos_consumer.py  # [RECEITA:R4 v1]
import uuid

import pytest

from apps.eventos.management.commands.consume_eventos import (
    HANDLERS,
    processar_envelope,
)
from apps.eventos.models import EventoProcessado
from apps.matriculas.models import Matricula

pytestmark = pytest.mark.django_db


def _envelope(event_id: str, *, pedido: str = "order-reentrega") -> dict:
    """Um aviso na versão 1. O `mp_payment_id` acompanha o pedido porque ele é
    a identidade do pagamento NO PROVEDOR: dois pedidos diferentes com a mesma
    referência seriam o mesmo dinheiro cobrado duas vezes, e o dedup entre
    versões (que lê essa referência) os trataria como um fato só."""
    return {
        "event": "pagamento.aprovado",
        "version": 1,
        "event_id": event_id,
        "occurred_at": "2026-08-20T12:00:00Z",
        "data": {
            "site_id": "site-1",
            "payment_id": f"pay-{pedido}",
            "order_id": pedido,
            "amount_cents": 9900,
            "method": "pix",
            "mp_payment_id": f"mp-{pedido}",
            "customer": {"email": "aluno@example.com", "name": "Aluno Exemplo"},
        },
    }


def test_evento_reentregue_mesmo_event_id_gera_uma_matricula():
    envelope = _envelope(str(uuid.uuid4()))

    for _ in range(3):
        processar_envelope(envelope, HANDLERS)

    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 1
    assert Matricula.objects.filter(order_id="order-reentrega").count() == 1


def test_evento_de_site_diferente_nao_colide_com_outro_order_id():
    e1 = _envelope(str(uuid.uuid4()))
    e2 = _envelope(str(uuid.uuid4()), pedido="order-outro")

    processar_envelope(e1, HANDLERS)
    processar_envelope(e2, HANDLERS)

    assert Matricula.objects.count() == 2
