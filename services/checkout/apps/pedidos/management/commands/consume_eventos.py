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
#
# Reentrega do PEL (ARMADILHAS §9): mensagem cujo handler estourou ficava em
# XPENDING do grupo para sempre — xreadgroup ">" só entrega mensagem NOVA, e
# ninguém chamava XAUTOCLAIM. Agora, a cada iteração do loop e ANTES do ">",
# reivindicamos as presas (idle >= IDLE_MS_REENTREGA) e as reprocessamos pelo
# MESMO caminho do handler das novas. Quem chega à MAX_ENTREGAS-ésima entrega
# NÃO é reprocessado: vai para a fila morta `<stream>.dlq` (payload original +
# motivo/delivery_count/movida_em), é ACKado no stream original e deixa um log
# ERROR com o event_id. Desenho e nomes são convenção do lote — as 4 células
# consumidoras implementam exatamente isto.
import json
import logging
import os
from datetime import datetime, timezone

import redis
from django.core.management.base import BaseCommand

from apps.pedidos.models import Order as OrderModel

logger = logging.getLogger(__name__)

GRUPO = "checkout"
CONSUMIDOR = "worker-1"
IDLE_MS_REENTREGA = 60000  # presa = parada há >= 60 s no PEL do grupo
MAX_ENTREGAS = 5  # na 5ª entrega não se reprocessa: fila morta


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


def _processar(r, stream: str, msg_id, campos) -> None:
    """Caminho ÚNICO de processamento — mensagens novas e reivindicadas passam
    por aqui. Se o handler estourar, a mensagem fica no PEL (sem ACK) e a
    reentrega a reclama depois de IDLE_MS_REENTREGA."""
    handler = STREAMS[stream]
    envelope = json.loads(campos[b"json"])
    handler(envelope["data"])
    r.xack(stream, GRUPO, msg_id)


def _mover_para_fila_morta(r, stream: str, msg_id, campos, entregas: int) -> None:
    # Defensivo de propósito: uma mensagem cujo b"json" nem parseia é
    # exatamente o tipo de veneno que acaba aqui — a fila morta não pode
    # estourar no mesmo lugar em que o handler estourou.
    try:
        event_id = json.loads(campos[b"json"]).get("event_id", "desconhecido")
    except (ValueError, KeyError, AttributeError):
        event_id = "desconhecido"
    campos_dlq = dict(campos)  # payload original, intacto
    campos_dlq.update(
        {
            "motivo": "max_entregas_esgotado",
            "delivery_count": str(entregas),
            "movida_em": datetime.now(timezone.utc).isoformat(),
        }
    )
    # Publica na .dlq ANTES do ACK — pior caso duplica na fila morta, nunca
    # perde (mesmo princípio do relay do outbox, ARMADILHAS §4.12).
    r.xadd(f"{stream}.dlq", campos_dlq)
    r.xack(stream, GRUPO, msg_id)
    logger.error(
        "FILA MORTA: evento %s (stream %s, msg %s) esgotou %d entregas e foi "
        "movido para %s.dlq — investigue o payload antes de reinjetar.",
        event_id,
        stream,
        msg_id,
        entregas,
        stream,
    )


def reivindicar_e_reprocessar_presas(r) -> None:
    """Uma passada de reentrega, chamada a cada iteração do loop ANTES do
    xreadgroup ">". XAUTOCLAIM devolve as mensagens paradas há mais de
    IDLE_MS_REENTREGA no PEL do grupo (e incrementa o delivery_count delas);
    o delivery_count real vem do próprio PEL (XPENDING). Quem já está em
    MAX_ENTREGAS vai para a fila morta; o resto volta pelo MESMO caminho do
    handler das mensagens novas."""
    for stream in STREAMS:
        resultado = r.xautoclaim(
            stream, GRUPO, CONSUMIDOR, min_idle_time=IDLE_MS_REENTREGA
        )
        # resultado = [cursor, [(id, campos), ...], ids-deletados]; entradas já
        # removidas do stream podem vir com campos None — não há o que fazer
        # com elas além de ignorar (o próprio Redis as tira do PEL).
        reivindicadas = [(m, c) for m, c in resultado[1] if c is not None]
        if not reivindicadas:
            continue
        entregas_por_msg = {
            p["message_id"]: p["times_delivered"]
            for p in r.xpending_range(
                stream,
                GRUPO,
                min=reivindicadas[0][0],
                max=reivindicadas[-1][0],
                count=len(reivindicadas),
            )
        }
        for msg_id, campos in reivindicadas:
            entregas = entregas_por_msg.get(msg_id, 1)
            if entregas >= MAX_ENTREGAS:
                _mover_para_fila_morta(r, stream, msg_id, campos, entregas)
            else:
                _processar(r, stream, msg_id, campos)


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
            # ANTES das novas: sem isto, mensagem cujo handler estourou ficava
            # pendente para sempre (ARMADILHAS §9).
            reivindicar_e_reprocessar_presas(r)
            resp = r.xreadgroup(
                GRUPO, CONSUMIDOR, {s: ">" for s in STREAMS}, count=10, block=5000
            )
            for stream, msgs in resp or []:
                for msg_id, campos in msgs:
                    _processar(r, stream.decode(), msg_id, campos)
