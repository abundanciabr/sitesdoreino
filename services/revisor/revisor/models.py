"""Only this cell's data. Identity IDs are opaque, never cross-database FKs."""
import uuid

from django.db import models


class Owner(models.Model):
    site_id = models.CharField(max_length=80)
    actor_id = models.CharField(max_length=128)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['site_id', 'actor_id'], name='revisor_owner_unique')]


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(Owner, on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)


class DailyQuota(models.Model):
    owner = models.ForeignKey(Owner, on_delete=models.PROTECT)
    day = models.DateField()
    used = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'day'], name='revisor_daily_unique'),
            models.CheckConstraint(condition=models.Q(used__gte=0, used__lte=10), name='revisor_daily_range'),
        ]


class Review(models.Model):
    STATES = [(x, x) for x in ('received', 'queued', 'analyzing', 'completed', 'unreadable', 'technical_failure')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(Owner, on_delete=models.PROTECT)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    idempotency_hash = models.CharField(max_length=64)
    request_hash = models.CharField(max_length=64)
    item_type = models.CharField(max_length=16)
    profile = models.CharField(max_length=16)
    studs_per_unit = models.FloatField(null=True)
    state = models.CharField(max_length=24, choices=STATES, default='received')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    report = models.JSONField(null=True)
    narration_state = models.CharField(max_length=16, default='pending')
    narration = models.JSONField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner', 'idempotency_hash'], name='revisor_idempotent')]
        indexes = [
            models.Index(fields=['owner', '-created_at', '-id'], name='revisor_history'),
            models.Index(fields=['state', 'created_at'], name='revisor_queue'),
        ]
