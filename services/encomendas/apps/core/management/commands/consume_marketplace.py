"""Consome fatos da Fila com reentrega do PEL e efeitos idempotentes."""
from __future__ import annotations

import json
import logging
import os

import redis
from django.core.management.base import BaseCommand
from django.utils import timezone
from outbox_relay import publicar_pendentes

from apps.core.eventos_marketplace import ASSUNTOS, processar
from apps.encomendas.models import OutboxMarketplace

logger = logging.getLogger(__name__)
GRUPO = "encomendas"
CONSUMIDOR = "worker-1"
STREAMS = [f"eventos.{evento}" for evento in (*ASSUNTOS, "marketplace.pagamento.aprovado")]
IDLE_MS_REENTREGA = 60_000
MAX_ENTREGAS = 5
LOTE_REENTREGA = 10


def _processar_mensagem(r, stream, msg_id, campos):
    envelope = json.loads(campos[b"json"])
    processar(envelope)
    r.xack(stream, GRUPO, msg_id)


def reentregar_presas(r, stream):
    presas = r.xpending_range(stream, GRUPO, min="-", max="+",
                             count=LOTE_REENTREGA, idle=IDLE_MS_REENTREGA)
    for presa in presas:
        if presa["times_delivered"] < MAX_ENTREGAS:
            continue
        msg_id = presa["message_id"]
        entradas = r.xrange(stream, min=msg_id, max=msg_id)
        campos = dict(entradas[0][1]) if entradas else {}
        r.xadd(f"{stream}.dlq", {
            **campos, "motivo": f"esgotou MAX_ENTREGAS={MAX_ENTREGAS} sem ACK",
            "delivery_count": str(presa["times_delivered"]),
            "movida_em": timezone.now().isoformat(),
        })
        r.xack(stream, GRUPO, msg_id)
        logger.error("Evento marketplace movido para %s.dlq: %s", stream, msg_id)
    resultado = r.xautoclaim(stream, GRUPO, CONSUMIDOR,
                            min_idle_time=IDLE_MS_REENTREGA, count=LOTE_REENTREGA)
    for msg_id, campos in resultado[1]:
        _processar_mensagem(r, stream, msg_id, campos)


class Command(BaseCommand):
    help = "Consome os eventos do marketplace e grava avisos internos"

    def handle(self, *args, **opts):
        r = redis.from_url(os.environ["REDIS_STREAMS_URL"])
        for stream in STREAMS:
            try:
                r.xgroup_create(stream, GRUPO, id="0", mkstream=True)
            except redis.ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise
        while True:
            publicar_pendentes(
                modelo=OutboxMarketplace, redis_url=os.environ["REDIS_STREAMS_URL"],
                agora=timezone.now, lote=100,
            )
            for stream in STREAMS:
                reentregar_presas(r, stream)
            for stream, mensagens in r.xreadgroup(
                GRUPO, CONSUMIDOR, {s: ">" for s in STREAMS}, count=10, block=5000,
            ) or []:
                for msg_id, campos in mensagens:
                    _processar_mensagem(r, stream, msg_id, campos)
