# apps/forum/tasks.py
"""O relay da outbox: os fatos deste fórum saem daqui para o Redis Streams.

Espelha o relay que já roda em produção nas cinco células que o têm (o mais novo
é o da `gamificacao`, de hoje). Não é falta de imaginação: um relay diferente por
célula significaria N modos de falha diferentes para o mesmo problema — e o do
`checkout` já se perdeu uma vez por um despacho fundir arquivos para caber no
orçamento.

**A ORDEM é intocável: publica no stream ANTES de marcar `published_at`.** Se o
processo morrer entre as duas escritas, o pior caso é REPUBLICAR — e o transporte
é at-least-once de propósito, com o consumidor deduplicando por `event_id`. A
ordem inversa trocaria "republicar" por "perder evento em silêncio".

**Nome do stream: `eventos.<nome-do-evento>`, sem versão.** A versão viaja no
envelope. Pôr `v1` no nome do stream faria de toda evolução de contrato uma
migração de infraestrutura, e o `v1` continuaria sendo emitido até o último
consumidor migrar (RITOS §3) — dois streams para o mesmo fato.
"""

import json
import logging
import os

import redis
from django.utils import timezone
from huey import crontab

from config.huey import huey

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
    (`armadilhas/097`): o container web importa este módulo pelo autodiscover do
    djhuey e não pode morrer no boot se a variável faltar. Faltando, o
    `KeyError` estoura só aqui, é engolido pelo `relay_apos_commit` e a carta
    fica pendente — nunca perdida.
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
        # As chaves que ESTE evento declara no nível de cima — aqui o `ator_id`,
        # que os quatro contratos deste fórum exigem. Vem de quem emitiu, que é
        # quem conhece o próprio contrato; o relay não decide nada.
        #
        # O `if colisao` NÃO é zelo teatral: um `**extra` solto num dicionário
        # literal sobrescreve o que veio antes, então um `envelope_extra` com a
        # chave `event` ou `version` trocaria a IDENTIDADE do evento no fio, em
        # silêncio, e o consumidor errado o receberia. Aqui isso é erro e para a
        # publicação — nunca um evento com identidade trocada.
        colisao = set(evento.envelope_extra) & set(envelope)
        if colisao:
            raise ValueError(
                f"envelope_extra do evento {evento.event_id} tentou sobrescrever "
                f"{sorted(colisao)} — o nível de cima do envelope é do relay. "
                "Campo novo de contrato entra com nome próprio, nunca por cima."
            )
        envelope.update(evento.envelope_extra)
        cliente.xadd(
            f"eventos.{evento.event}",
            {"json": json.dumps(envelope, ensure_ascii=False)},
        )
        # Marcar SÓ depois do xadd — inverter a ordem trocaria "republicar no
        # pior caso" por "perder evento no pior caso".
        evento.published_at = timezone.now()
        evento.save(update_fields=["published_at"])
        publicados += 1
    return publicados


def relay_apos_commit() -> None:
    """Registrada com `transaction.on_commit` em cada ponto de emissão.

    É o que dá latência sub-segundo sem furar a outbox: o publish acontece
    DEPOIS do commit, então nunca há evento no fio para uma mensagem que
    não existe.

    Falha aqui (Redis fora do ar, variável ausente) **nunca** perde o evento nem
    impede a fala de um aluno: ela segue na outbox com `published_at=None`, e a
    task periódica abaixo republica. Por isso o `except` largo — é defensivo por
    desenho, não descuido. E a direção importa: um ponto a menos é recuperável;
    uma resposta que o aluno não conseguiu publicar porque o Redis caiu, não.
    """
    try:
        relay_outbox()
    except Exception:  # noqa: BLE001 - defensivo por design, ver docstring
        logger.exception("relay_outbox falhou apos commit; evento fica pendente")


@huey.periodic_task(crontab(minute="*"))
def relay_outbox_periodico() -> int:
    """A rede de segurança: a cada minuto, o worker republica o que ficou.

    O worker é `python manage.py run_huey` — entrada canônica, e a única que faz
    `django.setup()` + autodiscover de `tasks.py`. Subir o `huey_consumer`
    direto dá um worker de pé com o registro VAZIO, que não executa nada e não
    reclama (`armadilhas/030`). No compose ele é o serviço `forum-relay`.
    """
    return relay_outbox()
