# tests/test_inv_leads_evento_atomico.py  # [RECEITA:R4 v1]
# Nome do arquivo = o invariante da célula (AGENTS.leads.md).
#
# O invariante tem duas metades. `test_inv_leads_evento_idempotente.py` guarda a
# metade "nunca DUAS entradas de timeline" (mesmo event_id 2× ⇒ uma entrada).
# Este arquivo guarda a metade "nunca ZERO": entrega at-least-once só vira
# exatamente-uma se o registro de dedup e o efeito do evento forem desfeitos
# juntos quando o handler falha. Sem isso, um evento que falhou no meio fica
# marcado como processado e toda reentrega é descartada em silêncio — buraco
# permanente na história da pessoa, que é o que esta célula existe para guardar.
import uuid

import pytest
from django.db import IntegrityError

from apps.core.handlers import ao_pagamento_aprovado, processar_envelope
from apps.core.models import EventoProcessado, Lead, TimelineEvent

pytestmark = pytest.mark.django_db

DATA = {
    "site_id": "site-a",
    "payment_id": "pay-1",
    "order_id": "ord-1",
    "amount_cents": 990,
    "method": "pix",
    "mp_payment_id": "mp-1",
    "customer": {"email": "ana@example.com", "name": "Ana"},
}


def _envelope() -> dict:
    return {
        "event": "pagamento.aprovado",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": "2026-08-20T12:00:00Z",
        "data": DATA,
    }


def test_handler_que_falha_no_meio_nao_deixa_evento_marcado_nem_timeline():
    """O handler grava a timeline e SÓ ENTÃO estoura — é a conexão que cai, o
    processo que morre depois do INSERT. Se o EventoProcessado sobrevivesse à
    falha, a reentrega do mesmo evento seria descartada e a entrada de timeline
    nunca existiria."""
    envelope = _envelope()

    def handler_que_falha_depois_de_gravar(event_id: str, data: dict) -> None:
        ao_pagamento_aprovado(event_id, data)  # o efeito acontece de verdade...
        raise RuntimeError("conexão caiu depois do INSERT")  # ...e então falha

    with pytest.raises(RuntimeError):
        processar_envelope(envelope, handler_que_falha_depois_de_gravar)

    # (a) o efeito do handler foi desfeito por inteiro — lead e timeline
    assert Lead.objects.filter(site_id="site-a", email="ana@example.com").count() == 0
    assert TimelineEvent.objects.count() == 0
    # (b) o registro de dedup foi desfeito junto — é isto que o bug quebrava
    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 0

    # (c) o ponto todo: a MESMA entrega, de novo, é processada normalmente
    assert processar_envelope(envelope, ao_pagamento_aprovado) is True

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.aprovado").count() == 1
    )
    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 1


def test_integrityerror_do_handler_nao_e_confundido_com_evento_ja_processado():
    """A armadilha da correção óbvia: com o handler dentro do `try`, um
    IntegrityError vindo DELE cairia no `except IntegrityError: return False` e o
    evento sumiria em silêncio. Aqui a colisão é real, não sintética — é a
    constraint uniq_lead_site_email, a mesma que `_upsert_lead()` disputa sob
    corrida."""
    Lead.objects.create(site_id="site-a", email="ana@example.com")  # já existe
    envelope = _envelope()

    def handler_que_colide_em_outra_constraint(event_id: str, data: dict) -> None:
        Lead.objects.create(site_id=data["site_id"], email=data["customer"]["email"])

    with pytest.raises(IntegrityError):
        processar_envelope(envelope, handler_que_colide_em_outra_constraint)

    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 0

    # e a reentrega continua sendo processada, não descartada
    assert processar_envelope(envelope, ao_pagamento_aprovado) is True

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.aprovado").count() == 1
    )
