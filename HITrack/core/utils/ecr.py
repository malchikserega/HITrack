"""
Amazon Elastic Container Registry (ECR) Scanner

This module provides utility functions for working with Amazon ECR.
It handles authentication via AWS credentials, data retrieval, and
basic operations with ECR using the Docker Registry HTTP API V2.

Authentication uses boto3 to obtain ECR auth tokens; all subsequent
API calls use standard Docker Registry V2 endpoints (the same protocol
that ACR and other OCI-compliant registries speak).
"""

# Standard library imports
import base64
import logging
import re
from typing import Generator, List, Optional, Tuple

# Third-party imports
import requests

from .helm import extract_images_from_chart_blob

logger = logging.getLogger(__name__)

# Configuration
PAGE_SIZE = 500


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_region(api_url: str) -> str:
    """
    Extract AWS region from an ECR URL.

    Supports formats:
      - https://123456789012.dkr.ecr.us-east-1.amazonaws.com
      - 123456789012.dkr.ecr.eu-west-1.amazonaws.com
    """
    host = api_url.strip().rstrip('/')
    if '://' in host:
        host = host.split('://', 1)[1]
    # ECR hostnames: <account>.dkr.ecr.<region>.amazonaws.com
    match = re.search(r'\.dkr\.ecr\.([a-z0-9-]+)\.amazonaws\.com', host)
    if match:
        return match.group(1)
    raise ValueError(
        f"Cannot extract AWS region from ECR URL: {api_url}. "
        "Expected format: https://<account_id>.dkr.ecr.<region>.amazonaws.com"
    )


def _normalize_base_url(api_url: Optional[str]) -> str:
    """Ensure api_url has https:// prefix and no trailing slash."""
    if not api_url or not api_url.strip():
        raise ValueError("ECR registry API URL is not configured")
    base = api_url.strip().rstrip('/')
    if not base.startswith('http://') and not base.startswith('https://'):
        base = f"https://{base}"
    return base


def _auth_headers(token: str) -> dict:
    """Build Authorization header for ECR (Basic auth with AWS token)."""
    return {"Authorization": f"Basic {token}"}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def get_bearer_token(api_url: str, login: str, password: str) -> str:
    """
    Get an ECR auth token using AWS credentials.

    Uses boto3 to call ecr:GetAuthorizationToken. The returned token is
    a base64-encoded 'AWS:<password>' string; we return the full base64
    value for use as a Basic auth token.

    Args:
        api_url (str): ECR registry URL (e.g. https://123456789012.dkr.ecr.us-east-1.amazonaws.com)
        login (str): AWS Access Key ID
        password (str): AWS Secret Access Key

    Returns:
        str: Base64-encoded auth token for Basic auth.

    Raises:
        Exception: If the token request fails.
    """
    try:
        import boto3

        region = _extract_region(api_url)
        client = boto3.client(
            'ecr',
            region_name=region,
            aws_access_key_id=login,
            aws_secret_access_key=password,
        )
        response = client.get_authorization_token()
        auth_data = response['authorizationData']
        if not auth_data:
            raise RuntimeError("ECR returned empty authorizationData")
        # Token is base64('AWS:<password>'); return raw base64 for Basic auth
        return auth_data[0]['authorizationToken']
    except Exception as e:
        logger.error("Failed to get ECR bearer token: %s", e)
        raise


# ---------------------------------------------------------------------------
# Repository discovery
# ---------------------------------------------------------------------------

def get_repositories(api_url: str, token: str, page_size: int = 100, last_repo: str = None) -> Tuple[list, str]:
    """
    Get repositories from ECR with pagination using Docker V2 _catalog.

    Args:
        api_url (str): ECR API URL
        token (str): Auth token (base64 Basic auth)
        page_size (int): Number of repositories to return (default: 100)
        last_repo (str): Name of the last repository from previous page

    Returns:
        Tuple[list, str]: (list of (repo_name, full_url) tuples, next page token or None)
    """
    base = _normalize_base_url(api_url)
    url = f"{base}/v2/_catalog?n={page_size}"
    if last_repo:
        url += f"&last={last_repo}"

    headers = _auth_headers(token)
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        detail = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                body = e.response.text[:500] if e.response.text else "(empty)"
            except Exception:
                body = "(unreadable)"
            detail = f"{e}: response {e.response.status_code} - {body}"
        logger.error("ECR _catalog request failed: %s", detail)
        raise RuntimeError(f"ECR registry request failed: {detail}") from e

    try:
        data = response.json()
    except ValueError as e:
        logger.error("ECR _catalog invalid JSON: %s", response.text[:200])
        raise RuntimeError(f"ECR returned invalid JSON: {e}") from e

    repos = data.get('repositories', [])

    # Next page from Link header if present
    next_page = None
    if 'Link' in response.headers:
        link_header = response.headers['Link']
        if 'next' in link_header:
            match = re.search(r'last=([^&>]+)', link_header)
            if match:
                next_page = match.group(1)

    # Full URL for each repo: registry_host/repo_name
    registry_host = base.split('//')[-1] if '//' in base else base
    return [(repo, f"{registry_host}/{repo}") for repo in repos], next_page


