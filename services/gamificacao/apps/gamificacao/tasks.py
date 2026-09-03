# apps/gamificacao/tasks.py
"""O relay da outbox: as cartas de celebração saem daqui para o Redis Streams.

Espelha o relay que já roda em produção na `alunos` (e antes dela em
`sugestoes`, `pagamentos`, `quiz` e `checkout`). Não é falta de imaginação: um
relay diferente por célula significaria N modos de falha diferentes para o mesmo
problema — e o do `checkout` já se perdeu uma vez por um despacho fundir
arquivos para caber no orçamento.

**A ORDEM é intocável: publica no stream ANTES de marcar `published_at`.** Se o
processo morrer entre as duas escritas, o pior caso é REPUBLICAR — e o
transporte é at-least-once de propósito, com o consumidor deduplicando por
`event_id`. A ordem inversa trocaria "republicar" por "perder evento em
silêncio".

**Nome do stream: `eventos.<nome-do-evento>`, sem versão.** A versão viaja no
envelope. Pôr `v1` no nome do stream faria de toda evolução de contrato uma
migração de infraestrutura, e o `v1` continuaria sendo emitido até o último
consumidor migrar (RITOS §3) — dois streams para o mesmo fato.
"""

import json
import logging
import os

import redis
from django.utils import timezone
from huey import crontab

from config.huey import huey

from .models import LancamentoDeXP, OutboxEvent

logger = logging.getLogger(__name__)

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
    djhuey e não pode morrer no boot se a variável faltar. Faltando, o
    `KeyError` estoura só aqui, é engolido pelo `relay_apos_commit` e a carta
    fica pendente — nunca perdida.
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
        # As chaves que ESTE evento declara no nível de cima — aqui o `ator_id`,
        # que nas cartas desta célula é `None` de propósito (ninguém "concede"
        # um nível). Vêm de quem emitiu, que é quem conhece o próprio contrato;
        # o relay não decide nada.
        #
        # O `if colisao` NÃO é zelo teatral: um `**extra` solto num dicionário
        # literal sobrescreve o que veio antes, então um `envelope_extra` com a
        # chave `event` ou `version` trocaria a IDENTIDADE do evento no fio, em
        # silêncio, e o consumidor errado o receberia. Aqui isso é erro e para a
        # publicação — nunca um evento com identidade trocada.
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
        # pior caso" por "perder evento no pior caso".
        evento.published_at = timezone.now()
        evento.save(update_fields=["published_at"])
        publicados += 1
    return publicados


def relay_apos_commit() -> None:
    """Registrada com `transaction.on_commit` em cada ponto de emissão.

    É o que dá latência sub-segundo sem furar a outbox: o publish acontece
    DEPOIS do commit, então nunca há carta no fio para uma subida de nível que
    não aconteceu.

    Falha aqui (Redis fora do ar, variável ausente) **nunca** perde a carta nem
    impede o crédito de XP: ela segue na outbox com `published_at=None`, e a
    task periódica abaixo republica. Por isso o `except` largo — é defensivo por
    desenho, não descuido. E a direção importa: um aviso a menos é recuperável;
    um ponto que não foi creditado porque o sininho estava fora do ar, não.
    """
    try:
        relay_outbox()
    except Exception:  # noqa: BLE001 - defensivo por design, ver docstring
        logger.exception("relay_outbox falhou apos commit; carta fica pendente")


@huey.periodic_task(crontab(minute="*"))
def relay_outbox_periodico() -> int:
    """A rede de segurança: a cada minuto, o worker republica o que ficou.

    O worker é `python manage.py run_huey` — entrada canônica, e a única que faz
    `django.setup()` + autodiscover de `tasks.py`. Subir o `huey_consumer`
    direto dá um worker de pé com o registro VAZIO, que não executa nada e não
    reclama (`armadilhas/030`). No compose ele é o serviço `gamificacao-relay`.
    """
    return relay_outbox()


def liberar_quarentena() -> tuple[int, int]:
    """Torna definitivo o XP em quarentena que já passou da data.

    Mesma lógica que `management/commands/liberar_quarentena.py` chama à mão —
    extraída para cá para que o comando e a task periódica não sejam duas
    cópias do mesmo gesto (a lei anti-duplicação vale para comportamento tanto
    quanto para dado). Devolve `(lançamentos liberados, perfis recalculados)`.

    **Por que esta task precisava nascer, e não só o comando.** O docstring do
    comando sempre disse *"de minuto em minuto, pelo mesmo processo que hospeda
    o consumidor"* — mas nada no `docker-compose.yml` ou no `huey` desta célula
    chamava o comando em lugar nenhum: ele só existia para rodar à mão. Na
    prática, XP social (sugestão, voto, fórum) nasce em quarentena
    (`quarentena_horas` de cada regra, RegraDePontuacao) e **ficaria represado
    para sempre** — o aluno faria a ação, a regra pagaria de verdade, e o
    número nunca apareceria no perfil dele, porque ninguém chamava o gesto que
    o tira da quarentena. Achado numa auditoria pedida pelo mantenedor em
    03/09/2026, depois de alunos já terem participado e o quadro de pontos
    continuar zerado.
    """
    # Importado AQUI, não no topo do arquivo: `motor.py` importa
    # `relay_apos_commit` deste módulo, e um `from .motor import recalcular`
    # no topo fecharia um ciclo (motor → tasks → motor) que o Python não
    # resolve. `tasks.py` é o módulo mais "de baixo" da célula — ele pode
    # depender de `motor.py` numa função, nunca no import do módulo inteiro.
    from .motor import recalcular

    agora = timezone.now()
    vencidos = LancamentoDeXP.objects.filter(
        status=LancamentoDeXP.Status.PENDENTE, liberado_em__lte=agora
    )
    # Quem recalcular depois. Coletado ANTES do update: depois dele o filtro
    # por `pendente` não acha mais ninguém.
    afetados = set(vencidos.values_list("pessoa_id", "site_id"))
    quantos = vencidos.update(status=LancamentoDeXP.Status.DEFINITIVO)

    for pessoa_id, site_id in afetados:
        recalcular(pessoa_id, site_id)

    return quantos, len(afetados)


@huey.periodic_task(crontab(minute="*"))
def liberar_quarentena_periodico() -> tuple[int, int]:
    """A rede de segurança do XP social: a cada minuto, libera quem venceu.

    Mesmo desenho de `relay_outbox_periodico` — mesmo worker (`run_huey`,
    serviço `gamificacao-relay` no compose), mesma cadência. Rodar duas vezes
    no mesmo minuto é seguro: o filtro é por `status`, e um lançamento já
    `DEFINITIVO` não é tocado de novo.
    """
    return liberar_quarentena()
