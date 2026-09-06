# apps/eventos/management/commands/consume_eventos.py  # [RECEITA:R4 v1]
import json
import logging
import os
from datetime import datetime, timezone

import redis
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from apps.eventos.handlers import (
    ao_aula_concluida,
    ao_checkpoint_devolvido,
    ao_envio_recebido,
    ao_pagamento_aprovado,
    ao_pagamento_recusado,
    ao_pessoa_cadastrada,
    ao_pix_expirado,
)
from apps.eventos.models import EventoProcessado

log = logging.getLogger(__name__)

GRUPO = "mensageria"  # nome DESTA célula
CONSUMIDOR = "worker-1"
STREAMS = {
    "eventos.pagamento.aprovado": ao_pagamento_aprovado,
    "eventos.pix.expirado": ao_pix_expirado,
    "eventos.pagamento.recusado": ao_pagamento_recusado,
    # Desde 02/09/2026: o cadastro é o gatilho da primeira sequência de verdade
    # (boas-vindas). O nome do stream é `eventos.<evento>`, SEM versão — a versão
    # viaja no envelope, e pôr `v1` aqui faria a célula escutar um stream que
    # ninguém escreve, em silêncio.
    "eventos.identidade.pessoa-cadastrada": ao_pessoa_cadastrada,
    # Desde 05/09/2026: a sala de aula (célula `cursos`). O envio recebido
    # guarda de quem é o checkpoint e cancela o silêncio; o devolvido dispara a
    # jornada do silêncio de 14 e 30 dias (degrau 2.4). Os dois entram pelo
    # MESMO consumidor e pelo mesmo grupo: nada muda no compose.
    "eventos.envio.recebido": ao_envio_recebido,
    "eventos.checkpoint.devolvido": ao_checkpoint_devolvido,
    # Desde 06/09/2026: a mesma sala de aula, agora pelo marco. A aula concluída
    # que FECHA UM BLOCO convida o aluno para a Prancheta (degrau 17 do
    # portfólio); a aula comum não convida ninguém, e é `ao_aula_concluida` que
    # separa as duas. Mesmo consumidor, mesmo grupo: nada muda no compose.
    "eventos.aula.concluida": ao_aula_concluida,
}

# Convenção do LOTE — as 4 células consumidoras usam OS MESMOS nomes e valores
# (não renomear nem "ajustar" só aqui):
IDLE_MS_REENTREGA = 60_000  # pendente sem ack há >= isto ⇒ reivindicável
MAX_ENTREGAS = 5  # entregas já feitas ⇒ fila morta, sem reprocessar


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
        # O `event_id` chega ao handler desde 02/09/2026. Era limitação
        # conhecida desta célula (LICOES.md), e virou impedimento: a carta de um
        # passo de sequência exige `origem_event_id` no contrato, e sem ele o
        # despachante — fail-closed — nunca publicaria nada.
        #
        # O `ator_id` chega desde 05/09/2026, pelo mesmo motivo de forma: em
        # `envio.recebido.v1` o aluno viaja SÓ no `ator_id` do envelope, e o
        # handler que guarda de quem é o envio não tinha como lê-lo. `.get`,
        # porque nem todo contrato desta célula o declara.
        handler(envelope["data"], envelope["event_id"], envelope.get("ator_id"))
        return True


def _processar_e_ack(r, stream, handler, msg_id, campos) -> None:
    """Caminho ÚNICO de processamento — mensagem nova e mensagem reivindicada
    passam pelos MESMOS passos (convenção do lote). Os dois desfechos de
    processar_envelope levam a ack: o handler rodou, ou o evento já tinha sido
    processado de verdade. Se ele ESTOURAR, o ack não acontece e a mensagem
    fica na PEL — de onde `_reivindicar_presas` a recupera na volta."""
    envelope = json.loads(campos[b"json"])
    processar_envelope(envelope, handler)
    r.xack(stream, GRUPO, msg_id)


