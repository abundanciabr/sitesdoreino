# apps/eventos/tasks.py  # [RECEITA:R8 v1]
import logging

from config.huey import huey

from .models import EnvioRegistrado

logger = logging.getLogger("mensageria.provedores")


def enviar_email(destinatario: str, assunto: str, corpo: str) -> None:
    """Stub: loga o envio. Provedor SMTP real fica para depois."""
    logger.info("EMAIL -> %s | %s\n%s", destinatario, assunto, corpo)


def enviar_whatsapp(destinatario: str, corpo: str) -> None:
    """Stub: loga o envio. Provedor WhatsApp real fica para depois."""
    logger.info("WHATSAPP -> %s | %s", destinatario, corpo)


PROVEDORES = {"email": enviar_email, "whatsapp": enviar_whatsapp}


def processar_envio(envio_id: int) -> None:
    """Corpo nu da task — chamado direto pelo teste-guarda, sem passar pelo Huey."""
    envio = EnvioRegistrado.objects.get(id=envio_id)
    if envio.status == "enviado":
        return  # idempotência extra: reentrega da própria task
    try:
        if envio.canal == "email":
            enviar_email(envio.destinatario, envio.assunto, envio.corpo)
        else:
            enviar_whatsapp(envio.destinatario, envio.corpo)
    except Exception as exc:  # provedor fora do ar
        envio.tentativas += 1
        envio.resultado = str(exc)[:500]
        envio.save(update_fields=["tentativas", "resultado"])
        raise  # o Huey decide o retry; nunca propaga a quem emitiu o evento
    envio.status = "enviado"
    envio.tentativas += 1
    envio.resultado = "ok"
    envio.save(update_fields=["status", "tentativas", "resultado"])


@huey.task(retries=5, retry_delay=30)
def enviar_notificacao(envio_id: int) -> None:
    """Toda task é idempotente — retry é comportamento normal, não exceção."""
    processar_envio(envio_id)
