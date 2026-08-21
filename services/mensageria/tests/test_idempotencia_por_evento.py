# [RECEITA:R5 v1] reentrega do mesmo evento ⇒ 1 envio (constituicoes/AGENTS.mensageria.md)
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction

from apps.eventos.handlers import ao_pagamento_aprovado
from apps.eventos.models import EnvioRegistrado, EventoProcessado

pytestmark = pytest.mark.django_db(transaction=True)

DATA_PAGAMENTO_APROVADO = {
    "site_id": "site-abc",
    "payment_id": "pay-1",
    "order_id": "order-1",
    "amount_cents": 1000,
    "method": "pix",
    "mp_payment_id": "mp-1",
    "customer": {"email": "cliente@example.com", "name": "Cliente Um"},
}


def test_event_id_repetido_estoura_integridade():
    """A camada mais externa (consume_eventos): reentrega do stream nunca chega ao handler."""
    event_id = uuid4()
    EventoProcessado.objects.create(event_id=event_id, event="pagamento.aprovado")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EventoProcessado.objects.create(
                event_id=event_id, event="pagamento.aprovado"
            )


def test_handler_chamado_duas_vezes_gera_um_unico_envio():
    """Segunda camada, por chave de negócio: mesmo handler chamado 2x (ex.: task
    do Huey reprocessando) não duplica o envio nem chama o provedor duas vezes."""
    with patch("apps.eventos.handlers.enviar_notificacao") as mock_enviar:
        ao_pagamento_aprovado(DATA_PAGAMENTO_APROVADO)
        ao_pagamento_aprovado(DATA_PAGAMENTO_APROVADO)

    assert (
        EnvioRegistrado.objects.filter(order_id="order-1", tipo="boas_vindas").count()
        == 1
    )
    assert mock_enviar.call_count == 1


def test_handler_sem_telefone_nao_envia_whatsapp():
    with patch("apps.eventos.handlers.enviar_notificacao"):
        ao_pagamento_aprovado(DATA_PAGAMENTO_APROVADO)

    assert not EnvioRegistrado.objects.filter(
        order_id="order-1", canal="whatsapp"
    ).exists()
