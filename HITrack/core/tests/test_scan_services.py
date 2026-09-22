from datetime import timedelta
from unittest.mock import patch

from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core.models import Image, Repository, RepositoryTag, ScanRun
from core.services.purl import component_identity
from core.services.scans import (
    claim_scan,
    finish_scan,
    queue_scan,
    renew_scan_lease,
    scan_idempotency_key,
    store_raw_artifact,
)
from core.tasks import reconcile_stale_scan_states, scan_image_with_grype
from core.utils.status import resolve_repository_scan_status


class RepositoryStatusResolutionTests(SimpleTestCase):
    def test_active_children_take_precedence(self):
        self.assertEqual(
            resolve_repository_scan_status('error', 1, 0, 2, 0),
            'in_process',
        )

    def test_child_error_replaces_stale_pending_or_in_process_status(self):
        self.assertEqual(resolve_repository_scan_status('pending', 0, 0, 1, 0), 'error')
        self.assertEqual(resolve_repository_scan_status('in_process', 0, 0, 0, 1), 'error')


class ScanRunServiceTests(TestCase):
    def setUp(self):
        self.image = Image.objects.create(name='registry.example/api', digest='sha256:abc')

    def test_queue_is_idempotent_for_same_scanner_and_digest(self):
        first, first_created = queue_scan(self.image, scanner_version='syft-1')
        second, second_created = queue_scan(self.image, scanner_version='syft-1')
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ScanRun.objects.count(), 1)

    def test_expired_lease_can_be_claimed_again(self):
        run, _ = queue_scan(self.image)
        ScanRun.objects.filter(pk=run.pk).update(status='running', lease_expires_at=timezone.now())
        claimed_run, claimed = claim_scan(run.pk)
        self.assertTrue(claimed)
        self.assertEqual(claimed_run.status, 'running')
        self.assertEqual(claimed_run.attempt_count, 1)

    def test_active_lease_and_successful_run_cannot_be_claimed_twice(self):
        run, _ = queue_scan(self.image)
        claimed_run, claimed = claim_scan(run.pk)
        self.assertTrue(claimed)
        same_run, claimed_again = claim_scan(run.pk)
        self.assertFalse(claimed_again)
        self.assertEqual(same_run.pk, claimed_run.pk)

        finish_scan(run.pk)
        successful_run, claimed_success = claim_scan(run.pk)
        self.assertFalse(claimed_success)
        self.assertEqual(successful_run.status, 'success')

    def test_finished_or_expired_identity_is_requeued_cleanly(self):
        run, _ = queue_scan(self.image, celery_task_id='old-task')
        finish_scan(run.pk, error='temporary failure')

        requeued, created = queue_scan(self.image, celery_task_id='new-task')

        self.assertTrue(created)
        self.assertEqual(requeued.pk, run.pk)
        self.assertEqual(requeued.status, 'queued')
        self.assertEqual(requeued.celery_task_id, 'new-task')
        self.assertEqual(requeued.error_message, '')
        self.assertIsNone(requeued.finished_at)

    def test_renew_scan_lease_keeps_pipeline_alive_between_tasks(self):
        run, _ = queue_scan(self.image)
        old_expiry = timezone.now()
        ScanRun.objects.filter(pk=run.pk).update(lease_expires_at=old_expiry)

        self.assertEqual(renew_scan_lease(run.pk), 1)

        run.refresh_from_db()
        self.assertGreater(run.lease_expires_at, old_expiry)

    def test_idempotency_key_prefers_digest_then_artifact_then_name(self):
        digest_key = scan_idempotency_key(self.image, 'scanner', 'policy')
        self.image.digest = ''
        self.image.artifact_reference = 'registry.example/api@sha256:def'
        artifact_key = scan_idempotency_key(self.image, 'scanner', 'policy')
        self.image.artifact_reference = ''
        name_key = scan_idempotency_key(self.image, 'scanner', 'policy')
        self.assertEqual(len({digest_key, artifact_key, name_key}), 3)

    def test_raw_artifact_storage_is_content_addressed_and_deduplicated(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            first = store_raw_artifact(self.image, 'sbom', {'artifacts': [{'name': 'curl'}]})
            second = store_raw_artifact(self.image, 'sbom', {'artifacts': [{'name': 'curl'}]})
            changed = store_raw_artifact(self.image, 'sbom', {'artifacts': [{'name': 'openssl'}]})

        self.assertEqual(first.pk, second.pk)
        self.assertNotEqual(first.pk, changed.pk)
        self.assertEqual(first.size_bytes, len(b'{"artifacts":[{"name":"curl"}]}'))
        self.assertTrue(first.storage_key.endswith(f'{first.checksum}.json'))


class StaleScanReconciliationTests(TestCase):
    def setUp(self):
        self.repository = Repository.objects.create(
            name='registry.example/api',
            url='registry.example/api',
            repository_type='docker',
            scan_status='in_process',
        )
        self.tag = RepositoryTag.objects.create(
            repository=self.repository,
            tag='1.0',
            processing_status='in_process',
        )
        self.image = Image.objects.create(
            name='registry.example/api:1.0',
            scan_status='in_process',
        )
        self.image.repository_tags.add(self.tag)

    def test_expired_run_fails_image_tag_and_repository(self):
        run, _ = queue_scan(self.image)
        ScanRun.objects.filter(pk=run.pk).update(
            status='running',
            lease_expires_at=timezone.now() - timedelta(minutes=1),
        )

        result = reconcile_stale_scan_states()

        run.refresh_from_db()
        self.image.refresh_from_db()
        self.tag.refresh_from_db()
        self.repository.refresh_from_db()
        self.assertEqual(result['expired_runs'], 1)
        self.assertEqual(run.status, 'failed')
        self.assertEqual(self.image.scan_status, 'error')
        self.assertEqual(self.tag.processing_status, 'error')
        self.assertEqual(self.repository.scan_status, 'error')

    @patch.dict('os.environ', {'HITRACK_ORPHAN_SCAN_TIMEOUT_MINUTES': '1'})
    def test_orphan_pending_image_without_run_is_failed(self):
        Image.objects.filter(pk=self.image.pk).update(
            scan_status='pending',
            updated_at=timezone.now() - timedelta(minutes=2),
        )

        result = reconcile_stale_scan_states()

        self.image.refresh_from_db()
        self.assertEqual(result['failed_images'], 1)
        self.assertEqual(self.image.scan_status, 'error')

    @patch('core.tasks.process_grype_scan_results.delay')
    def test_grype_redelivery_resumes_saved_result_processing(self, delay):
        self.image.grype_data = {'matches': []}
        self.image.save(update_fields=['grype_data', 'updated_at'])

        result = scan_image_with_grype.run(str(self.image.pk))

        self.assertEqual(result['status'], 'resumed')
        delay.assert_called_once_with(str(self.image.pk), {'matches': []}, None)


class PurlIdentityTests(TestCase):
    def test_version_and_qualifiers_do_not_change_component_identity(self):
        self.assertEqual(
            component_identity('pkg:deb/debian/curl@7.88.1?arch=amd64', 'deb', 'curl'),
            'pkg:deb/debian/curl',
        )

    def test_legacy_identity_keeps_ecosystems_separate(self):
        self.assertNotEqual(
            component_identity(None, 'npm', 'request'),
            component_identity(None, 'deb', 'request'),
        )
