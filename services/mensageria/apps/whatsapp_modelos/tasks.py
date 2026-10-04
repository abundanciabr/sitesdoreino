"""Sincronização periódica dos modelos aprovados (só quando o canal oficial está ligado)."""
import logging

from huey import crontab

from config.huey import huey

from . import cloud
from .modelos import sincronizar_modelos

logger = logging.getLogger(__name__)


@huey.periodic_task(crontab(minute="17"))
def sincronizar_modelos_whatsapp() -> int:
    if not cloud.configurado():
        return 0
    try:
        return sincronizar_modelos()["modelos"]
    except (cloud.CloudRecusou, cloud.CloudSemResposta) as exc:
        logger.warning("sincronizacao de modelos do WhatsApp falhou: %s", exc)
        return 0
