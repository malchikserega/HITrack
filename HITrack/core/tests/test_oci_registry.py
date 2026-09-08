import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

from core.models import ContainerRegistry
from core.utils.oci_registry import get_manifest, get_repositories, get_tags
from core.utils.registry import get_docker_login_credentials


def response(status, payload=None, headers=None, url='https://registry.example.test/v2/'):
    result = Mock()
    result.status_code = status
    result.headers = headers or {}
    result.url = url
    result.links = {}
    result.content = json.dumps(payload or {}).encode()
    result.json.return_value = payload or {}
    result.raise_for_status.side_effect = None if status < 400 else RuntimeError(f'HTTP {status}')
    return result


class OCIRegistryClientTests(SimpleTestCase):
    def setUp(self):
        self.registry = SimpleNamespace(
            api_url='https://registry.example.test',
            login='scanner',
            password='secret',
            token='',
        )

    @patch('core.utils.oci_registry.requests.get')
    @patch('core.utils.oci_registry.requests.request')
    def test_catalog_exchanges_bearer_challenge_with_catalog_scope(self, request, get):
        request.side_effect = [
            response(401, headers={
                'WWW-Authenticate': 'Bearer realm="https://auth.example.test/token",service="registry.example.test"'
            }),
            response(200, {'repositories': ['team/api']}),
        ]
        get.return_value = response(200, {'token': 'scoped-token'})

        repositories, next_page = get_repositories(self.registry, page_size=25)

        self.assertEqual(repositories, [('team/api', 'registry.example.test/team/api')])
        self.assertIsNone(next_page)
        self.assertEqual(get.call_args.kwargs['params']['scope'], 'registry:catalog:*')
        self.assertEqual(
            request.call_args_list[1].kwargs['headers']['Authorization'],
            'Bearer scoped-token',
        )

    @patch('core.utils.oci_registry.requests.get')
    @patch('core.utils.oci_registry.requests.request')
    def test_tags_use_repository_pull_scope(self, request, get):
        request.side_effect = [
            response(401, headers={
                'WWW-Authenticate': 'Bearer realm="https://auth.example.test/token",service="registry.example.test"'
            }),
            response(200, {'tags': ['1.0.0', 'latest']}),
        ]
        get.return_value = response(200, {'access_token': 'pull-token'})

        self.assertEqual(list(get_tags(self.registry, 'team/api', limit=10)), ['1.0.0', 'latest'])
        self.assertEqual(get.call_args.kwargs['params']['scope'], 'repository:team/api:pull')

    @patch('core.utils.oci_registry._request')
    def test_manifest_accepts_oci_and_docker_media_types(self, request):
        request.return_value = response(
            200,
            {'schemaVersion': 2},
            headers={'Docker-Content-Digest': 'sha256:abc'},
        )

        manifest, digest = get_manifest(self.registry, 'team/api', '1.0.0')

        self.assertEqual(manifest['schemaVersion'], 2)
        self.assertEqual(digest, 'sha256:abc')
        self.assertIn('application/vnd.oci.image.manifest.v1+json', request.call_args.kwargs['headers']['Accept'])


class RegistryDockerCredentialsTests(TestCase):
    def test_acr_uses_configured_service_principal_credentials(self):
        registry = ContainerRegistry(
            name='acr', provider='acr', api_url='https://example.azurecr.io',
            login='client-id', password='client-secret',
        )
        self.assertEqual(
            get_docker_login_credentials(registry),
            ('client-id', 'client-secret'),
        )

    def test_harbor_can_use_token_as_password(self):
        registry = ContainerRegistry(
            name='harbor', provider='harbor', api_url='https://harbor.example.test',
            login='robot$scanner', token='robot-token',
        )
        self.assertEqual(
            get_docker_login_credentials(registry),
            ('robot$scanner', 'robot-token'),
        )
