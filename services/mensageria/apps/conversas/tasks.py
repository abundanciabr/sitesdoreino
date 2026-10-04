"""Retomada periódica do que depende de outra célula."""
from huey import crontab

from config.huey import huey


@huey.periodic_task(crontab(minute="*/15"))
def conversas_retomar_descadastros() -> int:
    """Grava nas jornadas a preferência dos descadastros que ficaram pendentes."""
    from .descadastro import aplicar_pendentes

    return aplicar_pendentes()
