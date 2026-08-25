from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import (
    Component,
    ComponentVersion,
    ComponentVersionVulnerability,
    Image,
    Repository,
    RepositoryTag,
    Vulnerability,
)


class OrphanCleanupTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='operator', password='test-password')
        user.groups.add(Group.objects.create(name='operator'))
        self.client = APIClient()
        self.client.force_authenticate(user)

    def test_image_cleanup_only_deletes_unlinked_inactive_registry_images(self):
        orphan = Image.objects.create(
            name='registry.example/orphan:1', artifact_reference='registry.example/orphan:1',
            scan_status='success',
        )
        standalone = Image.objects.create(name='manual-image:1', scan_status='success')
        active = Image.objects.create(
            name='registry.example/active:1', artifact_reference='registry.example/active:1',
            scan_status='in_process',
        )
        linked = Image.objects.create(
            name='registry.example/linked:1', artifact_reference='registry.example/linked:1',
            scan_status='success',
        )
        repository = Repository.objects.create(name='repo', repository_type='docker')
        tag = RepositoryTag.objects.create(repository=repository, tag='latest')
        linked.repository_tags.add(tag)

        preview = self.client.get('/api/images/cleanup-orphaned/')
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.data, {
            'orphaned': 1, 'excluded_standalone': 1, 'excluded_active_scans': 1,
        })

        cleanup = self.client.post('/api/images/cleanup-orphaned/')
        self.assertEqual(cleanup.status_code, 200)
        self.assertEqual(cleanup.data['deleted'], 1)
        self.assertFalse(Image.objects.filter(pk=orphan.pk).exists())
        self.assertTrue(Image.objects.filter(pk=standalone.pk).exists())
        self.assertTrue(Image.objects.filter(pk=active.pk).exists())
        self.assertTrue(Image.objects.filter(pk=linked.pk).exists())

    def test_vulnerability_cleanup_uses_current_image_reachability(self):
        component = Component.objects.create(name='package', type='npm')
        orphan_version = ComponentVersion.objects.create(component=component, version='1')
        linked_version = ComponentVersion.objects.create(component=component, version='2')
        linked_version.images.add(Image.objects.create(name='current:1'))
        orphan = Vulnerability.objects.create(vulnerability_id='CVE-ORPHAN', severity='HIGH')
        linked = Vulnerability.objects.create(vulnerability_id='CVE-LINKED', severity='HIGH')
        ComponentVersionVulnerability.objects.create(
            component_version=orphan_version, vulnerability=orphan,
        )
        ComponentVersionVulnerability.objects.create(
            component_version=linked_version, vulnerability=linked,
        )

        preview = self.client.get('/api/vulnerabilities/cleanup-orphaned/')
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.data['orphaned'], 1)
        cleanup = self.client.post('/api/vulnerabilities/cleanup-orphaned/')
        self.assertEqual(cleanup.data['deleted'], 1)
        self.assertFalse(Vulnerability.objects.filter(pk=orphan.pk).exists())
        self.assertTrue(Vulnerability.objects.filter(pk=linked.pk).exists())
