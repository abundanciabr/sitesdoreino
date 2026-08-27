# apps/eventos/management/commands/consume_eventos.py  # [RECEITA:R4 v1]
import json
import logging
import os
from datetime import datetime, timezone

import redis
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from apps.eventos.models import EventoProcessado
from apps.notificacoes.handlers import ao_notificacao_devida

logger = logging.getLogger(__name__)

GRUPO = "notificacoes"  # nome DESTA célula
CONSUMIDOR = "worker-1"
STREAMS = ["eventos.notificacao.devida"]
HANDLERS = {"notificacao.devida": ao_notificacao_devida}

# Convenção do lote de reentrega — MESMOS nomes e valores nas 4 células
# consumidoras (alunos, checkout, leads, mensageria). Guarda:
# tests/test_reentrega_pel.py::test_constantes_do_lote_nao_derivam.
IDLE_MS_REENTREGA = 60_000  # presa = pendente sem ACK há pelo menos isto
MAX_ENTREGAS = 5  # contagem do PEL em que a mensagem vai para a fila morta
LOTE_REENTREGA = 10  # quantas presas olhar por iteração (mesmo teto do xreadgroup)


def processar_envelope(envelope: dict, handlers: dict) -> None:
    """Dedup por event_id: evento reentregue não dispara o handler de novo.
    handlers mapeia envelope["event"] -> callable(data, *, ator_id). A assinatura
    tem um argumento a mais que a receita R4 v1 — ver o comentário no ponto de
    chamada, que explica por quê e o que aconteceria sem ele.

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
        # ADAPTAÇÃO DESTA CÉLULA À RECEITA R4 v1, declarada em vez de silenciosa:
        # o handler recebe também o `ator_id`, que mora no ENVELOPE e não no
        # `data`. Foi o Rito de Contrato de 26/08/2026 que o pôs lá, e de
        # propósito — assim qualquer célula lê "quem fez isto" sem conhecer o
        # formato do assunto. Um handler que só recebesse `data` teria de
        # aceitar que essa informação não existe, ou obrigaria o `ator_id` a
        # descer para dentro de cada assunto, que é o desenho que o rito
        # recusou.
        #
        # `.get()` e não `[...]`: o contrato declara `ator_id` NULÁVEL (fato de
        # máquina não tem gente), e um envelope sem a chave é um envelope de
        # outro evento — que este consumidor nunca vê, porque assina um stream
        # só. Estourar aqui trocaria "não havia ator" por "a célula caiu".
        handlers[envelope["event"]](envelope["data"], ator_id=envelope.get("ator_id"))


def _mover_para_fila_morta(
    r: "redis.Redis", stream: str, msg_id: bytes, delivery_count: int
) -> None:
    """Esgotou MAX_ENTREGAS: preserva a mensagem em <stream>.dlq e tira do PEL.

    O handler NÃO roda. XADD na fila morta ANTES do XACK, de propósito: se o
    processo morrer entre os dois, a mensagem continua presa e o próximo ciclo
    a move de novo — duplicata na .dlq é melhor que mensagem perdida.

    O ERROR abaixo é o alarme possível hoje; alerta de verdade é dívida
    registrada (§9), não deste despacho.
    """
    entradas = r.xrange(stream, min=msg_id, max=msg_id)
    campos = dict(entradas[0][1]) if entradas else {}
    try:
        event_id = json.loads(campos[b"json"])["event_id"]
    except (KeyError, ValueError):
        # Payload ilegível ou mensagem apagada do stream — vai para a .dlq do
        # mesmo jeito: o motivo de o handler estourar pode ser exatamente este.
        event_id = "desconhecido"
    r.xadd(
        f"{stream}.dlq",
        {
            **campos,
            "motivo": f"esgotou MAX_ENTREGAS={MAX_ENTREGAS} sem ACK",
            "delivery_count": str(delivery_count),
            "movida_em": datetime.now(timezone.utc).isoformat(),
        },
    )
    r.xack(stream, GRUPO, msg_id)
    msg_id_txt = msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
    logger.error(
        "FILA MORTA: evento %s (stream=%s, msg_id=%s, delivery_count=%s) movido "
        "para %s.dlq — o handler NAO rodou; investigar e reprocessar manualmente.",
        event_id,
        stream,
        msg_id_txt,
        delivery_count,
        stream,
    )


def reentregar_presas(r: "redis.Redis", stream: str, handlers: dict) -> None:
    """A peça que faltava (ARMADILHAS-OPERACAO.md §9): `xreadgroup(">")` só entrega
    mensagem NOVA — quem estourava o handler ficava em XPENDING para sempre.
    Roda a cada iteração do loop, ANTES da leitura de mensagens novas:

    1) quem já chegou a MAX_ENTREGAS no PEL vai para a fila morta, sem rodar o
       handler (XPENDING traz a contagem; XAUTOCLAIM não traz — daí as duas
       chamadas);
    2) o resto preso há IDLE_MS_REENTREGA+ é reivindicado (XAUTOCLAIM) e
       reprocessado pelo MESMO caminho das mensagens novas — idempotência
       segura pós-#43: registro e efeito na mesma transação.

    Se o reprocesso estourar de novo, a exceção propaga como no caminho normal
    (o processo morre e o supervisor o traz de volta); a mensagem segue no PEL
    com delivery_count incrementado pelo próprio XAUTOCLAIM — o teto de
    MAX_ENTREGAS é o que impede o ciclo de ser eterno.
    """
    presas = r.xpending_range(
        stream, GRUPO, min="-", max="+", count=LOTE_REENTREGA, idle=IDLE_MS_REENTREGA
    )
    for presa in presas:
        if presa["times_delivered"] >= MAX_ENTREGAS:
            _mover_para_fila_morta(
                r, stream, presa["message_id"], presa["times_delivered"]
            )
    # As movidas para a .dlq acima já foram ACKadas — o XAUTOCLAIM não as vê.
    resultado = r.xautoclaim(
        stream, GRUPO, CONSUMIDOR, min_idle_time=IDLE_MS_REENTREGA, count=LOTE_REENTREGA
    )
    for msg_id, campos in resultado[1]:
        envelope = json.loads(campos[b"json"])
        processar_envelope(envelope, handlers)
        r.xack(stream, GRUPO, msg_id)


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
            for stream in STREAMS:
                reentregar_presas(r, stream, HANDLERS)
            resp = r.xreadgroup(
                GRUPO, CONSUMIDOR, {s: ">" for s in STREAMS}, count=10, block=5000
            )
            for stream, msgs in resp or []:
                for msg_id, campos in msgs:
                    envelope = json.loads(campos[b"json"])
                    processar_envelope(envelope, HANDLERS)
                    r.xack(stream, GRUPO, msg_id)
