from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from core.models import Image, Repository, RepositoryTag


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
})
class RepositoryTagProcessEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='operator', password='test-password')
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.repository = Repository.objects.create(
            name='example/service',
            url='registry.example.com/example/service',
            repository_type='docker',
        )
        self.tag = RepositoryTag.objects.create(repository=self.repository, tag='1.0.0')

    @patch('core.tasks.process_single_tag.apply_async')
    def test_process_reports_background_task_as_scheduled(self, apply_async):
        apply_async.return_value = SimpleNamespace(id='parent-task-id')

        response = self.client.post(
            reverse('repository-tag-process', args=[self.tag.uuid]),
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'scheduled')
        self.assertEqual(response.data['tag_status'], 'pending')
        self.assertEqual(response.data['task_id'], 'parent-task-id')
        self.assertIn('SBOM scans', response.data['message'])
        self.tag.refresh_from_db()
        self.assertEqual(self.tag.processing_status, 'pending')
        apply_async.assert_called_once_with(
            args=[str(self.tag.uuid)],
            task_name='Process Single Tag',
        )

    @patch('core.tasks.scan_repository_tags.apply_async')
    def test_repository_scan_reports_background_task_as_scheduled(self, apply_async):
        apply_async.return_value = SimpleNamespace(id='repository-task-id')

        response = self.client.post(
            reverse('repository-scan-tags', args=[self.repository.uuid]),
            {'latest_only': True},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'scheduled')
        self.assertEqual(response.data['repository_status'], 'pending')
        self.assertEqual(response.data['task_id'], 'repository-task-id')
        self.repository.refresh_from_db()
        self.assertEqual(self.repository.scan_status, 'pending')
        apply_async.assert_called_once_with(
            args=[str(self.repository.uuid)],
            kwargs={'latest_only': True},
            task_name='Scan Repository Tags',
        )

    @patch('core.tasks.periodic_repository_scan.delay')
    def test_scan_all_queues_periodic_repository_task(self, delay):
        delay.return_value = SimpleNamespace(id='bulk-task-id')

        response = self.client.post(reverse('repository-scan-all-tags'), format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'scheduled')
        self.assertEqual(response.data['task_id'], 'bulk-task-id')
        self.assertIn('active repositories', response.data['message'])
        delay.assert_called_once_with()

    @patch('core.tasks.generate_sbom_and_create_components.delay')
    def test_image_rescan_reports_background_task_as_scheduled(self, delay):
        image = Image.objects.create(name='registry.example.com/example/service:1.0.0')
        delay.return_value = SimpleNamespace(id='image-task-id')

        response = self.client.post(reverse('image-rescan', args=[image.uuid]), format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'scheduled')
        self.assertEqual(response.data['image_status'], 'pending')
        self.assertEqual(response.data['task_id'], 'image-task-id')
        image.refresh_from_db()
        self.assertEqual(image.scan_status, 'pending')

    @patch('core.tasks.scan_image_with_grype.delay')
    def test_grype_rescan_reports_background_task_as_scheduled(self, delay):
        image = Image.objects.create(
            name='registry.example.com/example/service:1.0.0',
            sbom_data={'artifacts': []},
        )
        delay.return_value = SimpleNamespace(id='grype-task-id')

        response = self.client.post(reverse('image-rescan-grype', args=[image.uuid]), format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'scheduled')
        self.assertEqual(response.data['image_status'], 'pending')
        self.assertEqual(response.data['task_id'], 'grype-task-id')
        image.refresh_from_db()
        self.assertEqual(image.scan_status, 'pending')
