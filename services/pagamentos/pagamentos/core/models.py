# pagamentos/core/models.py  # [RECEITA:R1 v1]
# core/ é dono do modelo (ver AGENTS.pagamentos: "core/ ... modelos, ledger, outbox,
# ... gateway p/ providers"). methods/pix e methods/card leem/escrevem Intent daqui —
# isso NÃO viola INV-P9 (a independência é só entre os dois métodos, e entre método
# e providers; método→core é permitido e é o padrão desta célula).
#
# Outbox (RECEITA:R3) e o helper de transição+dedup dos webhooks moram aqui também
# — não em app Django separado. Decisão de orçamento (ver LICOES.md): core/models.py
# é o ÚNICO app com models.py/migrations desta célula; um app "eventos" à parte
# custaria outro migrations/__init__.py sem necessidade arquitetural real.
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import redis
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

STATUS_CHOICES = [
    ("created", "created"),
    ("pending", "pending"),
    ("approved", "approved"),
    ("rejected", "rejected"),
    ("expired", "expired"),
    ("refunded", "refunded"),
]
METHOD_CHOICES = [("pix", "pix"), ("card", "card")]


class Intent(models.Model):
    """Uma linha por intenção de cobrança. `idempotency_key` é o que torna
    POST /intents idempotente (INV-P4): a MESMA chave sempre resolve para a
    MESMA linha — nunca uma segunda chamada ao provider."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.CharField(max_length=255, unique=True)
    site_id = models.CharField(
        max_length=255
    )  # OPACO — armazenar e ecoar, nunca interpretar
    order_id = models.CharField(max_length=255)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="created")
    amount_cents = models.PositiveIntegerField()  # dinheiro é inteiro sempre
    currency = models.CharField(max_length=3, default="BRL")
    customer = models.JSONField()
    metadata = models.JSONField(default=dict, blank=True)

    provider_payment_id = models.CharField(max_length=255, blank=True, default="")
    pix_qr_code = models.TextField(blank=True, default="")
    pix_qr_code_base64 = models.TextField(blank=True, default="")
    pix_expires_at = models.DateTimeField(null=True, blank=True)
    card_reason_code = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["order_id"])]

    def __str__(self) -> str:
        return f"{self.method}:{self.id}:{self.status}"


class OutboxEvent(models.Model):
    """[RECEITA:R3 v1] Uma linha por evento emitido. `emitir()` grava SEMPRE na
    MESMA transação da mudança de estado que a justifica (INV-P6) — o relay
    (`relay_outbox`) publica no Redis Streams depois, marcando `published_at`."""

    event_id = models.UUIDField(default=uuid.uuid4, unique=True)
    event = models.CharField(max_length=100)  # ex.: "pagamento.aprovado"
    version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField()  # SÓ o campo `data` do envelope
    occurred_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["published_at"])]

    def __str__(self) -> str:
        return f"{self.event}:{self.event_id}"


def emitir(event: str, data: dict[str, Any], *, version: int = 1) -> OutboxEvent:
    """[RECEITA:R3 v1] [INV-P6] Chame SEMPRE dentro da MESMA transaction.atomic()
    da mudança de estado que o justifica — estado sem evento e evento sem estado
    são ambos impossíveis."""
    return OutboxEvent.objects.create(event=event, version=version, payload=data)


def relay_outbox() -> int:
    """[RECEITA:R3 v1] Publica os eventos pendentes em `eventos.<nome>` no Redis
    Streams e marca `published_at`. Chamada via `transaction.on_commit` logo após
    a transação que gravou o evento (latência sub-segundo). Nesta fase do
    esqueleto não há worker/periodic task de "rede de segurança" (Huey) — ver
    LICOES.md; a função é idempotente e segura de chamar de novo manualmente
    (um evento com `published_at` preenchido é ignorado pelo filtro abaixo)."""
    pendentes = list(
        OutboxEvent.objects.filter(published_at__isnull=True).order_by("id")[:200]
    )
    if not pendentes:
        return 0
    cliente = redis.from_url(settings.REDIS_STREAMS_URL)  # type: ignore[no-untyped-call]
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


def _relay_apos_commit() -> None:
    """Publica imediatamente após o commit. Uma falha aqui (ex.: Redis fora do
    ar) NUNCA perde o evento — ele já está persistido na outbox com
    `published_at=None` e será republicado na próxima chamada de
    `relay_outbox()` (manual, ou de um próximo webhook)."""
    try:
        relay_outbox()
    except Exception:  # noqa: BLE001 - defensivo por design, ver docstring
        logger.exception("relay_outbox falhou apos commit; evento fica pendente")


def transicionar_e_emitir(
    *, mp_payment_id: str, novo_status: str, evento: str, dados: dict[str, Any]
) -> bool:
    """[INV-P3] [INV-P6] Usado pelos webhook handlers de methods/pix e
    methods/card. Idempotente por `mp_payment_id` + status alvo: se a Intent já
    está no status alvo (replay do MP), é no-op — nenhuma transição, nenhum
    evento novo. Senão, a transição de estado e a linha da outbox nascem na
    MESMA transação; o `select_for_update()` fecha a corrida de duas entregas
    concorrentes do mesmo webhook. Devolve True quando de fato transicionou."""
    with transaction.atomic():
        intent = (
            Intent.objects.select_for_update()
            .filter(provider_payment_id=mp_payment_id)
            .first()
        )
        if intent is None or intent.status == novo_status:
            return False
        intent.status = novo_status
        intent.save(update_fields=["status", "updated_at"])
        emitir(evento, dados)
    transaction.on_commit(_relay_apos_commit)
    return True
