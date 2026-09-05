# apps/cursos/tasks.py  # [RECEITA:R3 v1 + R8 v1]
"""O relay da outbox e o tique do prazo: os dois batimentos desta célula.

**O relay** (`relay_outbox`) espelha o de `pagamentos`, o que já roda em
produção há semanas, e os que nasceram dele (`quiz`, `checkout`, `sugestoes`).
Não é falta de imaginação: um relay diferente por célula significaria cinco
modos de falha diferentes para o mesmo problema. Molde:
`services/sugestoes/apps/sugestoes/tasks.py`, copiado e nunca importado (Lei 7).

**A ORDEM é intocável: publica no stream ANTES de marcar `published_at`.** Se o
processo morrer entre as duas escritas, o pior caso é REPUBLICAR, e o transporte
é at-least-once de propósito, com o consumidor deduplicando por `event_id`
(R4). A ordem inversa trocaria "republicar" por "perder evento em silêncio".

**Nome do stream: `eventos.<nome-do-evento>`, sem versão.** A versão viaja no
envelope. Pôr `v1` no nome do stream faria de toda evolução de contrato uma
migração de infraestrutura.

**O tique** (`bater_o_tique`) é o relógio da fila de revisão: de minuto em
minuto pergunta ao banco "que envio passou das 24 horas sem laudo?" e registra
o estouro. Molde: `services/encomendas/apps/encomendas/tasks.py`. Não existe
timer agendado por envio, e isso é a parte importante: um timer vive fora do
banco e some num deploy sem deixar rastro; a reavaliação periódica pergunta "o
que está vencido AGORA?", e por isso sobrevive a reinício, deploy e queda do
Redis. Toda a regra mora em `envio.registrar_estouros(agora)`, que é função de
(estado, `agora`) e não sabe o que é Huey; este arquivo só lê o relógio.

**Um worker, os dois batimentos.** O serviço auxiliar no compose (degrau 1.7,
`infra/`) é `python manage.py run_huey`, a entrada canônica e a única que faz
`django.setup()` + autodiscover deste módulo (`armadilhas/030`). Ele lê
`HUEY_REDIS_URL` (a fila) e `REDIS_STREAMS_URL` (o transporte dos eventos), as
mesmas duas variáveis das células irmãs, e as duas no PONTO DE USO
(`armadilhas/097`).
"""

import json
import logging
import os

import redis
from django.utils import timezone
from huey import crontab

from config.huey import huey

from . import envio as checkpoint
from .models import OutboxEvent

logger = logging.getLogger(__name__)

# Um lote por passada. Não é otimização: sem teto, uma outbox represada por
# Redis fora do ar viraria uma transação gigante na primeira volta.
LOTE = 200


def relay_outbox() -> int:
    """Publica os pendentes em `eventos.<nome>` e marca `published_at`.

    Idempotente e segura de chamar a qualquer momento: linha com
    `published_at` preenchido é ignorada pelo filtro, então uma segunda passada
    não republica nada.

    `REDIS_STREAMS_URL` é lida **no ponto de uso**, nunca no import
    (`armadilhas/097`): o container web importa este módulo (via `eventos.py` e
    via o autodiscover do djhuey) e não pode morrer no boot se a variável
    faltar. Faltando, o `KeyError` estoura só aqui, é engolido pelo
    `relay_apos_commit` e o evento fica pendente, nunca perdido.
    """
    pendentes = list(
        OutboxEvent.objects.filter(published_at__isnull=True).order_by("id")[:LOTE]
    )
    if not pendentes:
        return 0
    cliente = redis.from_url(os.environ["REDIS_STREAMS_URL"])
    publicados = 0
    for evento in pendentes:
        envelope = {
            "event": evento.event,
            "version": evento.version,
            "event_id": str(evento.event_id),
            "occurred_at": evento.occurred_at.isoformat(),
            "data": evento.payload,
        }
        # As chaves que ESTE evento declara no nível de cima (o `ator_id`). Vêm
        # de quem emitiu, que é quem conhece o próprio contrato; o relay não
        # decide nada.
        #
        # O `if colisao` NÃO é zelo teatral: um `**extra` solto num dicionário
        # literal sobrescreve o que veio antes, então um `envelope_extra` com a
        # chave `event` ou `version` trocaria a IDENTIDADE do evento no fio, em
        # silêncio, e o consumidor errado o receberia. Aqui isso é ERROR e para
        # a publicação, nunca um evento com identidade trocada.
        colisao = set(evento.envelope_extra) & set(envelope)
        if colisao:
            raise ValueError(
                f"envelope_extra do evento {evento.event_id} tentou sobrescrever "
                f"{sorted(colisao)}: o nível de cima do envelope é do relay. "
                "Campo novo de contrato entra com nome próprio, nunca por cima."
            )
        envelope.update(evento.envelope_extra)
        cliente.xadd(
            f"eventos.{evento.event}",
            {"json": json.dumps(envelope, ensure_ascii=False)},
        )
        # Marcar SÓ depois do xadd: inverter a ordem trocaria "republicar no
        # pior caso" por "perder evento no pior caso".
        evento.published_at = timezone.now()
        evento.save(update_fields=["published_at"])
        publicados += 1
    return publicados


def relay_apos_commit() -> None:
    """Registrada com `transaction.on_commit` por `eventos.emitir`.

    É o que dá latência sub-segundo sem furar a outbox: o publish acontece
    DEPOIS do commit, então nunca há evento no fio para um fato que não
    aconteceu.

    Falha aqui (Redis fora do ar, variável ausente) **nunca** perde o evento
    nem quebra a página do aluno: ele segue na outbox com `published_at=None`,
    e a task periódica abaixo republica. Por isso o `except` largo: é defensivo
    por desenho, não descuido.
    """
    try:
        relay_outbox()
    except Exception:  # noqa: BLE001 - defensivo por design, ver docstring
        logger.exception("relay_outbox falhou apos commit; evento fica pendente")


@huey.periodic_task(crontab(minute="*"))
def relay_outbox_periodico() -> int:
    """[RECEITA:R3 v1] A rede de segurança: a cada minuto, o worker republica."""
    return relay_outbox()


def bater_o_tique() -> tuple[int, ...]:
    """Uma passada do relógio da fila de revisão. O gesto inteiro, sem Huey.

    Separada da task de propósito: é esta função que o teste chama e que um
    comando de plantão poderia chamar à mão. `agora` é lido UMA vez, aqui, e
    desce por argumento: dois envios vencidos na mesma passada recebem o mesmo
    `estourado_em`, e o registro continua função de (estado, `agora`).
    """
    return checkpoint.registrar_estouros(timezone.now())


@huey.periodic_task(crontab(minute="*"))
def tique_periodico() -> tuple[int, ...]:
    """De minuto em minuto, para sempre. Um agendamento, que não conhece envio
    nenhum: pergunta ao banco o que está vencido."""
    return bater_o_tique()
