"""AWS ECR adapter using the native API (ECR does not expose v2 catalog)."""

from __future__ import annotations

import base64
import json
import re
from typing import Generator, Optional, Tuple

import boto3
import requests


_PRIVATE_ECR_HOST = re.compile(
    r"^(?P<account>\d+)\.dkr\.ecr(?:-fips)?\.(?P<region>[a-z0-9-]+)\.amazonaws\.com(?:\.cn)?$"
)


def _registry_context(registry):
    host = str(registry.api_url or '').split('://')[-1].strip().strip('/').split('/')[0]
    match = _PRIVATE_ECR_HOST.match(host)
    if not match:
        raise ValueError(
            'AWS ECR api_url must be a private ECR hostname such as '
            '123456789012.dkr.ecr.us-east-1.amazonaws.com'
        )
    return host, match.group('account'), match.group('region')


def _client(registry):
    _host, _account, region = _registry_context(registry)
    kwargs = {'region_name': region}
    if registry.login and registry.password:
        kwargs.update({
            'aws_access_key_id': registry.login,
            'aws_secret_access_key': registry.password,
        })
        if registry.token:
            kwargs['aws_session_token'] = registry.token
    return boto3.client('ecr', **kwargs)


def get_repositories(registry, page_size: int = 100, last_repo: str = None) -> Tuple[list, Optional[str]]:
    _host, account, _region = _registry_context(registry)
    kwargs = {'registryId': account, 'maxResults': min(max(int(page_size), 1), 1000)}
    if last_repo:
        kwargs['nextToken'] = last_repo
    payload = _client(registry).describe_repositories(**kwargs)
    repositories = [
        (row['repositoryName'], row['repositoryUri'])
        for row in payload.get('repositories', [])
    ]
    return repositories, payload.get('nextToken')


def get_tags(registry, repo: str, limit: int = None) -> Generator[str, None, None]:
    client = _client(registry)
    token = None
    count = 0
    while True:
        kwargs = {
            'repositoryName': repo,
            'filter': {'tagStatus': 'TAGGED'},
            'maxResults': min(max(int(limit or 1000), 1), 1000),
        }
        if token:
            kwargs['nextToken'] = token
        payload = client.describe_images(**kwargs)
        for detail in payload.get('imageDetails', []):
            for tag in detail.get('imageTags', []):
                yield tag
                count += 1
                if limit is not None and count >= limit:
                    return
        token = payload.get('nextToken')
        if not token:
            return


def get_manifest(registry, repo: str, tag: str):
    payload = _client(registry).batch_get_image(
        repositoryName=repo,
        imageIds=[{'imageTag': tag}],
        acceptedMediaTypes=[
            'application/vnd.oci.image.manifest.v1+json',
            'application/vnd.docker.distribution.manifest.v2+json',
            'application/vnd.docker.distribution.manifest.list.v2+json',
        ],
    )
    images = payload.get('images') or []
    if not images:
        return None, None
    image = images[0]
    return json.loads(image['imageManifest']), image.get('imageId', {}).get('imageDigest')


def get_image_digest(registry, image_ref: str) -> Optional[str]:
    host, _account, _region = _registry_context(registry)
    value = image_ref.split(f'{host}/', 1)[-1]
    if ':' in value.rsplit('/', 1)[-1]:
        repo, tag = value.rsplit(':', 1)
    else:
        repo, tag = value, 'latest'
    _manifest, digest = get_manifest(registry, repo, tag)
    return digest


def get_blob(registry, repo: str, digest: str) -> bytes:
    payload = _client(registry).get_download_url_for_layer(
        repositoryName=repo,
        layerDigest=digest,
    )
    response = requests.get(payload['downloadUrl'], timeout=60)
    response.raise_for_status()
    return response.content


def get_docker_login_credentials(registry) -> Tuple[str, str]:
    _host, account, _region = _registry_context(registry)
    payload = _client(registry).get_authorization_token(registryIds=[account])
    entries = payload.get('authorizationData') or []
    if not entries:
        raise RuntimeError('AWS ECR returned no Docker authorization token')
    decoded = base64.b64decode(entries[0]['authorizationToken']).decode()
    username, password = decoded.split(':', 1)
    return username, password
