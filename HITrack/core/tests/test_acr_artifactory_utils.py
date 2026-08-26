from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase

from core.utils import acr, artifactory


def ok_response(payload=None, *, headers=None, text='', content=b'', links=None):
    response = Mock()
    response.status_code = 200
    response.headers = headers or {}
    response.text = text
    response.content = content
    response.links = links or {}
    response.json.return_value = payload if payload is not None else {}
    response.raise_for_status.return_value = None
    return response


class ACRUtilityTests(SimpleTestCase):
    @patch('core.utils.acr.requests.get')
    def test_catalog_parses_repository_urls_and_next_page(self, get):
        get.return_value = ok_response(
            {'repositories': ['team/api']},
            headers={'Link': '</v2/_catalog?n=1&last=team%2Fapi>; rel="next"'},
        )

        repositories, next_page = acr.get_repositories(
            'https://registry.azurecr.io', 'token', page_size=1,
        )

        self.assertEqual(repositories, [('team/api', 'registry.azurecr.io/team/api')])
        self.assertEqual(next_page, 'team%2Fapi')
        self.assertEqual(get.call_args.kwargs['timeout'], 30)

    @patch('core.utils.acr.requests.get')
    def test_paged_data_follows_relative_next_link(self, get):
        get.side_effect = [
            ok_response({'tags': ['1']}, links={'next': {'url': '/next'}}),
            ok_response({'tags': ['2']}),
        ]

        pages = list(acr.get_paged_data('https://registry.azurecr.io/start', 'token'))

        self.assertEqual(pages, [{'tags': ['1']}, {'tags': ['2']}])
        self.assertEqual(get.call_args_list[1].args[0], 'https://registry.azurecr.io/next')

    @patch('core.utils.acr.get_paged_data')
    def test_tags_honor_limit_and_missing_tags(self, paged):
        paged.return_value = iter([
            {'tags': ['3.0', '2.0', '1.0']},
            {'tags': None},
        ])
        self.assertEqual(
            list(acr.get_tags('https://registry.azurecr.io', 'token', 'team/api', limit=2)),
            ['3.0', '2.0'],
        )

    def test_helm_manifest_helpers_are_defensive(self):
        self.assertTrue(acr.is_helm_chart({
            'config': {'mediaType': 'application/vnd.cncf.helm.config.v1+json'},
        }))
        self.assertTrue(acr.is_helm_chart({'annotations': {'org.opencontainers.artifact.type': 'helm.chart'}}))
        self.assertFalse(acr.is_helm_chart({}))
        self.assertEqual(acr.get_chart_digest({
            'layers': [{'mediaType': 'application/tar+gzip', 'digest': 'sha256:chart'}],
        }), 'sha256:chart')
        self.assertIsNone(acr.get_chart_digest({'layers': []}))

    @patch('core.utils.acr.extract_images_from_chart_blob', return_value=['registry/app:1'])
    @patch('core.utils.acr.requests.get')
    def test_helm_blob_is_downloaded_and_parsed(self, get, extract):
        get.return_value = ok_response(content=b'chart')

        images = acr.get_helm_images(
            'https://registry.azurecr.io', 'token', 'charts/app', 'sha256:chart',
        )

        self.assertEqual(images, ['registry/app:1'])
        extract.assert_called_once_with(b'chart', 'charts/app:sha256:chart')
        self.assertEqual(get.call_args.kwargs['timeout'], 60)

    @patch('core.utils.acr.requests.get')
    def test_helm_blob_failure_is_actionable(self, get):
        get.side_effect = requests.ConnectionError('offline')
        with self.assertRaisesRegex(RuntimeError, 'Failed to download Helm chart'):
            acr.get_helm_images(
                'https://registry.azurecr.io', 'token', 'charts/app', 'sha256:chart',
            )

    @patch('core.utils.acr.requests.get')
    def test_digest_is_read_from_manifest_headers(self, get):
        get.return_value = ok_response(headers={'Docker-Content-Digest': 'sha256:image'})
        self.assertEqual(
            acr.get_acr_image_digest(
                'https://registry.azurecr.io', 'token',
                'registry.azurecr.io/team/api:1.0',
            ),
            'sha256:image',
        )


