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

    São DUAS transações aninhadas. Parecem redundantes; não são — cada uma fecha
    um modo de falha diferente, e remover qualquer uma reabre um bug silencioso.
    Guarda das duas: tests/test_inv_p5_dedup_atomico.py.

    (1) A EXTERNA envolve o registro E o efeito, para que falhem juntos. Se o
        handler estourar (deadlock, conexão caída, timeout), o EventoProcessado
        é desfeito junto e a reentrega volta a funcionar. Com o create()
        commitando sozinho — como era antes —, um hiccup de 2s do Postgres no
        meio da matrícula deixava o evento marcado como visto: toda reentrega
        futura caía no `except IntegrityError` abaixo e era descartada em
        silêncio. O cliente pagou e nunca foi matriculado, sem nada no sistema
        para descobrir isso (não há reconciliação).

    (2) A INTERNA é savepoint SÓ em volta do create(), por dois motivos.
        Primeiro, ARMADILHAS.md §4.8: sem savepoint próprio, o IntegrityError
        do event_id duplicado marca a transação inteira como abortada e a query
        seguinte estoura TransactionManagementError em vez de o evento ser
        simplesmente ignorado. Segundo — e é por isso que o handler está FORA
        do try, não só fora do savepoint —, o `except` precisa enxergar
        exclusivamente o IntegrityError DESTE create. Com o handler dentro do
        try, um IntegrityError vindo de dentro dele (qualquer constraint que
        nada tem a ver com event_id) seria lido como "já processado" e o evento
        seria descartado em silêncio: o mesmo bug de antes, só que mais difícil
        de enxergar.
    """
    with transaction.atomic():  # (1) registro e efeito: vivem ou morrem juntos
        try:
            with transaction.atomic():  # (2) savepoint: SÓ o create
                EventoProcessado.objects.create(event_id=envelope["event_id"])
        except IntegrityError:
            return  # já processado: nada foi gravado, o handler não roda de novo
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
