"""Same-content (same digest) images share one scan.

Regression coverage for an unchanged busybox sidecar image: every tag has the same digest, so
every tag maps to one ScanRun. A tag that arrived while another tag's scan was
live used to be skipped and never received results; it now waits on that run,
gets its results, is re-queued if the run fails, and reuses a fresh result.
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Image, Repository, RepositoryTag, ScanRun
from core.services.scans import (
    CLAIMED,
    WAITING,
    complete_scan,
    find_reusable_scan_source,
    image_scan_is_active,
    join_or_claim_scan,
    reap_stale_scans,
)

DIGEST = 'sha256:' + '9e' * 32
SBOM = {'artifacts': [{'name': 'busybox', 'version': '1.36.1'}]}
GRYPE = {'matches': [], 'descriptor': {'name': 'grype'}}


def _busybox(tag, **fields):
    defaults = {'digest': DIGEST, 'scan_status': 'pending'}
    defaults.update(fields)
    return Image.objects.create(name=f'registry.example/sidecar-busybox:{tag}', **defaults)


def _scanned(image):
    Image.objects.filter(pk=image.pk).update(
        scan_status='success', sbom_data=SBOM, grype_data=GRYPE,
        vulnerability_summary={'critical': 0, 'high': 0},
    )
    image.refresh_from_db()
    return image


class JoinOrClaimTests(TestCase):
    def test_second_image_with_same_digest_waits_on_the_live_run(self):
        first, second = _busybox('21.31.0.16'), _busybox('21.30.0.43')

        run, outcome = join_or_claim_scan(first)
        joined, second_outcome = join_or_claim_scan(second)

        self.assertEqual(outcome, CLAIMED)
        self.assertEqual(second_outcome, WAITING)
        self.assertEqual(joined.pk, run.pk)
        self.assertEqual(list(run.waiting_images.all()), [second])
        self.assertTrue(image_scan_is_active(second))

    def test_redelivered_message_reclaims_its_own_live_run(self):
        image = _busybox('21.31.0.21', scan_status='in_process')
        run, _ = join_or_claim_scan(image, celery_task_id='task-1')

        again, outcome = join_or_claim_scan(image, celery_task_id='task-1')

        self.assertEqual(outcome, CLAIMED)
        self.assertEqual(again.pk, run.pk)
        self.assertEqual(again.attempt_count, 2)
        self.assertFalse(again.waiting_images.exists())

    def test_finished_run_is_claimed_again_not_waited_on(self):
        first, second = _busybox('1'), _busybox('2')
        run, _ = join_or_claim_scan(first)
        complete_scan(run.pk)

        rerun, outcome = join_or_claim_scan(second)

        self.assertEqual(outcome, CLAIMED)
        self.assertEqual(rerun.pk, run.pk)
        self.assertEqual(rerun.status, 'running')
        self.assertEqual(rerun.attempt_count, 2)
        self.assertFalse(rerun.waiting_images.exists())

    def test_current_subject_is_live_even_when_an_older_image_owns_the_run(self):
        owner = _scanned(_busybox('21.30.0.3'))
        run, _ = join_or_claim_scan(owner)
        complete_scan(run.pk)
        subject = _busybox('21.31.0.21', scan_status='in_process')

        join_or_claim_scan(subject)
        Image.objects.filter(pk=subject.pk).update(updated_at=timezone.now() - timedelta(days=1))
        subject.refresh_from_db()

        self.assertEqual(ScanRun.objects.get(pk=run.pk).image_id, owner.pk)
        self.assertTrue(image_scan_is_active(subject))


class FinishScanRunTests(TestCase):
    def setUp(self):
        repository = Repository.objects.create(name='helm/branding', url='helm/branding', repository_type='helm')
        self.tag = RepositoryTag.objects.create(repository=repository, tag='21.30.43', processing_status='in_process')
        self.subject = _busybox('21.31.0.16', scan_status='in_process')
        self.waiter = _busybox('21.30.0.43')
        self.waiter.repository_tags.add(self.tag)
        self.run, _ = join_or_claim_scan(self.subject)
        join_or_claim_scan(self.waiter)

    def test_success_copies_results_to_waiters(self):
        from core.tasks import _finish_scan_run

        _scanned(self.subject)
        released = _finish_scan_run(self.run.uuid, source_image=self.subject)

        self.assertEqual(released, [self.waiter.pk])
        self.waiter.refresh_from_db()
        self.tag.refresh_from_db()
        self.run.refresh_from_db()
        self.assertEqual(self.waiter.scan_status, 'success')
        self.assertEqual(self.waiter.grype_data, GRYPE)
        self.assertEqual(self.waiter.sbom_data, SBOM)
        self.assertEqual(self.tag.processing_status, 'success')
        self.assertEqual(self.run.status, 'success')
        self.assertFalse(self.run.waiting_images.exists())

    @patch('core.tasks.generate_sbom_and_create_components.delay')
    def test_failure_requeues_waiters_but_not_the_failed_subject(self, delay):
        from core.tasks import _finish_scan_run

        _finish_scan_run(self.run.uuid, error='pull timed out', source_image=self.subject)

        delay.assert_called_once_with(image_uuid=str(self.waiter.pk), art_type='helm')
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, 'failed')
        self.assertFalse(self.run.waiting_images.exists())

    def test_reaper_releases_waiters_of_an_expired_run(self):
        ScanRun.objects.filter(pk=self.run.pk).update(lease_expires_at=timezone.now() - timedelta(minutes=1))

        reaped_runs, released = reap_stale_scans()

        self.assertEqual(reaped_runs, 1)
        self.assertIn(self.waiter.pk, released)
        self.waiter.refresh_from_db()
        self.assertEqual(self.waiter.scan_status, 'error')
        self.assertFalse(ScanRun.objects.get(pk=self.run.pk).waiting_images.exists())


class GenerateTaskDedupTests(TestCase):
    def test_task_waits_instead_of_scanning_identical_live_content(self):
        from core.tasks import generate_sbom_and_create_components

        join_or_claim_scan(_busybox('21.31.0.16', scan_status='in_process'))
        loser = _busybox('21.30.0.43', scan_status='in_process')

        result = generate_sbom_and_create_components(image_uuid=str(loser.uuid))

        self.assertEqual(result['status'], 'waiting')
        loser.refresh_from_db()
        self.assertEqual(loser.scan_status, 'pending')
        self.assertTrue(loser.waiting_scan_runs.exists())

    def test_task_reuses_a_fresh_result_of_identical_content(self):
        from core.tasks import generate_sbom_and_create_components

        source = _scanned(_busybox('21.31.0.16'))
        run, _ = join_or_claim_scan(source)
        complete_scan(run.pk)
        newcomer = _busybox('21.31.0.21')

        result = generate_sbom_and_create_components(image_uuid=str(newcomer.uuid))

        self.assertEqual(result['status'], 'reused')
        self.assertEqual(result['source_image_uuid'], str(source.uuid))
        newcomer.refresh_from_db()
        self.assertEqual(newcomer.scan_status, 'success')
        self.assertEqual(newcomer.grype_data, GRYPE)


class ReuseWindowTests(TestCase):
    def setUp(self):
        self.source = _scanned(_busybox('21.31.0.16'))
        self.run, _ = join_or_claim_scan(self.source)
        complete_scan(self.run.pk)
        self.newcomer = _busybox('21.31.0.21')

    def test_fresh_result_is_reusable(self):
        self.assertEqual(find_reusable_scan_source(self.newcomer), self.source)

    def test_result_older_than_window_is_not_reused(self):
        ScanRun.objects.filter(pk=self.run.pk).update(finished_at=timezone.now() - timedelta(hours=25))
        self.assertIsNone(find_reusable_scan_source(self.newcomer))

    @override_settings(SCAN_REUSE_HOURS=0)
    def test_reuse_can_be_disabled(self):
        self.assertIsNone(find_reusable_scan_source(self.newcomer))

    def test_images_without_digest_never_reuse(self):
        nameless = Image.objects.create(name='registry.example/local:dev', digest='')
        self.assertIsNone(find_reusable_scan_source(nameless))
