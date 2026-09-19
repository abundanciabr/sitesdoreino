"""Os dois batimentos de fundo desta casa: a varredura dos links e o relay.

A VARREDURA QUE DESCOBRE QUE UM LINK PAROU DE ABRIR (critério AC-09)
--------------------------------------------------------------------

O mantenedor escolheu o link colado sabendo o preço (plano §6.2): link de aluno
quebra, e quando quebra o portfólio dele fica com um buraco que a escola não
consegue consertar. Este arquivo é a metade da mitigação que a tela não cobre:
a peça foi conferida no dia em que foi colada, e é UM MÊS DEPOIS que o Drive
some, a pasta vira privada ou o domínio morre. Ninguém está olhando naquela
hora, então a escola olha sozinha.

**O QUE ELA FAZ, E O QUE ELA NUNCA FAZ.** Ela MARCA e DESMARCA: quem parou de
abrir vira `quebrado`, com a data; quem voltou a abrir vira `respondendo` de
novo, e a data da quebra some junto. **Ela nunca apaga peça** (critério AC-09).
Apagar a obra de um aluno por causa de uma medição de rede é a falha que não
tem volta, e é por isso que existe um teste só para isso, provado por mutação.

**POR QUE AQUI ELA CONTA TIMEOUT COMO NÃO ABRIU, e a tela do aluno não.** São
situações diferentes e por isso a decisão é diferente, de propósito. Na tela há
um aluno esperando, e recusar a obra dele por causa de uma tosse da nossa rede
seria acusá-lo de um problema que pode ser nosso. Aqui não há ninguém
esperando, a marca é reversível na varredura seguinte, e o endereço cujo
domínio morreu de vez nunca mais devolve status nenhum: se a varredura também
esperasse por um status, ela ficaria cega justamente para o caso que o plano
pediu para vigiar.

**POR QUE ESTA VARREDURA NÃO PASSA PELO `do_aluno`.** O isolamento do critério
AC-07 é a porta de quem lê PARA um aluno, e esta varredura não responde a
ninguém: ela é a escola olhando os próprios links, sem tela, sem sessão e sem
destinatário. Não há resposta em que uma peça de um aluno pudesse aparecer para
outro. A porta continua obrigatória em tudo que serve requisição de gente, e
`tests/test_isolamento_por_aluno.py` continua sendo quem prova isso.

**ELA RODA EM PROCESSO PRÓPRIO, NUNCA DENTRO DO ASGI** (`armadilhas/170`, e a
razão está escrita em `config/settings.py`): sob ASGI, reaproveitar conexão de
banco vaza uma conexão por requisição, e nem a suíte, nem o `/healthz`, nem o
deploy acusam. O processo é `python manage.py run_huey`, síncrono.
"""

from __future__ import annotations

import json
import logging
import os

import redis
from django.db import transaction
from django.utils import timezone
from huey import crontab

from config.huey import huey

from . import conferencia_do_link
from .models import EstadoDoLink, OutboxEvent, Peca

logger = logging.getLogger("pages.tasks")


def reconferir_os_links() -> dict[str, int]:
    """Uma passada por todas as peças da escola. O gesto inteiro, sem Huey.

    Separada da task de propósito, pelo mesmo motivo da célula `encomendas`: é
    esta função que o teste chama e que um plantão futuro poderia chamar à mão.
    A task abaixo só a agenda.

    **`agora` é lido UMA VEZ e desce por argumento.** Se cada peça lesse o
    próprio relógio, duas peças da mesma passada teriam datas de quebra
    separadas por segundos, e a tela do aluno mostraria como se tivessem
    quebrado em momentos diferentes.

    **Uma peça que estoura não derruba as outras.** Uma obra torta não pode
    parar a vigilância da escola inteira.

    **A lista de quem conferir é lida INTEIRA antes do laço, e são só os
    números.** Um `iterator()` aqui abriria um cursor no servidor e o manteria
    aberto durante minutos de conversa com sites de terceiros, dentro de uma
    transação que o Django precisa segurar para o cursor existir. Aí cada
    `atomic()` de dentro deixaria de ser transação e viraria um savepoint da de
    fora: uma peça que estourasse abortaria a transação inteira, e a consulta
    seguinte morreria com `TransactionManagementError` (`armadilhas/027`) em vez
    de a varredura continuar. Nada disso apareceria na suíte, porque o
    `pytest-django` já roda cada teste dentro de uma transação e faz o mesmo
    savepoint nos dois casos. Uma lista de números inteiros de todas as peças
    da escola cabe na memória com folga.
    """
    agora = timezone.now()
    placar = {"conferidas": 0, "quebradas": 0, "voltaram": 0}

    for numero in list(Peca.objects.order_by("pk").values_list("pk", flat=True)):
        peca = Peca.objects.filter(pk=numero).first()
        # Sumiu entre a lista e agora: o aluno tirou a peça da estante durante a
        # varredura. É o desfecho certo, e não um erro para registrar.
        if peca is None:
            continue
        try:
            with transaction.atomic():
                mudou = _anotar(peca, conferencia_do_link.conferir(peca.link), agora)
        except Exception:  # noqa: BLE001 - uma peça torta não para as outras
            logger.exception("a reconferência da peça %s falhou", peca.pk)
            continue
        placar["conferidas"] += 1
        if mudou:
            placar[mudou] += 1

    logger.info(
        "reconferência de links: %s conferidas, %s quebraram, %s voltaram",
        placar["conferidas"],
        placar["quebradas"],
        placar["voltaram"],
    )
    return placar


