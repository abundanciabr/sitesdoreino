# apps/eventos/management/commands/consume_eventos.py  # [RECEITA:R4 v1]
import json
import os

import redis
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

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


def processar_envelope(envelope: dict, handler) -> bool:
    """Dedup por event_id. Devolve True se o handler rodou, False se o evento já
    tinha sido processado antes (dedup, não erro).

    Vive fora de `handle()` para ser testável sem Redis. Era exatamente a
    limitação registrada no LICOES.md desta célula — "o loop em si não tem teste
    próprio, a garantia está em duas camadas testáveis" — e o bug abaixo morava
    justamente na parte que nenhuma daquelas duas camadas alcançava.

    São DUAS transações aninhadas. Parecem redundantes; não são — cada uma fecha
    um modo de falha diferente. Guarda das duas:
    tests/test_inv_mensageria_evento_atomico.py.

    (1) A EXTERNA envolve o registro E o efeito, para que falhem juntos. Com o
        create() commitando sozinho — como era antes —, uma falha no meio do
        handler deixava o evento marcado como visto e a reentrega caía no
        `except IntegrityError` abaixo. Aqui isso era pior do que nas outras
        células: o caminho de dedup dá `xack` na mensagem, então a reentrega
        descartada era REMOVIDA do stream — não sobrava nada na PEL para
        recuperar depois. E `ao_pagamento_aprovado()` registra duas vezes
        (e-mail e WhatsApp, cada um na sua transação): bastava a segunda falhar
        para aquele WhatsApp nunca mais ser enviado, com o e-mail já entregue.

    (2) A INTERNA é savepoint SÓ em volta do create() — que antes não existia
        aqui de forma nenhuma (ARMADILHAS.md §4.8 na forma crua). Duas razões:
        sem ele, o IntegrityError do event_id duplicado marca a transação
        inteira como abortada; e o `except` precisa enxergar exclusivamente o
        IntegrityError DESTE create. Com o handler dentro do try, um
        IntegrityError vindo dele — a constraint uniq_envio_por_order_tipo_canal
        que `get_or_create()` disputa sob corrida, por exemplo — seria lido como
        "já processado": o mesmo bug, só que mais difícil de enxergar.

    Com esta estrutura o `xack` no dedup volta a ser seguro: `False` agora só
    acontece quando o efeito daquele evento realmente commitou alguma vez.
    """
    with transaction.atomic():  # (1) registro e efeito: vivem ou morrem juntos
        try:
            with transaction.atomic():  # (2) savepoint: SÓ o create
                EventoProcessado.objects.create(
                    event_id=envelope["event_id"], event=envelope["event"]
                )
        except IntegrityError:
            return False  # já processado: nada foi gravado, o handler não roda
        handler(envelope["data"])
        return True


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
                    # Os dois desfechos de processar_envelope levam a ack: o
                    # handler rodou, ou o evento já tinha sido processado de
                    # verdade. Se ele ESTOURAR, o ack não acontece e a mensagem
                    # fica na PEL para ser reentregue — é esse o ponto.
                    processar_envelope(envelope, handler)
                    r.xack(stream, GRUPO, msg_id)
