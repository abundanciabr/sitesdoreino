# apps/pedidos/tasks.py  # [RECEITA:R3 v1 + R8 v1]
# Relay do outbox: publica os eventos pendentes (`pedido.criado`) em
# `eventos.<nome>` no Redis Streams. Espelha o relay de `pagamentos` (provado
# em produção): publica no stream ANTES de marcar `published_at` — se o
# processo morrer entre as duas escritas, o pior caso é REPUBLICAR (o
# transporte é at-least-once de propósito e os consumidores dedupam), nunca
# perder o evento (ARMADILHAS §4.12: o lado produtor íntegro é este).
import json
import logging
import os

import redis
from django.utils import timezone
from huey import crontab

from config.huey import huey

from .models import OutboxEvent

logger = logging.getLogger(__name__)


def relay_outbox() -> int:
    """Publica os pendentes e marca `published_at`. Idempotente: linha com
    `published_at` preenchido é ignorada, então chamar de novo é sempre
    seguro. A conexão abre no ponto de uso — nada de fail-hard no import
    (§5.3): sem REDIS_STREAMS_URL só o relay falha; o web sobe normal."""
    pendentes = list(
        OutboxEvent.objects.filter(published_at__isnull=True).order_by("id")[:200]
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
        cliente.xadd(
            f"eventos.{evento.event}",
            {"json": json.dumps(envelope, ensure_ascii=False)},
        )
        # Marcar SÓ depois do xadd — inverter a ordem trocaria "republicar no
        # pior caso" por "perder evento no pior caso" (§4.12).
        evento.published_at = timezone.now()
        evento.save(update_fields=["published_at"])
        publicados += 1
    return publicados


def relay_apos_commit() -> None:
    """Callback do `transaction.on_commit` no ponto de emissão (latência
    sub-segundo). Falha aqui NUNCA perde o evento: ele segue na outbox com
    `published_at=None` e a task periódica abaixo republica."""
    try:
        relay_outbox()
    except Exception:  # noqa: BLE001 - defensivo por design, ver docstring
        logger.exception("relay_outbox falhou apos commit; evento fica pendente")


@huey.periodic_task(crontab(minute="*"))
def relay_outbox_periodico() -> int:
    """Rede de segurança (R3): a cada minuto republica o que o on_commit não
    conseguiu publicar (Redis fora do ar na hora, processo morto etc.)."""
    return relay_outbox()
