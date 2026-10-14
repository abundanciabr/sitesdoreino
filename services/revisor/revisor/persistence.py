"""Atomic submission reservation; no file storage or analysis in transactions."""
import hashlib
import json
import math
import re
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from revisor.models import DailyQuota, Owner, Project, Review


class ReservationError(ValueError):
    pass


def reserve(*, site_id, actor_id, project_id, key, upload_sha256, item_type, profile,
            studs_per_unit=None, now=None):
    """Caller must authenticate and validate upload envelope before reserving.

    PostgreSQL owner row lock serializes quota and idempotency across workers.
    Reservation consumes one attempt even when the subsequent file is unreadable.
    A retry of the same request consumes none, including across date boundaries.
    This is not a worker queue: transition to queued requires temporary upload
    handoff and crash recovery, implemented in the HTTP/worker delivery.
    """
    if (not isinstance(site_id, str) or not 0 < len(site_id) <= 80
            or not isinstance(actor_id, str) or not 0 < len(actor_id) <= 128
            or not isinstance(key, str) or not 16 <= len(key) <= 128
            or not isinstance(upload_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', upload_sha256)
            or item_type not in {'accessory', 'clothing', 'weapon', 'vehicle', 'scene'}
            or profile not in {'game', 'rigid', 'layered'}):
        raise ReservationError('invalid_request')
    if studs_per_unit is not None:
        if type(studs_per_unit) not in (int, float) or not math.isfinite(studs_per_unit) or not 0 < studs_per_unit <= 10000:
            raise ReservationError('invalid_request')
        studs_per_unit = float(studs_per_unit)
    moment = now or timezone.now()
    if timezone.is_naive(moment):
        raise ReservationError('invalid_request')
    digest = hashlib.sha256(key.encode('utf-8')).hexdigest()
    fingerprint = hashlib.sha256(json.dumps(
        [str(project_id), upload_sha256, item_type, profile, studs_per_unit],
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
    with transaction.atomic():
        owner, _ = Owner.objects.get_or_create(site_id=site_id, actor_id=actor_id)
        owner = Owner.objects.select_for_update().get(pk=owner.pk)
        previous = Review.objects.filter(owner=owner, idempotency_hash=digest).first()
        if previous:
            if previous.request_hash != fingerprint:
                raise ReservationError('idempotency_conflict')
            return previous, False
        project = Project.objects.filter(pk=project_id, owner=owner).first()
        if project is None:
            raise ReservationError('not_found')
        quota, _ = DailyQuota.objects.get_or_create(owner=owner, day=moment.astimezone(ZoneInfo('America/Sao_Paulo')).date())
        if quota.used >= 10:
            raise ReservationError('daily_quota')
        review = Review.objects.create(owner=owner, project=project, idempotency_hash=digest,
                                       request_hash=fingerprint, item_type=item_type, profile=profile,
                                       studs_per_unit=studs_per_unit)
        quota.used += 1
        quota.save(update_fields=['used'])
        return review, True
