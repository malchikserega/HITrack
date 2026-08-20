from unittest.mock import patch

from django.test import TestCase

from core.models import ContainerRegistry, Repository, RepositoryTag
from core.tasks import _resolve_helm_image_location


class RegistryFallbackResolutionTests(TestCase):
    def setUp(self):
        self.registry = ContainerRegistry.objects.create(
            name='jfrog-primary',
            provider='jfrog',
            api_url='https://jfrog.example.test/artifactory',
            image_fallback_repositories=[],
        )
        self.repository = Repository.objects.create(
            name='helm-local/platform-chart',
            url='https://jfrog.example.test/artifactory/helm-local/platform-chart',
            repo_key='helm-local',
            repository_type='helm',
            container_registry=self.registry,
            status=True,
        )
        self.tag = RepositoryTag.objects.create(
            repository=self.repository,
            tag='1.0.0',
        )

    @patch('core.utils.registry.get_image_digest', return_value=None)
    def test_empty_registry_configuration_does_not_use_hidden_fallback(
        self,
        get_image_digest,
    ):
        legacy_registry = ContainerRegistry.objects.create(
            name='legacy-fallback-auth',
            provider='acr',
            api_url='https://legacy.example.test',
        )
        legacy_repository = Repository.objects.create(
            name='legacy/docker-local',
            url='https://legacy.example.test/docker-local',
            repository_type='docker',
            container_registry=legacy_registry,
        )
        # Preserve historical data while proving it is no longer an active
        # fallback source when the registry-level policy is empty.
        self.repository.image_fallback_repositories.add(legacy_repository)

        resolved_ref, digest, artifact_ref, error = _resolve_helm_image_location(
            self.repository,
            self.tag,
            self.registry,
            'unavailable.example.test/team/application:2.4.0',
        )

        self.assertIsNone(resolved_ref)
        self.assertIsNone(digest)
        self.assertIsNone(artifact_ref)
        self.assertIn('Could not resolve Helm child image', error)
        self.assertGreater(get_image_digest.call_count, 0)
        self.assertEqual(
            {call.args[0].uuid for call in get_image_digest.call_args_list},
            {self.registry.uuid},
        )
        self.assertEqual(
            list(self.repository.image_fallback_repositories.values_list('uuid', flat=True)),
            [legacy_repository.uuid],
        )

    @patch('core.utils.registry.get_image_digest')
    def test_configured_registry_fallback_uses_its_auth_registry(
        self,
        get_image_digest,
    ):
        auth_registry = ContainerRegistry.objects.create(
            name='acr-fallback-auth',
            provider='acr',
            api_url='https://fallback.example.test',
        )
        self.registry.image_fallback_repositories = [{
            'url': 'fallback.example.test/docker-local',
            'name': 'docker-local',
            'registry_uuid': str(auth_registry.uuid),
        }]
        self.registry.save(update_fields=['image_fallback_repositories'])
        expected_digest = f"sha256:{'a' * 64}"

        def resolve_digest(registry, image_ref):
            if registry.uuid == auth_registry.uuid:
                self.assertEqual(
                    image_ref,
                    'fallback.example.test/docker-local/team/application:2.4.0',
                )
                return expected_digest
            return None

        get_image_digest.side_effect = resolve_digest

        resolved_ref, digest, artifact_ref, error = _resolve_helm_image_location(
            self.repository,
            self.tag,
            self.registry,
            'unavailable.example.test/team/application:2.4.0',
        )

        self.assertEqual(
            resolved_ref,
            'fallback.example.test/docker-local/team/application:2.4.0',
        )
        self.assertEqual(digest, expected_digest)
        self.assertEqual(artifact_ref, resolved_ref)
        self.assertIsNone(error)
        self.assertTrue(
            any(call.args[0].uuid == auth_registry.uuid for call in get_image_digest.call_args_list)
        )
