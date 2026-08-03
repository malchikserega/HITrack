from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from core.models import Repository, RepositoryTag


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
