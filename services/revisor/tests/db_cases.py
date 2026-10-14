"""Run with Django test runner; SQLite does not prove PostgreSQL concurrency."""
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.db import IntegrityError, transaction, connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature

from revisor.models import DailyQuota, Owner, Project, Review
from revisor.persistence import ReservationError, reserve


class PersistenceTests(TestCase):
    def setUp(self):
        self.owner = Owner.objects.create(site_id='meshcraft', actor_id='opaque-student')
        self.project = Project.objects.create(owner=self.owner, name='Hair')
        self.args = dict(site_id='meshcraft', actor_id='opaque-student', project_id=self.project.pk,
                         key='request-00000001', upload_sha256='a'*64, item_type='accessory', profile='rigid')

    def test_ten_attempts_and_idempotent_retry(self):
        for n in range(10):
            reserve(**{**self.args, 'key': f'request-{n:08}'})
        previous, created = reserve(**{**self.args, 'key': 'request-00000000'})
        self.assertFalse(created)
        self.assertEqual(previous.state, 'received')
        with self.assertRaisesRegex(ReservationError, 'daily_quota'):
            reserve(**{**self.args, 'key': 'request-00000010'})
        self.assertEqual(Review.objects.count(), 10)
        self.assertEqual(DailyQuota.objects.get().used, 10)

    def test_conflict_does_not_consume_quota(self):
        reserve(**self.args)
        with self.assertRaisesRegex(ReservationError, 'idempotency_conflict'):
            reserve(**{**self.args, 'upload_sha256': 'b'*64})
        self.assertEqual(DailyQuota.objects.get().used, 1)

    def test_other_student_and_other_site_cannot_reserve_project(self):
        for overrides in ({'actor_id': 'another-student'}, {'site_id': 'another-site'}):
            with self.assertRaisesRegex(ReservationError, 'not_found'):
                reserve(**{**self.args, **overrides})
        self.assertEqual(Review.objects.count(), 0)


        self.assertEqual(DailyQuota.objects.count(), 0)

    def test_sao_paulo_day_and_retry_after_midnight(self):
        first, _ = reserve(**self.args, now=datetime(2026, 10, 14, 2, 59, tzinfo=timezone.utc))
        same, created = reserve(**self.args, now=datetime(2026, 10, 14, 3, 1, tzinfo=timezone.utc))
        self.assertEqual(first.pk, same.pk)
        self.assertFalse(created)
        self.assertEqual(str(DailyQuota.objects.get().day), '2026-10-13')
        reserve(**{**self.args, 'key': 'request-00000002'}, now=datetime(2026, 10, 14, 3, 1, tzinfo=timezone.utc))
        self.assertEqual(DailyQuota.objects.count(), 2)

    def test_failed_write_rolls_back_reservation(self):
        with patch('revisor.persistence.Review.objects.create', side_effect=IntegrityError('test')):
            with self.assertRaises(IntegrityError):
                reserve(**self.args)
        self.assertEqual(DailyQuota.objects.count(), 0)
        self.assertEqual(Review.objects.count(), 0)

    def test_database_enforces_daily_ceiling(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            DailyQuota.objects.create(owner=self.owner, day='2026-10-14', used=11)

    def test_nonfinite_scale_is_rejected_without_reservation(self):
        for value in (float('nan'), float('inf'), -1, True):
            with self.assertRaisesRegex(ReservationError, 'invalid_request'):
                reserve(**{**self.args, 'studs_per_unit': value})
        self.assertEqual(Review.objects.count(), 0)


@skipUnlessDBFeature('has_select_for_update')
class ConcurrentReservations(TransactionTestCase):
    def setUp(self):
        owner = Owner.objects.create(site_id='meshcraft', actor_id='student')
        self.project = Project.objects.create(owner=owner, name='Concurrency')

    def submit(self, key):
        try:
            review, created = reserve(site_id='meshcraft', actor_id='student', project_id=self.project.pk,
                                      key=key, upload_sha256='a'*64, item_type='accessory', profile='rigid')
            return str(review.pk), created
        except ReservationError as exc:
            return str(exc), False
        finally:
            connections.close_all()

    def test_twenty_simultaneous_requests_consume_only_ten(self):
        with ThreadPoolExecutor(max_workers=20) as workers:
            results = list(workers.map(self.submit, [f'request-{i:08}' for i in range(20)]))
        self.assertEqual(sum(created for _, created in results), 10)
        self.assertEqual(sum(code == 'daily_quota' for code, _ in results), 10)
        self.assertEqual(Review.objects.count(), 10)
        self.assertEqual(DailyQuota.objects.get().used, 10)

    def test_simultaneous_retries_have_one_result_and_one_charge(self):
        with ThreadPoolExecutor(max_workers=12) as workers:
            results = list(workers.map(self.submit, ['same-request-0001']*12))
        self.assertEqual(len({identifier for identifier, _ in results}), 1)
        self.assertEqual(sum(created for _, created in results), 1)
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(DailyQuota.objects.get().used, 1)
