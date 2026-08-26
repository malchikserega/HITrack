from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from core.utils import registry


def configured(provider, **overrides):
    values = {
        'provider': provider,
        'pk': 'registry-id',
        'api_url': 'https://registry.example',
        'login': 'user',
        'password': 'password',
        'token': '',
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class RegistryCredentialDispatchTests(SimpleTestCase):
    @patch('core.utils.ecr.get_docker_login_credentials', return_value=('AWS', 'short-lived'))
    def test_ecr_docker_credentials_are_dynamic(self, credentials):
        value = registry.get_docker_login_credentials(configured('ecr'))
        self.assertEqual(value, ('AWS', 'short-lived'))
        credentials.assert_called_once()

    def test_static_registry_credentials_are_provider_appropriate(self):
        self.assertEqual(
            registry.get_docker_login_credentials(configured('jfrog')),
            ('user', 'password'),
        )
        self.assertEqual(
            registry.get_docker_login_credentials(configured('harbor', password='', token='robot-token')),
            ('user', 'robot-token'),
        )
        self.assertIsNone(registry.get_docker_login_credentials(None))

    @patch('core.utils.registry.get_bearer_token', return_value='acr-token')
    def test_acr_token_fallback_uses_official_docker_username(self, token):
        value = registry.get_docker_login_credentials(
            configured('acr', login='', password='', token=''),
        )
        self.assertEqual(value, ('00000000-0000-0000-0000-000000000000', 'acr-token'))


class RegistryOperationDispatchTests(SimpleTestCase):
    @patch('core.utils.artifactory.get_repositories_rest')
    @patch('core.utils.registry.get_bearer_token', return_value='basic')
    def test_jfrog_repository_discovery_combines_docker_and_helm(self, _token, get_repositories):
        get_repositories.side_effect = [
            [('docker-local', 'docker-url')],
            [('helm-local', 'helm-url')],
        ]
        repositories, next_page = registry.get_repositories(configured('jfrog'))
        self.assertEqual(repositories, [
            ('docker-local', 'docker-url', 'docker'),
            ('helm-local', 'helm-url', 'helm'),
        ])
        self.assertIsNone(next_page)

    @patch('core.utils.acr.get_repositories', return_value=([('app', 'url')], None))
    @patch('core.utils.registry.get_bearer_token', return_value='acr-token')
    def test_acr_repository_dispatch(self, _token, get_repositories):
        self.assertEqual(
            registry.get_repositories(configured('acr'), page_size=5),
            ([('app', 'url')], None),
        )
        get_repositories.assert_called_once_with(
            'https://registry.example', 'acr-token', page_size=5, last_repo=None,
        )

    @patch('core.utils.oci_registry.get_repositories', return_value=([('app', 'url')], None))
    def test_harbor_repository_dispatch(self, get_repositories):
        self.assertEqual(
            registry.get_repositories(configured('harbor')),
            ([('app', 'url')], None),
        )
        get_repositories.assert_called_once()

    @patch('core.utils.ecr.get_repositories', return_value=([('app', 'url')], 'next'))
    def test_ecr_repository_dispatch(self, get_repositories):
        self.assertEqual(
            registry.get_repositories(configured('ecr')),
            ([('app', 'url')], 'next'),
        )

    @patch('core.utils.oci_registry.get_tags', return_value=iter(['1.0']))
    def test_generic_oci_tag_dispatch(self, get_tags):
        self.assertEqual(list(registry.get_tags(configured('harbor'), 'team/api')), ['1.0'])
        get_tags.assert_called_once()

    @patch('core.utils.artifactory.get_manifest', return_value=({'schemaVersion': 2}, 'sha256:x'))
    @patch('core.utils.registry.get_bearer_token', return_value='basic')
    def test_jfrog_manifest_dispatch_uses_repo_specific_docker_api(self, _token, get_manifest):
        value = registry.get_manifest(
            configured('jfrog'), 'docker-local', '1.0', image_name='team/api',
        )
        self.assertEqual(value[1], 'sha256:x')
        self.assertIn('/api/docker/docker-local', get_manifest.call_args.args[0])
        self.assertEqual(get_manifest.call_args.args[2:], ('team/api', '1.0'))

    @patch('core.utils.ecr.get_image_digest', return_value='sha256:ecr')
    def test_ecr_digest_dispatch(self, get_digest):
        self.assertEqual(
            registry.get_image_digest(configured('ecr'), 'registry/team/api:1'),
            'sha256:ecr',
        )

    def test_reference_helpers_cover_path_and_subdomain_formats(self):
        self.assertEqual(
            registry.image_ref_repo_key(
                'https://repo.example/artifactory',
                'repo.example/artifactory/docker-local/team/api:1.0',
            ),
            'docker-local',
        )
        self.assertEqual(
            registry.build_fallback_image_ref_from_url(
                'https://mirror.example/docker', 'source.example/team/api:1.0',
            ),
            'mirror.example/docker/team/api:1.0',
        )
        self.assertEqual(
            registry.to_docker_pull_ref(
                'repo.example/artifactory/docker-local/team/api:1.0',
            ),
            'docker-local.repo.example/team/api:1.0',
        )
        self.assertEqual(registry.to_docker_pull_ref('harbor.example/team/api:1'), 'harbor.example/team/api:1')
