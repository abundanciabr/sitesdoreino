# apps/core/models.py  # [RECEITA:R4 v1]
import uuid

from django.db import models


class Lead(models.Model):
    """Uma pessoa, dentro de UM site. A mesma pessoa (mesmo e-mail) em sites
    diferentes é registrada como leads distintos — upsert é por (site_id, email)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = models.CharField(max_length=100)
    email = models.EmailField()
    name = models.CharField(max_length=200, blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    source = models.CharField(max_length=100, blank=True, default="")
    utm = models.JSONField(default=dict, blank=True)
    tags = models.JSONField(default=list, blank=True)
    consent = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "email"], name="uniq_lead_site_email"
            ),
        ]


class TimelineEvent(models.Model):
    """Histórico da pessoa, por site. Nunca é apagado — upsert e reprocessamento
    de evento só acrescentam entrada, nunca removem as existentes."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="timeline")
    event = models.CharField(max_length=100)  # ex.: "quiz.completado", "lead.upsert"
    event_id = models.UUIDField(null=True, blank=True)  # ausente para upsert via API
    payload = models.JSONField()
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["lead", "occurred_at"])]


class EventoProcessado(models.Model):
    """[INV-leads-idempotencia] a unicidade É o guarda: reentrega do mesmo
    event_id não roda o handler pela segunda vez."""

    event_id = models.UUIDField(unique=True)
    processed_at = models.DateTimeField(auto_now_add=True)
