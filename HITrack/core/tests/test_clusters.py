from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Cluster, ClusterImage, ContainerRegistry, Image
from core.tasks import _select_image_registry


class ClusterApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='cluster-operator', password='test-password')
        self.user.groups.add(Group.objects.create(name='operator'))
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.registry = ContainerRegistry.objects.create(
            name='Test Registry',
            provider='acr',
            api_url='https://registry.example.test',
            login='scanner',
            password='secret',
        )
        self.cluster = Cluster.objects.create(name='test-cluster')

    def test_check_images_reports_existing_missing_and_matching_registry(self):
        existing_ref = 'public-registry.example.test/public/router:1.0.0'
        Image.objects.create(name=existing_ref, artifact_reference=existing_ref)

        response = self.client.post('/api/clusters/check-images/', {
            'images': '\n'.join([
                existing_ref,
                'registry.example.test/team/backend:1.2.3',
                'not an image',
            ]),
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['summary'], {
            'total': 3,
            'existing': 1,
            'missing': 1,
            'invalid': 1,
            'authenticated': 1,
        })
        private_row = response.data['results'][1]
        self.assertEqual(private_row['registry']['uuid'], str(self.registry.uuid))
        self.assertTrue(private_row['authenticated_scan'])

    @patch('core.tasks.generate_sbom_and_create_components.delay')
    def test_attach_creates_standalone_image_with_registry_and_queues_scan(self, delay):
        delay.return_value.id = 'scan-task-id'
        reference = 'registry.example.test/team/backend:1.2.3'

        response = self.client.post(f'/api/clusters/{self.cluster.uuid}/attach-images/', {
            'images': [reference],
            'create_references': [reference],
            'scan_references': [reference],
        }, format='json')

        self.assertEqual(response.status_code, 200)
        image = Image.objects.get(artifact_reference=reference)
        self.assertEqual(image.container_registry, self.registry)
        self.assertEqual(image.scan_status, 'pending')
        self.assertTrue(ClusterImage.objects.filter(cluster=self.cluster, image=image).exists())
        delay.assert_called_once_with(str(image.uuid), 'docker')
        self.assertEqual(response.data['results'][0]['status'], 'created')

    def test_existing_image_is_attached_without_duplication(self):
        reference = 'public-registry.example.test/system/pause:3.10.2'
        image = Image.objects.create(name=reference, artifact_reference=reference)

        first = self.client.post(f'/api/clusters/{self.cluster.uuid}/attach-images/', {'images': [reference]}, format='json')
        second = self.client.post(f'/api/clusters/{self.cluster.uuid}/attach-images/', {'images': [reference]}, format='json')

        self.assertEqual(first.data['results'][0]['status'], 'attached')
        self.assertEqual(second.data['results'][0]['status'], 'already_attached')
        self.assertEqual(ClusterImage.objects.filter(cluster=self.cluster, image=image).count(), 1)

    def test_deleting_cluster_preserves_images(self):
        image = Image.objects.create(name='public-registry.example.test/library/base:3.2.1')
        ClusterImage.objects.create(cluster=self.cluster, image=image, source_reference=image.name)

        response = self.client.delete(f'/api/clusters/{self.cluster.uuid}/')

        self.assertEqual(response.status_code, 204)
        self.assertTrue(Image.objects.filter(pk=image.pk).exists())

    def test_orphan_cleanup_preserves_cluster_images(self):
        reference = 'registry.example.test/team/web-api:2.3.4-build5'
        image = Image.objects.create(name=reference, artifact_reference=reference)
        ClusterImage.objects.create(cluster=self.cluster, image=image, source_reference=reference)

        response = self.client.post('/api/images/cleanup-orphaned/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['excluded_cluster_linked'], 1)
        self.assertTrue(Image.objects.filter(pk=image.pk).exists())

    def test_scan_registry_selection_uses_direct_standalone_registry(self):
        image = Image.objects.create(
            name='registry.example.test/team/frontend:1.2.3',
            container_registry=self.registry,
        )

        self.assertEqual(_select_image_registry(image), self.registry)
