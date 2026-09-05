# tests/test_inv_mensageria_evento_atomico.py  # [RECEITA:R4 v1]
# Nome do arquivo = o invariante da célula (AGENTS.mensageria.md): "consumo
# idempotente por event_id — evento reentregue ⇒ UM envio".
#
# O invariante tem duas metades. `test_idempotencia_por_evento.py` guarda a
# metade "nunca DOIS envios". Este arquivo guarda a metade "nunca ZERO": entrega
# at-least-once só vira exatamente-uma se o registro de dedup e o efeito do
# evento forem desfeitos juntos quando o handler falha.
#
# Nesta célula o buraco era o mais afiado das três que copiaram a receita R4: o
# caminho de dedup dá xack, então uma reentrega descartada saía do stream de vez.
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import IntegrityError

from apps.eventos.handlers import ao_pagamento_aprovado
from apps.eventos.management.commands.consume_eventos import processar_envelope
from apps.eventos.models import EnvioRegistrado, EventoProcessado

pytestmark = pytest.mark.django_db(transaction=True)

DATA = {
    "site_id": "site-abc",
    "payment_id": "pay-1",
    "order_id": "order-1",
    "amount_cents": 1000,
    "method": "pix",
    "mp_payment_id": "mp-1",
    "customer": {"email": "cliente@example.com", "name": "Cliente Um"},
}


def _envelope() -> dict:
    return {
        "event": "pagamento.aprovado",
        "version": 1,
        "event_id": str(uuid4()),
        "occurred_at": "2026-08-20T12:00:00Z",
        "data": DATA,
    }


def test_handler_que_falha_no_meio_nao_deixa_evento_marcado_nem_envio():
    """O handler registra o envio e SÓ ENTÃO estoura. Se o EventoProcessado
    sobrevivesse, a reentrega cairia no dedup — e aqui o dedup dá xack, então a
    mensagem sairia do stream e a notificação nunca mais aconteceria."""
    envelope = _envelope()

    def handler_que_falha_depois_de_registrar(
        data: dict, event_id: str | None = None, ator_id: str | None = None
    ) -> None:
        # A assinatura ganhou o `event_id` em 02/09/2026 (a carta precisa
        # declarar a origem) e o `ator_id` em 05/09/2026 (o aluno de um envio
        # da sala de aula só viaja no envelope). Estes dublês não os usam.
        ao_pagamento_aprovado(data)  # o registro acontece de verdade...
        raise RuntimeError("conexão caiu depois do INSERT")  # ...e então falha

    with patch("apps.eventos.handlers.enviar_notificacao"):
        with pytest.raises(RuntimeError):
            processar_envelope(envelope, handler_que_falha_depois_de_registrar)

    # (a) o efeito do handler foi desfeito
    assert EnvioRegistrado.objects.count() == 0
    # (b) o registro de dedup foi desfeito junto — é isto que o bug quebrava
    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 0

    # (c) o ponto todo: a MESMA entrega, de novo, é processada normalmente
    with patch("apps.eventos.handlers.enviar_notificacao") as mock_enviar:
        assert processar_envelope(envelope, ao_pagamento_aprovado) is True

    assert (
        EnvioRegistrado.objects.filter(order_id="order-1", tipo="boas_vindas").count()
        == 1
    )
    assert mock_enviar.call_count == 1
    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 1


def test_integrityerror_do_handler_nao_e_confundido_com_evento_ja_processado():
    """A armadilha da correção óbvia: com o handler dentro do `try`, um
    IntegrityError vindo DELE cairia no `except IntegrityError: return False` e o
    evento sumiria em silêncio — com xack, sem sobrar nada na PEL. A colisão aqui
    é real: uniq_envio_por_order_tipo_canal, a mesma que `get_or_create()` disputa
    sob corrida."""
    EnvioRegistrado.objects.create(
        event="pagamento.aprovado",
        site_id="site-abc",
        order_id="order-1",
        tipo="boas_vindas",
        canal="email",
        destinatario="cliente@example.com",
        corpo="ja existia",
    )
    envelope = _envelope()

    def handler_que_colide_em_outra_constraint(
        data: dict, event_id: str | None = None, ator_id: str | None = None
    ) -> None:
        # A assinatura ganhou o `event_id` em 02/09/2026 (a carta precisa
        # declarar a origem) e o `ator_id` em 05/09/2026 (o aluno de um envio
        # da sala de aula só viaja no envelope). Estes dublês não os usam.
        EnvioRegistrado.objects.create(
            event="pagamento.aprovado",
            site_id=data["site_id"],
            order_id=data["order_id"],
            tipo="boas_vindas",
            canal="email",
            destinatario=data["customer"]["email"],
            corpo="colide",
        )

    with pytest.raises(IntegrityError):
        processar_envelope(envelope, handler_que_colide_em_outra_constraint)

    assert EventoProcessado.objects.filter(event_id=envelope["event_id"]).count() == 0
