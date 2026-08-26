import base64
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from core.utils import ecr


class ECRUtilityTests(SimpleTestCase):
    def setUp(self):
        self.registry = SimpleNamespace(
            api_url='123456789012.dkr.ecr.us-east-1.amazonaws.com',
            login='access-key',
            password='secret-key',
            token='session-token',
        )

    def test_registry_context_rejects_non_private_ecr_hosts(self):
        self.assertEqual(
            ecr._registry_context(self.registry),
            ('123456789012.dkr.ecr.us-east-1.amazonaws.com', '123456789012', 'us-east-1'),
        )
        invalid = SimpleNamespace(api_url='public.ecr.aws')
        with self.assertRaisesRegex(ValueError, 'private ECR hostname'):
            ecr._registry_context(invalid)

    @patch('core.utils.ecr.boto3.client')
    def test_client_uses_explicit_credential_and_region_fields(self, client):
        ecr._client(self.registry)
        client.assert_called_once_with(
            'ecr',
            region_name='us-east-1',
            aws_access_key_id='access-key',
            aws_secret_access_key='secret-key',
            aws_session_token='session-token',
        )

    @patch('core.utils.ecr._client')
    def test_repository_discovery_preserves_aws_pagination_token(self, client):
        client.return_value.describe_repositories.return_value = {
            'repositories': [{
                'repositoryName': 'team/api',
                'repositoryUri': '123456789012.dkr.ecr.us-east-1.amazonaws.com/team/api',
            }],
            'nextToken': 'next-token',
        }
        repositories, next_page = ecr.get_repositories(
            self.registry, page_size=50, last_repo='previous-token',
        )
        self.assertEqual(repositories[0][0], 'team/api')
        self.assertEqual(next_page, 'next-token')
        client.return_value.describe_repositories.assert_called_once_with(
            registryId='123456789012', maxResults=50, nextToken='previous-token',
        )

    @patch('core.utils.ecr._client')
    def test_tag_discovery_walks_pages_and_honors_limit(self, client):
        client.return_value.describe_images.side_effect = [
            {'imageDetails': [{'imageTags': ['3.0', '2.0']}], 'nextToken': 'next'},
            {'imageDetails': [{'imageTags': ['1.0']}]},
        ]
        self.assertEqual(
            list(ecr.get_tags(self.registry, 'team/api', limit=3)),
            ['3.0', '2.0', '1.0'],
        )
        self.assertEqual(client.return_value.describe_images.call_count, 2)

    @patch('core.utils.ecr._client')
    def test_manifest_and_digest_use_batch_get_image(self, client):
        client.return_value.batch_get_image.return_value = {
            'images': [{
                'imageManifest': json.dumps({'schemaVersion': 2}),
                'imageId': {'imageDigest': 'sha256:image'},
            }],
        }
        manifest, digest = ecr.get_manifest(self.registry, 'team/api', '1.0')
        resolved = ecr.get_image_digest(
            self.registry,
            '123456789012.dkr.ecr.us-east-1.amazonaws.com/team/api:1.0',
        )
        self.assertEqual(manifest, {'schemaVersion': 2})
        self.assertEqual(digest, 'sha256:image')
        self.assertEqual(resolved, 'sha256:image')

    @patch('core.utils.ecr.requests.get')
    @patch('core.utils.ecr._client')
    def test_blob_download_uses_presigned_url(self, client, get):
        client.return_value.get_download_url_for_layer.return_value = {
            'downloadUrl': 'https://signed.example/layer',
        }
        response = Mock(content=b'layer')
        response.raise_for_status.return_value = None
        get.return_value = response
        self.assertEqual(ecr.get_blob(self.registry, 'team/api', 'sha256:layer'), b'layer')
        get.assert_called_once_with('https://signed.example/layer', timeout=60)

    @patch('core.utils.ecr._client')
    def test_docker_credentials_decode_short_lived_authorization_token(self, client):
        encoded = base64.b64encode(b'AWS:temporary-password').decode()
        client.return_value.get_authorization_token.return_value = {
            'authorizationData': [{'authorizationToken': encoded}],
        }
        self.assertEqual(
            ecr.get_docker_login_credentials(self.registry),
            ('AWS', 'temporary-password'),
        )

    @patch('core.utils.ecr._client')
    def test_missing_manifest_and_authorization_token_are_explicit(self, client):
        client.return_value.batch_get_image.return_value = {'images': []}
        self.assertEqual(ecr.get_manifest(self.registry, 'team/api', 'missing'), (None, None))
        client.return_value.get_authorization_token.return_value = {'authorizationData': []}
        with self.assertRaisesRegex(RuntimeError, 'no Docker authorization token'):
            ecr.get_docker_login_credentials(self.registry)
