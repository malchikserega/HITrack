from types import SimpleNamespace
from unittest.mock import call, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Cluster, ClusterImage, ContainerRegistry, Image
from core.services.clusters import inspect_image_references
from core.tasks import _select_image_registry


class ClusterApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='cluster-operator', password='test-password')
        self.user.groups.add(Group.objects.create(name='operator'))
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.registry = ContainerRegistry.objects.create(
            name='NLP ACR',
            provider='acr',
            api_url='https://nlpapp0336cre.azurecr.io',
            login='scanner',
            password='secret',
        )
        self.cluster = Cluster.objects.create(name='aks-production')

    def test_check_images_reports_existing_missing_and_matching_registry(self):
        existing_ref = 'docker.io/openziti/ziti-router:1.7.0'
        Image.objects.create(name=existing_ref, artifact_reference=existing_ref)

        response = self.client.post('/api/clusters/check-images/', {
            'images': '\n'.join([
                existing_ref,
                'nlpapp0336cre.azurecr.io/litellm/backend:v1.94.0',
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

    def test_check_images_batches_existing_image_lookup(self):
        references = [f'registry.example.com/team/app:{index}' for index in range(25)]
        Image.objects.bulk_create([
            Image(name=reference, artifact_reference=reference)
            for reference in references
        ])

        with self.assertNumQueries(2):
            rows = inspect_image_references(references)

        self.assertEqual(len(rows), 25)
        self.assertTrue(all(row['exists'] for row in rows))

    @patch('core.tasks.generate_sbom_and_create_components.delay')
    def test_attach_creates_standalone_image_with_registry_and_queues_scan(self, delay):
        delay.return_value.id = 'scan-task-id'
        reference = 'nlpapp0336cre.azurecr.io/litellm/backend:v1.94.0'

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
        reference = 'mcr.microsoft.com/oss/v2/kubernetes/pause:3.10.2'
        image = Image.objects.create(name=reference, artifact_reference=reference)

        first = self.client.post(f'/api/clusters/{self.cluster.uuid}/attach-images/', {'images': [reference]}, format='json')
        second = self.client.post(f'/api/clusters/{self.cluster.uuid}/attach-images/', {'images': [reference]}, format='json')

        self.assertEqual(first.data['results'][0]['status'], 'attached')
        self.assertEqual(second.data['results'][0]['status'], 'already_attached')
        self.assertEqual(ClusterImage.objects.filter(cluster=self.cluster, image=image).count(), 1)

    def test_deleting_cluster_preserves_images(self):
        image = Image.objects.create(name='docker.io/library/alpine:3.22')
        ClusterImage.objects.create(cluster=self.cluster, image=image, source_reference=image.name)

        response = self.client.delete(f'/api/clusters/{self.cluster.uuid}/')

        self.assertEqual(response.status_code, 204)
        self.assertTrue(Image.objects.filter(pk=image.pk).exists())

    def test_orphan_cleanup_preserves_cluster_images(self):
        reference = 'nlpapp0336cre.azurecr.io/mpt-audit/web-api:6.0.9-g12c74bed'
        image = Image.objects.create(name=reference, artifact_reference=reference)
        ClusterImage.objects.create(cluster=self.cluster, image=image, source_reference=reference)

        response = self.client.post('/api/images/cleanup-orphaned/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['excluded_cluster_linked'], 1)
        self.assertTrue(Image.objects.filter(pk=image.pk).exists())

    def test_scan_registry_selection_uses_direct_standalone_registry(self):
        image = Image.objects.create(
            name='nlpapp0336cre.azurecr.io/litellm/ui:v1.94.0',
            container_registry=self.registry,
        )

        self.assertEqual(_select_image_registry(image), self.registry)

    def test_contents_returns_durable_scan_progress(self):
        statuses = ['success', 'error', 'pending', 'none']
        for index, scan_status in enumerate(statuses):
            image = Image.objects.create(name=f'registry.example.com/app:{index}', scan_status=scan_status)
            ClusterImage.objects.create(cluster=self.cluster, image=image, source_reference=image.name)

        response = self.client.get(f'/api/clusters/{self.cluster.uuid}/contents/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['progress'], {
            'state': 'running',
            'total': 4,
            'completed': 2,
            'remaining': 2,
            'pending': 1,
            'in_process': 0,
            'success': 1,
            'error': 1,
            'not_started': 1,
            'active': True,
            'percent': 50.0,
        })
        self.assertEqual(response.data['count'], 4)

    def test_contents_is_paginated_and_has_constant_query_count(self):
        images = [
            Image(name=f'registry.example.com/app:{index:03d}')
            for index in range(55)
        ]
        Image.objects.bulk_create(images)
        ClusterImage.objects.bulk_create([
            ClusterImage(cluster=self.cluster, image=image, source_reference=image.name)
            for image in images
        ])

        with self.assertNumQueries(3):
            response = self.client.get(
                f'/api/clusters/{self.cluster.uuid}/contents/?page=3&page_size=20'
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 55)
        self.assertEqual(len(response.data['images']), 15)
        self.assertIsNone(response.data['next'])
        self.assertIsNotNone(response.data['previous'])

    def test_scan_progress_does_not_load_cluster_images(self):
        images = [Image(name=f'registry.example.com/app:{index}') for index in range(20)]
        Image.objects.bulk_create(images)
        ClusterImage.objects.bulk_create([
            ClusterImage(cluster=self.cluster, image=image, source_reference=image.name)
            for image in images
        ])

        with self.assertNumQueries(1):
            response = self.client.get(f'/api/clusters/{self.cluster.uuid}/scan-progress/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total'], 20)

    @patch('core.tasks.generate_sbom_and_create_components.delay')
    def test_scan_all_queues_every_non_active_image_and_returns_progress(self, delay):
        delay.side_effect = [SimpleNamespace(id='task-1'), SimpleNamespace(id='task-2')]
        images = [
            Image.objects.create(name='registry.example.com/api:1', scan_status='success'),
            Image.objects.create(name='registry.example.com/worker:1', scan_status='none'),
            Image.objects.create(name='registry.example.com/running:1', scan_status='in_process'),
        ]
        for image in images:
            ClusterImage.objects.create(cluster=self.cluster, image=image, source_reference=image.name)

        response = self.client.post(f'/api/clusters/{self.cluster.uuid}/scan-all/', {}, format='json')

        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(response.data['scheduled']), 2)
        self.assertEqual(response.data['already_running'], [str(images[2].uuid)])
        self.assertEqual(response.data['progress']['total'], 3)
        self.assertEqual(response.data['progress']['remaining'], 3)
        self.assertEqual(response.data['progress']['pending'], 2)
        self.assertEqual(response.data['progress']['in_process'], 1)
        self.assertTrue(response.data['progress']['active'])
        delay.assert_has_calls([
            call(image_uuid=str(images[0].uuid), art_type='docker'),
            call(image_uuid=str(images[1].uuid), art_type='docker'),
        ], any_order=True)
