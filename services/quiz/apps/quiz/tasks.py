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
import uuid
from datetime import datetime

import redis
from django.utils import timezone
from huey import crontab

from config.huey import huey

from .models import OutboxEvent, TelemetryEvent

logger = logging.getLogger(__name__)

# Stream de clique. Não é a outbox: MAXLEN pode descartar evento antigo.
# O lead completo mora em Submission e em eventos.quiz.completado.
STREAM_TELEMETRIA = "telemetry.quiz.events"
GRUPO_TELEMETRIA = "quiz-telemetria"
CONSUMIDOR_TELEMETRIA = "huey"
MAXLEN_TELEMETRIA = 100_000
LOTE_TELEMETRIA = 500
TIPOS_DE_EVENTO = frozenset({"view_quiz", "view_question", "click_option", "abandon"})


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


def publicar_telemetria(envelope: dict) -> None:
    """XADD e nada mais. REDIS_STREAMS_URL é lida aqui, nunca no import."""
    cliente = redis.from_url(os.environ["REDIS_STREAMS_URL"])
    cliente.xadd(
        STREAM_TELEMETRIA,
        {"json": json.dumps(envelope, ensure_ascii=False)},
        maxlen=MAXLEN_TELEMETRIA,
        approximate=True,
    )


def _evento_da_mensagem(campos) -> TelemetryEvent | None:
    cru = campos.get(b"json") or campos.get("json")
    if not cru:
        return None
    if isinstance(cru, bytes):
        cru = cru.decode()
    try:
        dados = json.loads(cru)
    except json.JSONDecodeError:
        return None
    if not isinstance(dados, dict) or dados.get("event_type") not in TIPOS_DE_EVENTO:
        return None
    try:
        session_id = uuid.UUID(str(dados["session_id"]))
        ocorreu = datetime.fromisoformat(str(dados["occurred_at"]))
    except (KeyError, TypeError, ValueError):
        return None
    if timezone.is_naive(ocorreu):
        ocorreu = timezone.make_aware(ocorreu, timezone.utc)
    site_id = dados.get("site_id")
    quiz_slug = dados.get("quiz_slug")
    version_key = dados.get("version_key")
    element_id = dados.get("element_id") or ""
    metadata = dados.get("metadata") or {}
    if (
        not isinstance(site_id, str)
        or not isinstance(quiz_slug, str)
        or not isinstance(version_key, str)
        or not isinstance(element_id, str)
        or len(element_id) > 120
        or not isinstance(metadata, dict)
    ):
        return None
    return TelemetryEvent(
        session_id=session_id,
        site_id=site_id,
        quiz_slug=quiz_slug,
        version_key=version_key,
        event_type=dados["event_type"],
        element_id=element_id,
        metadata=metadata,
        occurred_at=ocorreu,
        received_at=timezone.now(),
    )


def drenar_telemetria(lote: int = LOTE_TELEMETRIA) -> int:
    """Lê um lote do stream e grava de uma vez. Payload inválido é confirmado
    para não prender o grupo. Falha no insert não confirma nada. Falha no ACK
    depois do insert deixa a mensagem pendente: o `>` não a reentrega, então
    a linha não duplica."""
    cliente = redis.from_url(os.environ["REDIS_STREAMS_URL"])
    try:
        cliente.xgroup_create(
            STREAM_TELEMETRIA, GRUPO_TELEMETRIA, id="0", mkstream=True
        )
    except redis.ResponseError as erro:
        if "BUSYGROUP" not in str(erro):
            raise
    resposta = cliente.xreadgroup(
        GRUPO_TELEMETRIA,
        CONSUMIDOR_TELEMETRIA,
        {STREAM_TELEMETRIA: ">"},
        count=lote,
    )
    if not resposta:
        return 0
    gravar = []
    confirmar = []
    for _stream, mensagens in resposta:
        for msg_id, campos in mensagens:
            evento = _evento_da_mensagem(campos)
            if evento is None:
                logger.warning("telemetria descartada: %s", msg_id)
            else:
                gravar.append(evento)
            confirmar.append(msg_id)
    if gravar:
        TelemetryEvent.objects.bulk_create(gravar)
    if confirmar:
        cliente.xack(STREAM_TELEMETRIA, GRUPO_TELEMETRIA, *confirmar)
    return len(gravar)


@huey.periodic_task(crontab(minute="*"))
def drenar_telemetria_periodico() -> int:
    return drenar_telemetria()


@huey.periodic_task(crontab(minute="*"))
def relay_outbox_periodico() -> int:
    """[RECEITA:R3 v1] Rede de segurança: a cada minuto, o worker
    (`python manage.py run_huey`) republica o que o caminho on_commit deixou
    pendente. É o que garante entrega mesmo que o web caia entre o commit e o
    publish."""
    return relay_outbox()
