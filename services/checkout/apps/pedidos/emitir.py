# [RECEITA:R3 v1]
from .models import OutboxEvent


def emitir(event: str, data: dict, *, version: int = 1) -> OutboxEvent:
    """[INV-P6] Chame SEMPRE dentro da MESMA transaction.atomic() da mudança de estado."""
    return OutboxEvent.objects.create(event=event, version=version, payload=data)
