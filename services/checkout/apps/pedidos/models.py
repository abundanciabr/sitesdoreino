import uuid

from django.db import models


class SnapshotCongelado(Exception):
    """[INV-P1] Tentativa de reescrever um snapshot já criado."""


# [INV-P1] O que o pedido congela na criação. Correção de pedido = pedido novo +
# cancelamento do antigo, nunca UPDATE nestes campos.
CAMPOS_CONGELADOS = ("site_id", "items", "total_cents", "customer")


class Session(models.Model):
    """Sessão de checkout: a oferta lida do catálogo NA ABERTURA, por site."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = models.CharField(max_length=64)  # [INV-P11] vem do Host, nunca do payload
    offer_slug = models.CharField(max_length=200)
    offer = models.JSONField()
    lead_id = models.CharField(max_length=64, blank=True, default="")
    utm = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["site_id", "offer_slug"])]


class OrderQuerySet(models.QuerySet):
    def update(self, **kwargs):
        # [INV-P1] QuerySet.update() não passa por Model.save() — o guarda precisa
        # existir nos dois caminhos, senão a lei vale só pela metade.
        congelados = sorted(set(kwargs) & set(CAMPOS_CONGELADOS))
        if congelados:
            raise SnapshotCongelado(
                f"snapshot é create-only; campos recusados: {', '.join(congelados)}"
            )
        return super().update(**kwargs)


class Order(models.Model):
    AGUARDANDO = "aguardando_pagamento"
    STATUS = [
        (AGUARDANDO, AGUARDANDO),
        ("pago", "pago"),
        ("recusado", "recusado"),
        ("expirado", "expirado"),
        ("reembolsado", "reembolsado"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.OneToOneField(
        Session, on_delete=models.PROTECT, related_name="order"
    )
    site_id = models.CharField(max_length=64)
    status = models.CharField(max_length=32, choices=STATUS, default=AGUARDANDO)
    items = models.JSONField()
    total_cents = models.PositiveIntegerField()
    customer = models.JSONField()
    method = models.CharField(max_length=8)
    intent_id = models.CharField(max_length=64)
    pix = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrderQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(total_cents__gte=1), name="order_total_cents_min_1"
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            anterior = (
                Order.objects.filter(pk=self.pk).values(*CAMPOS_CONGELADOS).first()
            )
            if anterior is not None:
                divergentes = sorted(
                    campo
                    for campo in CAMPOS_CONGELADOS
                    if getattr(self, campo) != anterior[campo]
                )
                if divergentes:
                    raise SnapshotCongelado(
                        "snapshot é create-only; campos recusados: "
                        f"{', '.join(divergentes)}"
                    )
        return super().save(*args, **kwargs)


class OutboxEvent(models.Model):  # [RECEITA:R3 v1]
    event_id = models.UUIDField(default=uuid.uuid4, unique=True)
    event = models.CharField(max_length=100)
    version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField()
    occurred_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["published_at"])]
