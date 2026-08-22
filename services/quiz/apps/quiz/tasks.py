# apps/quiz/tasks.py  # [RECEITA:R3 v1]
"""Relay da outbox: publica `quiz.completado.v1` no Redis Streams.

Espelha o desenho de pagamentos (`pagamentos/core/models.py`), provado em
produção. A ORDEM importa e é intocável: publica no stream ANTES de marcar
`published_at`. Se o publish falhar, o evento continua pendente e será
republicado (nunca perdido); se marcar falhar depois do publish, o pior caso
é uma republicação — e o consumidor deduplica por `event_id` (R4). A ordem
inversa (marcar antes) perderia evento em silêncio — é o irmão produtor do
bug consumidor descrito em ARMADILHAS §4.12.
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


def relay_outbox() -> int:
    """Publica os pendentes em `eventos.<nome>` e marca `published_at`.

    Idempotente e segura de chamar a qualquer momento (evento com
    `published_at` preenchido é ignorado pelo filtro). REDIS_STREAMS_URL é
    lida no PONTO DE USO (ARMADILHAS §5.3): nada fail-hard no import — o web
    importa este módulo (via views e via djhuey) e não pode morrer no boot
    se a variável faltar; faltando, o KeyError estoura só aqui, é engolido
    pelo `relay_apos_commit` e o evento fica pendente, nunca perdido.
    """
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
        evento.published_at = timezone.now()
        evento.save(update_fields=["published_at"])
        publicados += 1
    return publicados


def relay_apos_commit() -> None:
    """Registrada via `transaction.on_commit` no ponto de emissão. Uma falha
    aqui (Redis fora do ar, variável ausente) NUNCA perde o evento nem quebra
    a resposta ao lead: ele já está persistido na outbox com
    `published_at=None`, e a task periódica abaixo o republica."""
    try:
        relay_outbox()
    except Exception:  # noqa: BLE001 - defensivo por design, ver docstring
        logger.exception("relay_outbox falhou apos commit; evento fica pendente")


@huey.periodic_task(crontab(minute="*"))
def relay_outbox_periodico() -> int:
    """[RECEITA:R3 v1] Rede de segurança: a cada minuto, o worker
    (`python manage.py run_huey`) republica o que o caminho on_commit deixou
    pendente. É o que garante entrega mesmo que o web caia entre o commit e o
    publish."""
    return relay_outbox()