# ---------------------------------------------------------------------------
# Tag listing
# ---------------------------------------------------------------------------

def get_tags(api_url: str, token: str, repo: str, limit: int = None) -> Generator[str, None, None]:
    """
    Get tags for a repository.

    Args:
        api_url (str): ECR API URL
        token (str): Auth token (base64 Basic auth)
        repo (str): Repository name
        limit (int): Optional limit on the number of tags

    Yields:
        str: Tag name
    """
    base = _normalize_base_url(api_url)
    n = limit if limit is not None else PAGE_SIZE
    url = f"{base}/v2/{repo}/tags/list?n={n}"
    headers = _auth_headers(token)

    count = 0
    while url:
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            tags = data.get('tags') or []
            for tag in tags:
                yield tag
                count += 1
                if limit is not None and count >= limit:
                    return
            # Pagination: next link
            url = response.links.get('next', {}).get('url') or None
        except requests.RequestException as e:
            logger.error("Failed to fetch tags from %s: %s", url, e)
            break


# ---------------------------------------------------------------------------
# Manifest retrieval
# ---------------------------------------------------------------------------

def get_manifest(api_url: str, token: str, repo: str, tag: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Get manifest for a specific image tag.

    Args:
        api_url (str): ECR API URL
        token (str): Auth token (base64 Basic auth)
        repo (str): Repository name
        tag (str): Tag name

    Returns:
        Tuple[Optional[dict], Optional[str]]: Manifest data and Docker-Content-Digest.
    """
    try:
        base = _normalize_base_url(api_url)
        headers = {
            **_auth_headers(token),
            "Accept": "application/vnd.oci.image.manifest.v1+json, "
                      "application/vnd.docker.distribution.manifest.v2+json"
        }
        response = requests.get(f"{base}/v2/{repo}/manifests/{tag}", headers=headers, timeout=30)
        response.raise_for_status()
        return response.json(), response.headers.get("Docker-Content-Digest")
    except requests.RequestException as e:
        logger.error("Failed to get manifest for %s:%s: %s", repo, tag, e)
        return None, None


# ---------------------------------------------------------------------------
# Helm chart support
# ---------------------------------------------------------------------------

def get_helm_images(api_url: str, token: str, repo: str, digest: str) -> List[str]:
    """
    Extract container image references from a Helm chart blob.

    Args:
        api_url (str): ECR API URL
        token (str): Auth token
        repo (str): Repository name
        digest (str): Chart layer digest

    Returns:
        List[str]: List of container image references.
    """
    base = _normalize_base_url(api_url)
    headers = _auth_headers(token)
    blob_url = f"{base}/v2/{repo}/blobs/{digest}"
    try:
        response = requests.get(blob_url, headers=headers, timeout=60)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to download Helm chart %s:%s: %s", repo, digest, e)
        raise RuntimeError(f"Failed to download Helm chart {repo}:{digest}: {e}") from e

    return extract_images_from_chart_blob(response.content, f"{repo}:{digest}")


# ---------------------------------------------------------------------------
# Image digest
# ---------------------------------------------------------------------------

def get_ecr_image_digest(registry_url: str, token: str, image_ref: str) -> Optional[str]:
    """
    Get image digest from Amazon ECR.

    Args:
        registry_url: ECR registry URL (e.g. 'https://123456789012.dkr.ecr.us-east-1.amazonaws.com')
        token: ECR auth token (base64 Basic auth)
        image_ref: Full image reference (e.g. '123456789012.dkr.ecr.us-east-1.amazonaws.com/myimage:tag')

    Returns:
        str: Image digest or None if not found
    """
    try:
        registry = registry_url.split('://')[-1] if '://' in registry_url else registry_url
        registry = registry.rstrip('/')

        # Check if image_ref belongs to this registry
        if registry not in image_ref:
            logger.warning(
                "Image ref %s does not belong to ECR registry %s",
                image_ref, registry,
            )
            return None

        image_name = image_ref.split(registry + '/')[-1]
        if ':' not in image_name:
            logger.warning("No tag in image ref %s", image_ref)
            return None
        repository, tag = image_name.rsplit(':', 1)

        headers = {
            **_auth_headers(token),
            'Accept': 'application/vnd.docker.distribution.manifest.v2+json'
        }

        url = f'https://{registry}/v2/{repository}/manifests/{tag}'
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        digest = response.headers.get('Docker-Content-Digest')
        if digest:
            return digest

        logger.warning("Could not get digest for image %s from ECR API", image_ref)

    except Exception as e:
        logger.warning("Failed to get digest from ECR API for %s: %s", image_ref, e)

    return None


# ---------------------------------------------------------------------------
# Provider dispatch table
# ---------------------------------------------------------------------------

PROVIDER_FUNCTIONS = {
    'get_bearer_token': get_bearer_token,
    'get_repositories': get_repositories,
    'get_tags': get_tags,
    'get_manifest': get_manifest,
    'get_helm_images': get_helm_images,
    'get_image_digest': get_ecr_image_digest,
}
