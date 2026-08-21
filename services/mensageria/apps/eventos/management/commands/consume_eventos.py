# apps/eventos/management/commands/consume_eventos.py  # [RECEITA:R4 v1]
import json
import os

import redis
from django.core.management.base import BaseCommand
from django.db import IntegrityError

from apps.eventos.handlers import (
    ao_pagamento_aprovado,
    ao_pagamento_recusado,
    ao_pix_expirado,
)
from apps.eventos.models import EventoProcessado

GRUPO = "mensageria"  # nome DESTA célula
STREAMS = {
    "eventos.pagamento.aprovado": ao_pagamento_aprovado,
    "eventos.pix.expirado": ao_pix_expirado,
    "eventos.pagamento.recusado": ao_pagamento_recusado,
}


class Command(BaseCommand):
    help = "Consumer de eventos da mensageria (roda como processo supervisionado)"

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
                handler = STREAMS[stream.decode()]
                for msg_id, campos in msgs:
                    envelope = json.loads(campos[b"json"])
                    try:
                        EventoProcessado.objects.create(
                            event_id=envelope["event_id"], event=envelope["event"]
                        )
                    except IntegrityError:  # já processado — idempotência por event_id
                        r.xack(stream, GRUPO, msg_id)
                        continue
                    handler(envelope["data"])
                    r.xack(stream, GRUPO, msg_id)
