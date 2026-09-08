import json
from collections.abc import Callable
from contextlib import nullcontext
from datetime import datetime
from typing import Any

import redis

CAMPOS_PROTEGIDOS = frozenset({"event", "version", "event_id", "occurred_at", "data"})


class EnvelopeProtegidoSobrescrito(ValueError):
    pass


def montar_envelope(evento: Any) -> dict[str, Any]:
    envelope = {
        "event": evento.event,
        "version": evento.version,
        "event_id": str(evento.event_id),
        "occurred_at": evento.occurred_at.isoformat(),
        "data": evento.payload,
    }
    extras = evento.envelope_extra or {}
    colisao = set(extras) & CAMPOS_PROTEGIDOS
    if colisao:
        raise EnvelopeProtegidoSobrescrito(
            f"envelope_extra do evento {evento.event_id} tentou sobrescrever "
            f"{sorted(colisao)}. O nivel de cima do envelope e do relay. "
            "Campo novo de contrato entra com nome proprio, nunca por cima."
        )
    envelope.update(extras)
    return envelope


def _transacao_do_modelo(consulta: Any):
    alias = getattr(consulta, "db", None)
    if not alias:
        return nullcontext()
    try:
        from django.db import transaction
    except ImportError:
        return nullcontext()
    return transaction.atomic(using=alias)


def _travar_pendentes_se_o_banco_permite(consulta: Any) -> Any:
    alias = getattr(consulta, "db", None)
    if not alias:
        return consulta
    try:
        from django.db import connections
    except ImportError:
        return consulta
    recursos = connections[alias].features
    if getattr(recursos, "has_select_for_update_skip_locked", False):
        return consulta.select_for_update(skip_locked=True)
    if getattr(recursos, "has_select_for_update", False):
        return consulta.select_for_update()
    return consulta


def publicar_pendentes(
    *,
    modelo: Any,
    redis_url: str,
    agora: Callable[[], datetime],
    lote: int,
) -> int:
    consulta = modelo.objects.filter(published_at__isnull=True).order_by("id")
    with _transacao_do_modelo(consulta):
        pendentes = list(_travar_pendentes_se_o_banco_permite(consulta)[:lote])
        if not pendentes:
            return 0

        cliente = redis.from_url(redis_url)
        publicados = 0
        for evento in pendentes:
            envelope = montar_envelope(evento)
            cliente.xadd(
                f"eventos.{evento.event}",
                {"json": json.dumps(envelope, ensure_ascii=False)},
            )
            evento.published_at = agora()
            evento.save(update_fields=["published_at"])
            publicados += 1
        return publicados
