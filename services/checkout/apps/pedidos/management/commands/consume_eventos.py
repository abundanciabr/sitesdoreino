# apps/pedidos/management/commands/consume_eventos.py  # [RECEITA:R4 v1] adaptado
# Consome pagamento.aprovado/pagamento.recusado/pix.expirado e move o status do
# pedido (INV-P7 — o front só lê esse status via GET /pedidos/{id}).
#
# Dedup: o receituário R4 canônico usa uma tabela EventoProcessado (unicidade
# por event_id) como camada de idempotência ANTES do handler. Aqui o handler é
# idempotente por construção — Order.status só sai de "aguardando_pagamento"
# uma vez, via UPDATE condicional (WHERE status=aguardando_pagamento) — então
# reentrega (at-least-once) ou eventos fora de ordem são no-op sem tabela
# extra. Decisão registrada em LICOES.md desta célula.
import json
import os

import redis
from django.core.management.base import BaseCommand

from apps.pedidos.models import Order as OrderModel

GRUPO = "checkout"


def _transicionar(*, order_id: str, site_id: str, status: str) -> int:
    return OrderModel.objects.filter(
        pk=order_id, site_id=site_id, status=OrderModel.AGUARDANDO
    ).update(status=status)


def ao_pagamento_aprovado(data: dict) -> None:
    _transicionar(order_id=data["order_id"], site_id=data["site_id"], status="pago")


def ao_pagamento_recusado(data: dict) -> None:
    _transicionar(order_id=data["order_id"], site_id=data["site_id"], status="recusado")


def ao_pix_expirado(data: dict) -> None:
    _transicionar(order_id=data["order_id"], site_id=data["site_id"], status="expirado")


STREAMS = {
    "eventos.pagamento.aprovado": ao_pagamento_aprovado,
    "eventos.pagamento.recusado": ao_pagamento_recusado,
    "eventos.pix.expirado": ao_pix_expirado,
}


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
                handler = STREAMS[stream.decode()]
                for msg_id, campos in msgs:
                    envelope = json.loads(campos[b"json"])
                    handler(envelope["data"])
                    r.xack(stream, GRUPO, msg_id)
