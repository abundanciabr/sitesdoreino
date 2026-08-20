# apps/eventos/management/commands/consume_eventos.py  # [RECEITA:R4 v1]
import json
import os

import redis
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from apps.eventos.models import EventoProcessado
from apps.matriculas.handlers import ao_pagamento_aprovado

GRUPO = "alunos"  # nome DESTA célula
STREAMS = ["eventos.pagamento.aprovado"]
HANDLERS = {"pagamento.aprovado": ao_pagamento_aprovado}


def processar_envelope(envelope: dict, handlers: dict) -> None:
    """Dedup por event_id: evento reentregue não dispara o handler de novo.
    handlers mapeia envelope["event"] (ex.: "pagamento.aprovado") -> callable(data).

    O create() precisa do próprio savepoint (transaction.atomic() aninhado): sem
    ele, o IntegrityError do event_id duplicado marca a transação inteira como
    quebrada e qualquer query seguinte (inclusive de outro teste) estoura
    TransactionManagementError em vez de simplesmente ser ignorada."""
    try:
        with transaction.atomic():
            EventoProcessado.objects.create(event_id=envelope["event_id"])
    except IntegrityError:
        return
    handlers[envelope["event"]](envelope["data"])


class Command(BaseCommand):
    help = "Consumer de eventos da célula (roda como processo supervisionado)"

    def handle(self, *args, **opts):
        r = redis.from_url(os.environ["REDIS_STREAMS_URL"])
        for stream in STREAMS:
            try:
                r.xgroup_create(stream, GRUPO, id="0", mkstream=True)
            except redis.ResponseError:
                pass  # grupo já existe
        while True:
            resp = r.xreadgroup(
                GRUPO, "worker-1", {s: ">" for s in STREAMS}, count=10, block=5000
            )
            for stream, msgs in resp or []:
                for msg_id, campos in msgs:
                    envelope = json.loads(campos[b"json"])
                    processar_envelope(envelope, HANDLERS)
                    r.xack(stream, GRUPO, msg_id)
