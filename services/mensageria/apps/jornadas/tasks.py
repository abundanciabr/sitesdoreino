# apps/jornadas/tasks.py
"""O relay da outbox das jornadas: as cartas saem daqui para o Redis Streams.

Espelha o relay que já roda em produção na `identidade`, na `alunos` e antes
delas em `pagamentos`, `quiz` e `checkout`. Copiar o padrão é a lei; importar o
arquivo alheio seria furar a fronteira de célula.

**A ORDEM é intocável: publica no stream ANTES de marcar `published_at`.** Se o
processo morrer entre as duas escritas, o pior caso é REPUBLICAR — e o transporte
é at-least-once de propósito, com o consumidor deduplicando por `event_id`. A
ordem inversa trocaria "republicar" por "perder carta em silêncio".

**Nome do stream: `eventos.<nome-do-evento>`, sem versão.** A versão viaja no
envelope. Pôr `v1` no nome do stream faria de toda evolução de contrato uma
migração de infraestrutura.
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

# Um lote por passada. Não é otimização: sem teto, uma outbox represada por Redis
# fora do ar viraria uma transação gigante na primeira volta.
LOTE = 200


def relay_outbox() -> int:
    """Publica os pendentes em `eventos.<nome>` e marca `published_at`.

    Idempotente e segura de chamar a qualquer momento: linha com `published_at`
    preenchido é ignorada pelo filtro, então uma segunda passada não republica.

    `REDIS_STREAMS_URL` é lida **no ponto de uso**, nunca no import
    (`armadilhas/097`): o container web importa este módulo pelo autodiscover do
    djhuey e não pode morrer no boot se a variável faltar. Faltando, o `KeyError`
    estoura só aqui, é engolido pelo `relay_apos_commit` e a carta fica pendente
    — nunca perdida.
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
        # As chaves que ESTE evento declara no nível de cima — aqui o `ator_id`.
        # Vêm de quem emitiu, que é quem conhece o próprio contrato; o relay não
        # decide nada.
        #
        # O `if colisao` não é zelo teatral: um `**extra` solto sobrescreveria o
        # que veio antes, e um `envelope_extra` com a chave `event` ou `version`
        # trocaria a IDENTIDADE da carta no fio, em silêncio.
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
        # pior caso" por "perder carta no pior caso".
        evento.published_at = timezone.now()
        evento.save(update_fields=["published_at"])
        publicados += 1
    return publicados


def relay_apos_commit() -> None:
    """Registrada com `transaction.on_commit` no ponto de despacho.

    É o que dá latência sub-segundo sem furar a outbox: o publish acontece DEPOIS
    do commit, então nunca há carta no fio para uma entrega que não aconteceu.

    Falha aqui (Redis fora do ar, variável ausente) **nunca** perde a carta: ela
    segue na outbox com `published_at=None`, e a task periódica abaixo republica.
    Por isso o `except` largo — é defensivo por desenho, não descuido.
    """
    try:
        relay_outbox()
    except Exception:  # noqa: BLE001 - defensivo por design, ver docstring
        logger.exception("relay_outbox falhou apos commit; carta fica pendente")


@huey.periodic_task(crontab(minute="*"))
def relay_outbox_periodico() -> int:
    """A rede de segurança: a cada minuto, o worker republica o que ficou.

    O worker é `python manage.py run_huey` — entrada canônica, e a única que faz
    `django.setup()` + autodiscover de `tasks.py`. Subir o `huey_consumer` direto
    dá um worker de pé com o registro VAZIO, que não executa nada e não reclama
    (`armadilhas/030`).

    ATENÇÃO ao nome: esta célula JÁ TEM um `apps/eventos/tasks.py`, com a task de
    envio. Dois `tasks.py` na mesma célula é o esperado pelo autodiscover do
    djhuey (ele varre app por app) — o que NÃO se pode é os dois registrarem uma
    task com o mesmo nome, porque a segunda substituiria a primeira em silêncio.
    Aqui os nomes são distintos de propósito.
    """
    return relay_outbox()


@huey.periodic_task(crontab(minute="*/5"))
def varrer_jornadas() -> int:
    """A varredura periódica: é ela que faz o motor ANDAR em produção.

    Sem esta task, tudo o que a escada construiu fica parado: as inscrições
    existem, os passos têm hora marcada, e ninguém nunca passa para olhar. É o
    tipo de peça cuja ausência não dá erro nenhum — só silêncio.

    **De cinco em cinco minutos, e não a cada minuto.** O relógio das sequências
    é de DIAS; a régua fecha a janela às 20h e o teto é diário. Um passo que
    fica cinco minutos esperando não muda nada para o aluno, e a passada tem
    custo: ela lê inscrições, avalia condição e chama a régua. O `LOTE` do motor
    limita cada passada a 200.

    O import é DENTRO da função de propósito: `despacho` importa este módulo (ele
    precisa do `relay_apos_commit`), então importá-lo aqui em cima fecharia um
    ciclo no carregamento.
    """
    from . import despacho, motor

    passada = motor.varrer(despachar=despacho.despachar)
    if passada.examinadas:
        logger.info(
            "varredura: %s examinadas, %s entregues, %s barradas, %s puladas",
            passada.examinadas,
            passada.entregues,
            passada.barradas,
            passada.puladas,
        )
    return passada.entregues
