"""Consumidor dos eventos que acionam a equipe comercial de agentes.

Mesma receita das outras células (`services/leads/.../consume_eventos.py`):
grupo próprio, reentrega do que ficou preso na PEL e fila morta depois de
`MAX_ENTREGAS`. Uma diferença de propósito: o grupo nasce no FIM do stream
(`id="$"`). Eventos antigos não viram trabalho — abordar hoje quem respondeu
um quiz há meses seria mensagem fora de hora e gasto sem motivo.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

import redis
from django.core.management.base import BaseCommand

from apps.comercial.eventos import STREAMS, tratar

log = logging.getLogger("admin.comercial.consume_eventos")

GRUPO = "admin-comercial"
CONSUMIDOR = "worker-1"
IDLE_MS_REENTREGA = 60_000
MAX_ENTREGAS = 5


def garantir_grupos(r: redis.Redis) -> None:
    for stream in STREAMS:
        try:
            r.xgroup_create(stream, GRUPO, id="$", mkstream=True)
        except redis.ResponseError:
            pass  # grupo já existe


def processar_mensagem(r: redis.Redis, stream, msg_id, campos) -> None:
    nome = stream.decode() if isinstance(stream, bytes) else stream
    envelope = json.loads(campos[b"json"])
    tratar(nome, envelope)
    r.xack(nome, GRUPO, msg_id)


def _mover_para_fila_morta(r: redis.Redis, stream: str, msg_id, entregas: int) -> None:
    conteudo = r.xrange(stream, min=msg_id, max=msg_id)
    campos = dict(conteudo[0][1]) if conteudo else {}
    campos[b"motivo"] = f"comercial falhou em {entregas} entregas (MAX_ENTREGAS={MAX_ENTREGAS})"
    campos[b"delivery_count"] = str(entregas)
    campos[b"movida_em"] = datetime.now(timezone.utc).isoformat()
    campos[b"grupo"] = GRUPO
    r.xadd(f"{stream}.dlq", campos)
    r.xack(stream, GRUPO, msg_id)
    log.error("FILA MORTA (comercial): %s msg_id=%s movida para %s.dlq", stream, msg_id, stream)


def reivindicar_presas(r: redis.Redis, stream: str) -> None:
    for pendente in r.xpending_range(stream, GRUPO, min="-", max="+", count=100, idle=IDLE_MS_REENTREGA):
        if pendente["times_delivered"] >= MAX_ENTREGAS:
            _mover_para_fila_morta(r, stream, pendente["message_id"], pendente["times_delivered"])
    inicio = "0-0"
    while True:
        resultado = r.xautoclaim(stream, GRUPO, CONSUMIDOR, min_idle_time=IDLE_MS_REENTREGA,
                                 start_id=inicio, count=10)
        inicio, mensagens = resultado[0], resultado[1]
        for msg_id, campos in mensagens:
            processar_mensagem(r, stream, msg_id, campos)
        if inicio in (b"0-0", "0-0"):
            break


def uma_iteracao(r: redis.Redis, block_ms: int = 5000) -> None:
    for stream in STREAMS:
        reivindicar_presas(r, stream)
    resposta = r.xreadgroup(GRUPO, CONSUMIDOR, {s: ">" for s in STREAMS}, count=10, block=block_ms)
    for stream, mensagens in resposta or []:
        for msg_id, campos in mensagens:
            processar_mensagem(r, stream, msg_id, campos)


class Command(BaseCommand):
    help = "Consumidor dos eventos que acionam a equipe comercial de agentes"

    def handle(self, *args, **opts):
        url = (os.environ.get("REDIS_STREAMS_URL") or "").strip()
        if not url:
            log.warning("comercial: REDIS_STREAMS_URL ausente; o consumidor espera")
            while True:
                time.sleep(300)
        r = redis.from_url(url)
        garantir_grupos(r)
        while True:
            uma_iteracao(r)