def _anotar(peca: Peca, veredito, agora) -> str | None:
    """Grava o que a batida achou nesta peça. Devolve o que MUDOU, ou `None`.

    `quebrado_desde` só é escrito na TRANSIÇÃO para quebrado: reescrevê-lo a
    cada varredura apagaria a única resposta que ele existe para dar, que é
    "desde quando".
    """
    estava_quebrada = peca.estado_do_link == EstadoDoLink.QUEBRADO
    peca.conferido_em = agora

    if veredito.abriu:
        peca.estado_do_link = EstadoDoLink.RESPONDENDO
        peca.quebrado_desde = None
        peca.save(
            update_fields=[
                "estado_do_link",
                "conferido_em",
                "quebrado_desde",
                "atualizada_em",
            ]
        )
        return "voltaram" if estava_quebrada else None

    peca.estado_do_link = EstadoDoLink.QUEBRADO
    if not estava_quebrada:
        peca.quebrado_desde = agora
    peca.save(
        update_fields=[
            "estado_do_link",
            "conferido_em",
            "quebrado_desde",
            "atualizada_em",
        ]
    )
    return None if estava_quebrada else "quebradas"


# Uma vez por dia, às 4h20 da manhã em São Paulo (7h20 em UTC, que é o relógio
# do servidor). Diária, e não de hora em hora, por duas razões que puxam para o
# mesmo lado: um link que quebrou hoje de manhã não fica melhor por ser
# descoberto três horas antes, e cada passada é uma batida na porta de sites de
# terceiros que não pediram para ser visitados. De madrugada porque é quando o
# aluno não está com a Prancheta aberta.
@huey.periodic_task(crontab(hour="7", minute="20"))
def reconferencia_diaria() -> dict[str, int]:
    """O único agendamento desta célula. O worker é `manage.py run_huey`."""
    return reconferir_os_links()


# ---------------------------------------------------------------------------
# O RELAY DA OUTBOX (degrau 12, critério AC-12): o segundo batimento da casa
# ---------------------------------------------------------------------------
# Molde: `services/cursos/apps/cursos/tasks.py`, copiado e nunca importado
# (Lei 3). Não é falta de imaginação: um relay diferente por célula significa
# um modo de falha diferente por célula para o mesmo problema.
#
# **A ORDEM é intocável: publica no fio ANTES de marcar `published_at`.** Se o
# processo morrer entre as duas escritas, o pior caso é REPUBLICAR, e o
# transporte é at-least-once de propósito, com o consumidor deduplicando por
# `event_id` (é o que o contrato do selo promete). A ordem inversa trocaria
# "republicar" por "perder evento em silêncio".
#
# **Nome do fio: `eventos.<nome-do-evento>`, sem versão.** A versão viaja no
# envelope. Pôr `v1` no nome faria de toda evolução de contrato uma migração de
# infraestrutura.

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
    djhuey e não pode morrer no boot se a variável faltar, que é exatamente o
    estado da VPS hoje (`infra/env/pages.env.exemplo` diz, com todas as letras,
    que quem a entrega é o serviço do relay no compose). Faltando, o `KeyError`
    estoura só aqui, é engolido pelo `relay_apos_commit` e o evento fica
    PENDENTE na outbox, nunca perdido.
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
        # As chaves que ESTE evento declara no nível de cima (o `ator_id`). Vêm
        # de quem emitiu, que é quem conhece o próprio contrato; o relay não
        # decide nada.
        #
        # O `if colisao` não é zelo teatral: um `**extra` solto sobrescreve o
        # que veio antes, então um `envelope_extra` com a chave `event` ou
        # `version` trocaria a IDENTIDADE do evento no fio, em silêncio, e o
        # consumidor errado o receberia. Aqui isso para a publicação.
        colisao = set(evento.envelope_extra) & set(envelope)
        if colisao:
            raise ValueError(
                f"envelope_extra do evento {evento.event_id} tentou sobrescrever "
                f"{sorted(colisao)}: o nível de cima do envelope é do relay. "
                "Campo novo de contrato entra com nome próprio, nunca por cima."
            )
        envelope.update(evento.envelope_extra)
        cliente.xadd(
            f"eventos.{evento.event}",
            {"json": json.dumps(envelope, ensure_ascii=False)},
        )
        # Marcar SÓ depois do `xadd`: inverter a ordem trocaria "republicar no
        # pior caso" por "perder evento no pior caso".
        evento.published_at = timezone.now()
        evento.save(update_fields=["published_at"])
        publicados += 1
    return publicados


def relay_apos_commit() -> None:
    """Registrada com `transaction.on_commit` por quem emite.

    É o que dá latência sub-segundo sem furar a outbox: o publish acontece
    DEPOIS do commit, então nunca há evento no fio para um fato que não
    aconteceu.

    Falha aqui (Redis fora do ar, variável ausente) **nunca** perde o evento nem
    quebra a tela da equipe: o fato segue na outbox com `published_at=None`, e a
    task periódica abaixo republica. Por isso o `except` largo, que é defensivo
    por desenho e não descuido.
    """
    try:
        relay_outbox()
    except Exception:  # noqa: BLE001 - defensivo por design, ver docstring
        logger.exception("relay_outbox falhou apos commit; evento fica pendente")


@huey.periodic_task(crontab(minute="*"))
def relay_outbox_periodico() -> int:
    """[RECEITA:R3 v1] A rede de segurança: a cada minuto, o worker republica."""
    return relay_outbox()