class ArtifactoryUtilityTests(SimpleTestCase):
    def test_basic_token_and_url_normalization(self):
        token = artifactory.get_bearer_token('https://unused', 'user', 'pass')
        self.assertEqual(artifactory._auth_headers(token)['Authorization'], f'Basic {token}')
        self.assertEqual(
            artifactory._docker_api_base('repo.example/artifactory/', 'docker-local'),
            'https://repo.example/artifactory/api/docker/docker-local',
        )
        with self.assertRaisesRegex(ValueError, 'not configured'):
            artifactory._normalize_base_url('')

    @patch('core.utils.artifactory.requests.get')
    def test_repository_rest_filters_invalid_rows(self, get):
        get.return_value = ok_response([
            {'key': 'docker-local', 'url': 'https://repo/artifactory/docker-local/'},
            {'key': '', 'url': 'ignored'},
            {'key': 'missing-url'},
        ])
        self.assertEqual(
            artifactory.get_repositories_rest('https://repo/artifactory', 'token'),
            [('docker-local', 'https://repo/artifactory/docker-local')],
        )

    @patch('core.utils.artifactory.requests.get')
    def test_catalog_and_tags_preserve_pagination(self, get):
        get.side_effect = [
            ok_response(
                {'repositories': ['team/api']},
                headers={'Link': '</next?last=team%2Fapi>; rel="next"'},
            ),
            ok_response({'tags': ['2.0']}, links={'next': {'url': 'https://repo/next'}}),
            ok_response({'tags': ['1.0']}),
        ]

        images, next_page = artifactory.get_catalog(
            'https://repo/artifactory', 'token', 'docker-local', page_size=1,
        )
        tags = list(artifactory.get_tags(
            'https://repo/artifactory/api/docker/docker-local', 'token', 'team/api',
        ))

        self.assertEqual(images, ['team/api'])
        self.assertEqual(next_page, 'team%2Fapi')
        self.assertEqual(tags, ['2.0', '1.0'])

    @patch('core.utils.artifactory.requests.get')
    def test_manifest_returns_digest_and_allows_oci(self, get):
        get.return_value = ok_response(
            {'schemaVersion': 2},
            headers={'Docker-Content-Digest': 'sha256:image'},
        )
        manifest, digest = artifactory.get_manifest(
            'https://repo/artifactory/api/docker/docker-local',
            'token', 'team/api', '1.0',
        )
        self.assertEqual(manifest['schemaVersion'], 2)
        self.assertEqual(digest, 'sha256:image')
        self.assertIn('application/vnd.oci.image.manifest.v1+json', get.call_args.kwargs['headers']['Accept'])

    @patch('core.utils.artifactory.requests.get')
    def test_helm_index_normalizes_relative_local_and_absolute_urls(self, get):
        get.return_value = ok_response(text='''
entries:
  app:
    - version: 1.0.0
      urls: [local://packages/app-1.0.0.tgz]
    - version: 2.0.0
      url: https://cdn.example/app-2.0.0.tgz
  ignored: not-a-list
''')
        self.assertEqual(
            artifactory.get_helm_index('https://repo/artifactory', 'token', 'helm-local'),
            [
                {'chart': 'app', 'version': '1.0.0', 'url': 'https://repo/artifactory/helm-local/packages/app-1.0.0.tgz'},
                {'chart': 'app', 'version': '2.0.0', 'url': 'https://cdn.example/app-2.0.0.tgz'},
            ],
        )

    @patch('core.utils.artifactory.extract_images_from_chart_blob', return_value=['repo/app:1'])
    @patch('core.utils.artifactory.requests.get')
    def test_native_and_oci_helm_downloads_use_shared_parser(self, get, extract):
        get.side_effect = [ok_response(content=b'native'), ok_response(content=b'oci')]

        native = artifactory.get_helm_images_from_native_chart(
            'unused', 'token', 'https://repo/chart.tgz',
        )
        oci = artifactory.get_helm_images(
            'https://repo/artifactory/api/docker/helm-local',
            'token', 'charts/app', 'sha256:chart',
        )

        self.assertEqual(native, ['repo/app:1'])
        self.assertEqual(oci, ['repo/app:1'])
        self.assertEqual(extract.call_count, 2)

    @patch('core.utils.artifactory._digest_from_docker_pull')
    @patch('core.utils.artifactory.requests.get')
    def test_path_style_digest_prefers_artifactory_api(self, get, docker_digest):
        get.return_value = ok_response(headers={'Docker-Content-Digest': 'sha256:image'})
        digest = artifactory.get_artifactory_image_digest(
            'https://repo.example/artifactory', 'token',
            'repo.example/artifactory/docker-local/team/api:1.0',
        )
        self.assertEqual(digest, 'sha256:image')
        docker_digest.assert_not_called()
