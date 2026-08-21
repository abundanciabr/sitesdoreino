# tests/test_inv_p5_dedup_atomico.py  # [RECEITA:R4 v1]
# Nome do arquivo = código do invariante (INVARIANTES.md).
#
# INV-P5 tem duas metades. `test_inv_p5_matricula_lock.py` guarda a metade
# "nunca DUAS matrículas" (evento duplicado/concorrente). Este arquivo guarda a
# metade "nunca ZERO": entrega at-least-once só vira exatamente-uma se o registro
# de dedup e o efeito do evento forem desfeitos juntos quando o handler falha.
# Sem isso, um evento que falhou no meio fica marcado como processado e toda
# reentrega futura é descartada em silêncio — cliente pago, aluno não matriculado.
import uuid

import pytest
from django.db import IntegrityError

from apps.eventos.management.commands.consume_eventos import (
    HANDLERS,
    processar_envelope,
)
from apps.eventos.models import EventoProcessado
from apps.matriculas.handlers import ao_pagamento_aprovado
from apps.matriculas.models import Matricula

pytestmark = pytest.mark.django_db

ORDER_ID = "order-atomicidade"


def _envelope(event_id: str) -> dict:
    return {
        "event": "pagamento.aprovado",
        "version": 1,
        "event_id": event_id,
        "occurred_at": "2026-08-20T12:00:00Z",
        "data": {
            "site_id": "site-1",
            "payment_id": "pay-1",
            "order_id": ORDER_ID,
            "amount_cents": 9900,
            "method": "pix",
            "mp_payment_id": "mp-1",
            "customer": {"email": "aluno@example.com", "name": "Aluno Exemplo"},
        },
    }


def test_handler_que_falha_no_meio_nao_deixa_evento_marcado_nem_matricula():
    """O handler matricula e SÓ ENTÃO estoura — é o hiccup de 2s do Postgres, a
    conexão que cai, o processo que morre depois do INSERT. Se a matrícula
    sobrevivesse pela metade, ou se o EventoProcessado sobrevivesse, a reentrega
    do mesmo evento seria descartada e a matrícula nunca aconteceria."""
    envelope = _envelope(str(uuid.uuid4()))

    def handler_que_falha_depois_de_matricular(data: dict) -> None:
        ao_pagamento_aprovado(data)  # o efeito acontece de verdade...
        raise RuntimeError("conexão caiu depois do INSERT")  # ...e então falha

    with pytest.raises(RuntimeError):
        processar_envelope(
            envelope, {"pagamento.aprovado": handler_que_falha_depois_de_matricular}
        )

    # (a) o efeito do handler foi desfeito
    assert Matricula.objects.filter(order_id=ORDER_ID).count() == 0
    # (b) o registro de dedup foi desfeito junto — é isto que o bug quebrava
    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 0

    # (c) o ponto todo: a MESMA entrega, de novo, matricula normalmente
    processar_envelope(envelope, HANDLERS)

    assert Matricula.objects.filter(order_id=ORDER_ID).count() == 1
    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 1


def test_integrityerror_do_handler_nao_e_confundido_com_evento_ja_processado():
    """A armadilha da correção óbvia: com o handler dentro do `try`, um
    IntegrityError vindo DELE (constraint que nada tem a ver com event_id) cairia
    no `except IntegrityError: return` e o evento sumiria em silêncio. O savepoint
    interno existe para que o `except` só enxergue o create() do EventoProcessado."""
    envelope = _envelope(str(uuid.uuid4()))

    def handler_com_integrityerror_alheio(data: dict) -> None:
        raise IntegrityError("constraint sem relação nenhuma com event_id")

    with pytest.raises(IntegrityError):
        processar_envelope(
            envelope, {"pagamento.aprovado": handler_com_integrityerror_alheio}
        )

    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 0

    # e a reentrega continua sendo processada, não descartada
    processar_envelope(envelope, HANDLERS)

    assert Matricula.objects.filter(order_id=ORDER_ID).count() == 1
