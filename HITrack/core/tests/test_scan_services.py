from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Image, ScanRun
from core.services.purl import component_identity
from core.services.scans import claim_scan, finish_scan, queue_scan, scan_idempotency_key, store_raw_artifact


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
