# apps/eventos/tasks.py  # [RECEITA:R8 v1]
"""O envio de verdade — e o dia em que esta célula parou de fingir.

**O fato cru que este arquivo apaga:** até 02/09/2026, `enviar_email` dizia, na
própria docstring, *"Stub: loga o envio"*. Ela escrevia a mensagem num arquivo de
log e voltava sem erro — e `processar_envio` marcava a linha como `enviado`.
**Nenhum e-mail jamais saiu desta plataforma, e o registro de auditoria afirmava
o contrário.** Era falso-verde no lugar mais caro: o único lugar capaz de
responder *"nós mandamos?"* respondia "sim" para todos.

O TRANSPORTE É SMTP, E ISSO É DECISÃO, NÃO PREGUIÇA
----------------------------------------------------
O mantenedor escolheu o Brevo como provedor. O que entra aqui é SMTP, e não a
API HTTP dele: SMTP é o denominador comum de todo provedor sério, então trocar de
fornecedor um dia vira mudança de env em vez de um PR reescrevendo o cliente. A
escolha dele mora no arquivo de env da VPS, que é onde ela pertence.

FALHA TEM QUE ESTOURAR, E AGORA HÁ TRÊS JEITOS DE FALHAR
---------------------------------------------------------
A `LICOES.md` desta célula já explicava por que uma exceção engolida aqui seria
pior que o erro: é a exceção escapando que faz o `@huey.task(retries=5)` saber
que precisa reagendar. Uma task que "termina com sucesso" tendo falhado nunca
mais tenta.

O que muda é que agora há três causas distintas, e nomeá-las é o que faz um
incidente durar minutos em vez de horas:

- **`EmailNaoConfigurado`** — o passo do mantenedor ainda não foi feito. Não é
  defeito de código, e não adianta reprocessar: adianta configurar.
- **`EnvioRecusado`** — o provedor aceitou a conversa e não aceitou a carta.
- **`SMTPException`** e parentes — provedor fora do ar, ou credencial inválida.
  Aí sim retentar faz sentido.

**"Sem exceção" NÃO É PROVA DE ENTREGA** (`armadilhas/028`, na sua forma SMTP).
`send_mail` devolve QUANTAS mensagens saíram, e devolver `0` sem levantar é um
desfecho real do backend do Django. Ler esse número é o que impede esta função de
recriar, com transporte de verdade, exatamente a mentira que ela veio apagar.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail

from config.huey import huey

from .models import EnvioRegistrado

logger = logging.getLogger("mensageria.provedores")


class EmailNaoConfigurado(RuntimeError):
    """Não há provedor de e-mail neste ambiente — e isso não é defeito de código.

    Classe própria porque a AÇÃO que ela pede é diferente de todas as outras:
    nenhuma quantidade de retentativa a resolve, e quem a vir num log precisa
    saber que o conserto é o passo do mantenedor (conta no provedor, domínio
    remetente, registros de DNS), não um deploy.

    Ela LEVANTA em vez de voltar em silêncio de propósito. O silêncio é
    exatamente o que esta célula fazia antes, e o preço era o registro de
    auditoria afirmar que a carta saiu.
    """


class EnvioRecusado(RuntimeError):
    """O provedor conversou e não aceitou a carta: zero mensagens saíram."""


def enviar_email(destinatario: str, assunto: str, corpo: str) -> None:
    """Manda o e-mail de verdade. Volta em silêncio SÓ quando ele saiu.

    Sem `fail_silently`, e o nome do parâmetro do Django explica o porquê melhor
    que qualquer comentário: com ele ligado, um provedor fora do ar vira `None` e
    a linha é marcada como enviada.
    """
    if not (settings.EMAIL_HOST and settings.DEFAULT_FROM_EMAIL):
        raise EmailNaoConfigurado(
            "SMTP_HOST/SMTP_FROM ausentes no env desta celula — o passo do "
            "mantenedor (conta no provedor, dominio remetente e os registros de "
            "DNS) ainda nao foi feito. Nenhum e-mail sai, e nenhuma linha e "
            "marcada como enviada."
        )

    quantos = send_mail(
        subject=assunto,
        message=corpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[destinatario],
        fail_silently=False,
    )
    if quantos != 1:
        # `armadilhas/028` na forma SMTP: ausência de exceção não é prova. O
        # backend do Django devolve a CONTAGEM, e `0` sem levantar é desfecho
        # real — sem esta linha, ele viraria "enviado" no registro.
        raise EnvioRecusado(
            f"o provedor aceitou a conexao e nao aceitou a carta: {quantos} "
            f"mensagem(ns) enviada(s), esperava 1"
        )


def enviar_whatsapp(destinatario: str, corpo: str) -> None:
    """Stub: loga o envio. WhatsApp oficial é o degrau 10 do plano das jornadas.

    Continua fingindo, e o `despacho` das jornadas SABE disso: ele recusa o canal
    `whatsapp` levantando `CanalNaoSuportado`, então nenhuma jornada consegue
    marcar como entregue algo que este stub não entregou. O caminho transacional
    antigo ainda o chama, e essa dívida fica declarada aqui em vez de escondida.
    """
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
        # `status` NÃO vira "enviado" aqui, e é o ponto inteiro deste arquivo: a
        # linha fica como está e o Huey reagenda.
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
