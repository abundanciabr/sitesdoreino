# pagamentos/core/models.py  # [RECEITA:R1 v1]
# core/ é dono do modelo (ver AGENTS.pagamentos: "core/ ... modelos, ledger, outbox,
# ... gateway p/ providers"). methods/pix e methods/card leem/escrevem Intent daqui —
# isso NÃO viola INV-P9 (a independência é só entre os dois métodos, e entre método
# e providers; método→core é permitido e é o padrão desta célula).
from __future__ import annotations

import uuid

from django.db import models

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