def _entregas_ja_feitas(r, stream, msg_id) -> int:
    """Quantas entregas esta mensagem JÁ recebeu ANTES da reivindicação atual.

    O delivery_count é lido do PEL DEPOIS do XAUTOCLAIM — e reivindicar soma 1
    ao contador — então o `- 1` desfaz esse incremento. Ex.: o PEL mostrava 5
    entregas feitas, o claim levou a 6; aqui devolve 5, que é o número que a
    regra da fila morta compara ("delivery_count do PEL já em MAX_ENTREGAS")."""
    pendencia = r.xpending_range(stream, GRUPO, min=msg_id, max=msg_id, count=1)
    if not pendencia:
        # Saiu do PEL entre o claim e a leitura (ack concorrente). Processar de
        # novo é seguro: o dedup por event_id absorve; ack repetido é inócuo.
        return 0
    return int(pendencia[0]["times_delivered"]) - 1


def _mover_para_fila_morta(r, stream, msg_id, campos, entregas) -> None:
    """Mensagem que esgotou MAX_ENTREGAS não roda o handler de novo: vai para
    `<stream>.dlq` com o payload original + motivo/delivery_count/movida_em,
    e sai do stream original via ack. O log ERROR é o alarme — nada mais no
    caminho automático olha a fila morta por enquanto."""
    try:
        event_id = str(json.loads(campos[b"json"])["event_id"])
    except (KeyError, ValueError, TypeError):
        event_id = "<event_id ilegivel>"
    r.xadd(
        f"{stream}.dlq",
        {
            **campos,  # payload original, intacto
            b"motivo": "max_entregas_esgotadas",
            b"delivery_count": str(entregas),
            b"movida_em": datetime.now(timezone.utc).isoformat(),
        },
    )
    r.xack(stream, GRUPO, msg_id)
    log.error(
        "FILA MORTA: event_id=%s esgotou %d entregas (MAX_ENTREGAS=%d) e foi "
        "movido de %s para %s.dlq (msg_id=%s): intervencao manual necessaria",
        event_id,
        entregas,
        MAX_ENTREGAS,
        stream,
        stream,
        msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
    )


def _reivindicar_presas(r, stream, handler) -> None:
    """Reentrega das presas (ARMADILHAS §9): quando o handler estoura, o ack
    não acontece e a mensagem fica no PEL do grupo — e `xreadgroup ">"` só
    entrega mensagem NOVA, então ela ficava pendente PARA SEMPRE. A cada
    iteração do loop, antes de ler novas, o XAUTOCLAIM transfere para este
    consumidor tudo que está parado há >= IDLE_MS_REENTREGA e reprocessa pelo
    MESMO caminho das novas. Quem já esgotou MAX_ENTREGAS vai para a fila
    morta em vez de rodar de novo.

    Se o reprocesso estourar de novo, a exceção propaga igual à do caminho
    novo (processo cai, supervisor reinicia) — a mensagem segue na PEL com o
    delivery_count somado pelo claim, e converge para a fila morta.
    """
    cursor = "0-0"
    while True:
        resultado = r.xautoclaim(
            stream,
            GRUPO,
            CONSUMIDOR,
            min_idle_time=IDLE_MS_REENTREGA,
            start_id=cursor,
            count=10,
        )
        cursor, mensagens = resultado[0], resultado[1]
        for msg_id, campos in mensagens:
            if campos is None:
                continue  # entrada já apagada do stream (Redis <7 devolve nil)
            entregas = _entregas_ja_feitas(r, stream, msg_id)
            if entregas >= MAX_ENTREGAS:
                _mover_para_fila_morta(r, stream, msg_id, campos, entregas)
                continue
            _processar_e_ack(r, stream, handler, msg_id, campos)
        if cursor in (b"0-0", "0-0"):
            break  # o XAUTOCLAIM sempre avança o cursor; 0-0 = varredura completa


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
            # Convenção do lote: reivindicar as presas ANTES de ler as novas —
            # tudo dentro do MESMO loop, sem thread nem processo extra.
            for stream, handler in STREAMS.items():
                _reivindicar_presas(r, stream, handler)
            resp = r.xreadgroup(
                GRUPO, CONSUMIDOR, {s: ">" for s in STREAMS}, count=10, block=5000
            )
            for stream_bruto, msgs in resp or []:
                handler = STREAMS[stream_bruto.decode()]
                for msg_id, campos in msgs:
                    _processar_e_ack(r, stream_bruto, handler, msg_id, campos)
