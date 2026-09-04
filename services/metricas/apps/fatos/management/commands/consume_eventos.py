"""O consumidor de eventos da `metricas`  # [RECEITA:R4 v1, adaptada]

Roda como processo supervisionado, ao lado do container web, e é a única boca
de entrada do livro de fatos. O molde é o das cinco células consumidoras
(`alunos`, `checkout`, `leads`, `mensageria`, `gamificacao`), com as mesmas
constantes de reentrega — copiar o padrão é Lei 3, e divergir nos números
tornaria impossível comparar o comportamento de duas células em incidente.

## As três adaptações desta célula, declaradas em vez de silenciosas

**1. Não há tabela `EventoProcessado`.** Nas outras células ela existe porque o
efeito do evento (creditar XP, matricular) não deixa rastro do `event_id`; aqui
o efeito É gravar o evento, e `Evento.event_id` já é único. Uma segunda tabela
com a mesma chave seria o mesmo fato em dois lugares, e as duas poderiam
discordar.

**2. Não há mapa de handlers.** Tudo que chega com envelope bom é guardado.
Assunto novo entra sozinho no livro, sem PR nenhum — que é a diferença entre
um livro e um contador.

**3. Envelope inválido não estoura: vira EventoMorto e é ACKado.** Nas outras
células, um envelope quebrado explode o handler, a mensagem fica presa no PEL
e, cinco entregas depois, cai na fila morta do Redis, onde ninguém olha. Aqui
ela cai numa TABELA, que o painel mostra e sobre a qual há três ações
(inspecionar, tentar de novo, descartar com motivo). Reentregar um corpo
quebrado não o conserta; o que conserta é alguém ver.

## O que ele assina, e por que não assina mais

Os assuntos com contrato CONGELADO em `contracts/eventos/` que alguma célula
publica hoje. Assinar um stream que ninguém publica criaria um grupo de
consumo vazio e a impressão de que o caminho está pronto (a mesma razão pela
qual a `gamificacao` deixa `aula.concluida` de fora).

`matricula.situacao-alterada` é o assunto que esta célula mais quer, porque é
dele que sai "quem virou aluna". A `alunos` já o publica, mas ele **ainda não
tem contrato congelado** em `contracts/eventos/` — é a dívida que o degrau 8 do
plano existe para pagar. Ele entra aqui no mesmo PR do contrato, e não antes:
guardar como fato o que ninguém prometeu manter é construir número sobre areia.
"""

import json
import logging
import os
from datetime import datetime, timezone

import redis
from django.core.management.base import BaseCommand

from apps.fatos.recepcao import MORTO, receber

logger = logging.getLogger(__name__)

GRUPO = "metricas"  # nome DESTA célula
CONSUMIDOR = "worker-1"

#: Os assuntos com contrato congelado que alguém publica hoje.
STREAMS = [
    # Quem entrou no site (`identidade`, desde 31/08/2026).
    "eventos.identidade.pessoa-cadastrada",
    # A jornada de aprendizado (`quiz`).
    "eventos.quiz.completado",
    # A vida do fórum (`forum`, desde 30/08/2026).
    "eventos.forum.topico-criado",
    "eventos.forum.mensagem-criada",
    "eventos.forum.resposta-aceita",
    "eventos.forum.mensagem-removida",
    # A Caixa de Sugestões (`sugestoes`).
    "eventos.sugestao.criada",
    "eventos.sugestao.status-alterado",
    "eventos.sugestao.voto-adicionado",
    "eventos.sugestao.voto-removido",
]

# Convenção do lote de reentrega — MESMOS nomes e valores das outras células.
IDLE_MS_REENTREGA = 60_000  # presa = pendente sem ACK há pelo menos isto
MAX_ENTREGAS = 5  # contagem do PEL em que a mensagem vai para a fila morta
LOTE_REENTREGA = 10  # quantas presas olhar por iteração


def _corpo(campos: dict) -> bytes:
    """O texto cru da mensagem, sem supor que a chave existe."""
    return campos.get(b"json") or campos.get("json") or b""


def processar(cru: bytes) -> str:
    """Guarda o fato e devolve o desfecho, registrando o que merece log."""
    desfecho, objeto = receber(cru)
    if desfecho == MORTO:
        # ERROR e não WARNING: um evento que a plataforma afirmou e o livro não
        # pôde guardar é um buraco na contagem, e alguém precisa olhar.
        logger.error(
            "EVENTO MORTO (id=%s): %s. Inspecionar em /admin/, tentar de novo "
            "ou descartar com motivo.",
            getattr(objeto, "pk", "?"),
            getattr(objeto, "motivo", "?"),
        )
    return desfecho


def _mover_para_fila_morta(
    r: "redis.Redis", stream: str, msg_id: bytes, delivery_count: int
) -> None:
    """Esgotou MAX_ENTREGAS: preserva a mensagem em <stream>.dlq e tira do PEL.

    Nesta célula este caminho quase não deveria acontecer, porque `receber`
    não levanta — uma mensagem só chega aqui se o processo morreu no meio
    (banco fora do ar, contêiner reiniciado). XADD antes do XACK, de propósito:
    duplicata na `.dlq` é melhor que mensagem perdida.
    """
    entradas = r.xrange(stream, min=msg_id, max=msg_id)
    campos = dict(entradas[0][1]) if entradas else {}
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
    logger.error(
        "FILA MORTA DO REDIS: stream=%s msg_id=%s delivery_count=%s. O livro "
        "NAO guardou este fato; investigar e reprocessar manualmente.",
        stream,
        msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
        delivery_count,
    )


def reentregar_presas(r: "redis.Redis", stream: str) -> None:
    """`xreadgroup(">")` só entrega mensagem NOVA; o que ficou preso volta aqui."""
    presas = r.xpending_range(
        stream, GRUPO, min="-", max="+", count=LOTE_REENTREGA, idle=IDLE_MS_REENTREGA
    )
    for presa in presas:
        if presa["times_delivered"] >= MAX_ENTREGAS:
            _mover_para_fila_morta(
                r, stream, presa["message_id"], presa["times_delivered"]
            )
    resultado = r.xautoclaim(
        stream, GRUPO, CONSUMIDOR, min_idle_time=IDLE_MS_REENTREGA, count=LOTE_REENTREGA
    )
    for msg_id, campos in resultado[1]:
        processar(_corpo(dict(campos)))
        r.xack(stream, GRUPO, msg_id)


class Command(BaseCommand):
    help = "Recebe os eventos da plataforma e os guarda no livro de fatos"

    def handle(self, *args, **opts):
        r = redis.from_url(os.environ["REDIS_STREAMS_URL"])
        for stream in STREAMS:
            try:
                r.xgroup_create(stream, GRUPO, id="0", mkstream=True)
            except redis.ResponseError:
                pass  # grupo já existe
        while True:
            for stream in STREAMS:
                reentregar_presas(r, stream)
            resp = r.xreadgroup(
                GRUPO, CONSUMIDOR, {s: ">" for s in STREAMS}, count=10, block=5000
            )
            for stream, msgs in resp or []:
                for msg_id, campos in msgs:
                    processar(_corpo(dict(campos)))
                    r.xack(stream, GRUPO, msg_id)
