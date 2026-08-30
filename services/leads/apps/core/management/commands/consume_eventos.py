# apps/core/management/commands/consume_eventos.py  # [RECEITA:R4 v1 + reentrega]
import json
import logging
import os
from datetime import datetime, timezone

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

log = logging.getLogger("leads.consume_eventos")

GRUPO = "leads"  # nome DESTA célula
CONSUMIDOR = "worker-1"

# Convenção do LOTE de reentrega (mesmos nomes e valores nas 4 células
# consumidoras — alunos, checkout, leads, mensageria; não invente variação):
IDLE_MS_REENTREGA = 60_000  # presa há >= 60s na PEL ⇒ é reivindicada e reprocessada
MAX_ENTREGAS = 5  # delivery_count do PEL já em 5 ⇒ fila morta, sem reprocessar

STREAMS = {
    "eventos.quiz.completado": ao_quiz_completado,
    "eventos.pedido.criado": ao_pedido_criado,
    "eventos.pagamento.aprovado": ao_pagamento_aprovado,
    "eventos.pagamento.recusado": ao_pagamento_recusado,
    "eventos.pix.expirado": ao_pix_expirado,
}


def garantir_grupos(r: redis.Redis) -> None:
    for stream in STREAMS:
        try:
            r.xgroup_create(stream, GRUPO, id="0", mkstream=True)
        except redis.ResponseError:
            pass  # grupo já existe


def processar_mensagem(r: redis.Redis, stream, handler, msg_id, campos) -> None:
    """O caminho ÚNICO de processamento: mensagens novas e reivindicadas passam
    por aqui. Exceção do handler propaga DE PROPÓSITO — a transação de
    processar_envelope() desfaz o efeito, o xack abaixo não roda e a mensagem
    fica na PEL do grupo, onde reivindicar_presas() a recupera na próxima
    iteração (ou na próxima vida do processo, se a exceção o derrubar)."""
    envelope = json.loads(campos[b"json"])
    processar_envelope(envelope, handler)
    r.xack(stream, GRUPO, msg_id)


def _mover_para_fila_morta(r: redis.Redis, stream: str, msg_id, entregas: int) -> None:
    """Mensagem que esgotou MAX_ENTREGAS não é reprocessada: vai para
    <stream>.dlq com o payload original + motivo/delivery_count/movida_em, e é
    ACKada no stream de origem para sair da PEL de vez. O log ERROR abaixo é o
    alarme — a fila morta só serve se alguém souber que ela encheu."""
    conteudo = r.xrange(stream, min=msg_id, max=msg_id)
    campos = dict(conteudo[0][1]) if conteudo else {}
    try:
        event_id = json.loads(campos[b"json"])["event_id"]
    except (KeyError, ValueError):
        event_id = "desconhecido"
    campos[b"motivo"] = (
        f"handler falhou em {entregas} entregas (MAX_ENTREGAS={MAX_ENTREGAS})"
    )
    campos[b"delivery_count"] = str(entregas)
    campos[b"movida_em"] = datetime.now(timezone.utc).isoformat()
    r.xadd(f"{stream}.dlq", campos)
    r.xack(stream, GRUPO, msg_id)
    log.error(
        "FILA MORTA: evento %s esgotou %s entregas e foi movido para %s.dlq "
        "(msg_id=%s): precisa de intervenção manual",
        event_id,
        entregas,
        stream,
        msg_id,
    )


def reivindicar_presas(r: redis.Redis, stream: str, handler) -> None:
    """Reentrega de mensagens presas na PEL do grupo. Sem isto, um evento cujo
    handler estourou fica pendente PARA SEMPRE: xreadgroup(..., ">") só entrega
    mensagem nova (ARMADILHAS-OPERACAO.md §9). Roda ANTES do xreadgroup, a cada iteração.

    A ordem importa: a fila morta vem PRIMEIRO, lendo o delivery_count direto
    do PEL (XPENDING), porque o XAUTOCLAIM incrementa o contador ao reivindicar
    — checar depois dele contaria a reivindicação atual como uma entrega."""
    for pendente in r.xpending_range(
        stream, GRUPO, min="-", max="+", count=100, idle=IDLE_MS_REENTREGA
    ):
        if pendente["times_delivered"] >= MAX_ENTREGAS:
            _mover_para_fila_morta(
                r, stream, pendente["message_id"], pendente["times_delivered"]
            )
    inicio = "0-0"
    while True:
        resultado = r.xautoclaim(
            stream,
            GRUPO,
            CONSUMIDOR,
            min_idle_time=IDLE_MS_REENTREGA,
            start_id=inicio,
            count=10,
        )
        inicio, mensagens = resultado[0], resultado[1]
        for msg_id, campos in mensagens:
            processar_mensagem(r, stream, handler, msg_id, campos)
        if inicio in (b"0-0", "0-0"):
            break


def uma_iteracao(r: redis.Redis, block_ms: int = 5000) -> None:
    """Uma volta do loop do consumer: primeiro a reentrega das presas, depois
    as mensagens novas — as duas pelo MESMO processar_mensagem()."""
    for stream, handler in STREAMS.items():
        reivindicar_presas(r, stream, handler)
    resp = r.xreadgroup(
        GRUPO, CONSUMIDOR, {s: ">" for s in STREAMS}, count=10, block=block_ms
    )
    for stream, msgs in resp or []:
        handler = STREAMS[stream.decode()]
        for msg_id, campos in msgs:
            processar_mensagem(r, stream, handler, msg_id, campos)


class Command(BaseCommand):
    help = "Consumer dos eventos da plataforma que alimentam a timeline de leads"

    def handle(self, *args, **opts):
        r = redis.from_url(os.environ["REDIS_STREAMS_URL"])
        garantir_grupos(r)
        while True:
            uma_iteracao(r)
