# apps/core/management/commands/consume_eventos.py  # [RECEITA:R4 v1]
import json
import os

import redis
from django.core.management.base import BaseCommand

from apps.core.handlers import (
    ao_pagamento_aprovado,
    ao_pagamento_recusado,
    ao_pedido_criado,
    ao_pix_expirado,
    ao_quiz_completado,
    processar_envelope,
)

GRUPO = "leads"  # nome DESTA célula
STREAMS = {
    "eventos.quiz.completado": ao_quiz_completado,
    "eventos.pedido.criado": ao_pedido_criado,
    "eventos.pagamento.aprovado": ao_pagamento_aprovado,
    "eventos.pagamento.recusado": ao_pagamento_recusado,
    "eventos.pix.expirado": ao_pix_expirado,
}


class Command(BaseCommand):
    help = "Consumer dos eventos da plataforma que alimentam a timeline de leads"

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
                    processar_envelope(envelope, handler)
                    r.xack(stream, GRUPO, msg_id)
