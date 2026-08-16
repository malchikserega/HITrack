from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core.models import Image, ScanRun
from core.services.purl import component_identity
from core.services.scans import claim_scan, queue_scan
from core.tasks import _is_image_available_locally


class LocalDockerImageTests(SimpleTestCase):
    @patch('core.tasks.subprocess.run')
    def test_detects_image_that_exists_in_local_docker(self, run):
        run.return_value = Mock(returncode=0)

        self.assertTrue(_is_image_available_locally('my-service:dev'))
        run.assert_called_once_with(
            ['docker', 'image', 'inspect', 'my-service:dev'],
            capture_output=True,
            check=False,
        )

    @patch('core.tasks.subprocess.run')
    def test_missing_local_image_uses_registry_fallback(self, run):
        run.return_value = Mock(returncode=1)

        self.assertFalse(_is_image_available_locally('my-service:dev'))


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
