from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, TestCase

from core.models import ContainerRegistry, Repository
from core.tasks import scan_repository_tags
from core.utils import acr, artifactory


def successful_response(payload, headers=None):
    response = Mock()
    response.status_code = 200
    response.headers = headers or {}
    response.links = {}
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class ACRProviderContractTests(SimpleTestCase):
    @patch('core.utils.acr.requests.get')
    def test_username_password_token_exchange_uses_official_data_plane_contract(self, get):
        get.return_value = successful_response({'access_token': 'acr-token'})

        token = acr.get_bearer_token(
            'https://registry.azurecr.io/', 'service-principal', 'secret'
        )

        self.assertEqual(token, 'acr-token')
        url = get.call_args.args[0]
        self.assertIn('/oauth2/token?', url)
        self.assertIn('api-version=2021-07-01', url)
        self.assertIn('service=registry.azurecr.io', url)
        self.assertEqual(get.call_args.kwargs['timeout'], 30)
        self.assertTrue(get.call_args.kwargs['headers']['Authorization'].startswith('Basic '))

    @patch('core.utils.acr.requests.get')
    def test_manifest_requests_multi_arch_oci_and_docker_formats(self, get):
        get.return_value = successful_response(
            {'schemaVersion': 2},
            {'Docker-Content-Digest': 'sha256:abc'},
        )

        manifest, digest = acr.get_manifest(
            'https://registry.azurecr.io', 'token', 'team/api', '1.0.0'
        )

        self.assertEqual(manifest['schemaVersion'], 2)
        self.assertEqual(digest, 'sha256:abc')
        accept = get.call_args.kwargs['headers']['Accept']
        self.assertIn('application/vnd.oci.image.index.v1+json', accept)
        self.assertIn('application/vnd.docker.distribution.manifest.list.v2+json', accept)

    @patch('core.utils.acr.requests.get')
    def test_tag_connectivity_failure_is_not_silently_reported_as_empty(self, get):
        error = requests.ConnectionError('unreachable')
        error.response = None
        get.side_effect = error

        with self.assertRaises(requests.ConnectionError):
            list(acr.get_tags('https://registry.azurecr.io', 'token', 'team/api'))


class JFrogProviderContractTests(SimpleTestCase):
    @patch('core.utils.artifactory.requests.get')
    def test_tag_failure_is_not_silently_reported_as_empty(self, get):
        get.side_effect = requests.ConnectionError('unreachable')

        with self.assertRaisesRegex(RuntimeError, 'tag request failed'):
            list(artifactory.get_tags(
                'https://repo.example.test/artifactory/api/docker/docker-local',
                'basic-token',
                'team/api',
            ))

    @patch('core.utils.artifactory.requests.get')
    def test_manifest_failure_is_propagated_to_repository_scan(self, get):
        get.side_effect = requests.HTTPError('unauthorized')

        with self.assertRaisesRegex(RuntimeError, 'manifest request failed'):
            artifactory.get_manifest(
                'https://repo.example.test/artifactory/api/docker/docker-local',
                'basic-token',
                'team/api',
                '1.0.0',
            )


class RepositoryDiscoveryFailureStateTests(TestCase):
    @patch('core.utils.registry.get_tags', side_effect=RuntimeError('registry unavailable'))
    def test_acr_failure_sets_repository_error_instead_of_success_with_zero_tags(self, _get_tags):
        registry = ContainerRegistry.objects.create(
            name='acr', provider='acr', api_url='https://registry.azurecr.io',
        )
        repository = Repository.objects.create(
            name='team/api', container_registry=registry, status=True,
        )

        result = scan_repository_tags.run(str(repository.uuid))

        repository.refresh_from_db()
        self.assertEqual(repository.scan_status, 'error')
        self.assertEqual(result['status'], 'error')

    @patch('core.utils.registry.get_tags', side_effect=RuntimeError('registry unavailable'))
    def test_jfrog_failure_sets_repository_error(self, _get_tags):
        registry = ContainerRegistry.objects.create(
            name='jfrog', provider='jfrog',
            api_url='https://repo.example.test/artifactory',
        )
        repository = Repository.objects.create(
            name='docker-local/team/api', repo_key='docker-local',
            repository_type='docker', container_registry=registry, status=True,
        )

        result = scan_repository_tags.run(str(repository.uuid))

        repository.refresh_from_db()
        self.assertEqual(repository.scan_status, 'error')
        self.assertEqual(result['status'], 'error')
