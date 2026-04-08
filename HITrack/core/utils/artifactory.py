"""
JFrog Artifactory Container Registry Scanner

This module provides utility functions for working with JFrog Artifactory
Docker/OCI registries. It uses the Docker Registry HTTP API V2 with Basic
authentication. It handles authentication, data retrieval, and basic
operations with Artifactory container repositories.
"""

# Standard library imports
import base64
import json
import logging
import re
import subprocess
from typing import Any, Dict, Generator, List, Optional, Tuple
from urllib.parse import urlparse

# Third-party imports
import requests
import yaml

from .helm import extract_images_from_chart_blob

logger = logging.getLogger(__name__)

# Configuration
PAGE_SIZE = 500


def get_bearer_token(api_url: str, login: str, password: str) -> str:
    """
    Get auth token for Artifactory (Basic auth encoded).
    Artifactory Docker API uses Basic authentication; we return base64(login:password)
    so callers can use Authorization: Basic {token}.

    Args:
        api_url (str): Artifactory registry base URL (e.g. https://company.jfrog.io/artifactory/docker-local)
        login (str): Login username (or username for API key)
        password (str): Password or API key

    Returns:
        str: Base64-encoded "login:password" for Basic auth.
    """
    return base64.b64encode(f"{login}:{password}".encode()).decode()


def _auth_headers(token: str) -> dict:
    """Build Authorization header for Artifactory (Basic auth)."""
    return {"Authorization": f"Basic {token}"}


def _normalize_base_url(api_url: Optional[str]) -> str:
    """Ensure api_url has no trailing slash and is a valid base URL."""
    if not api_url or not api_url.strip():
        raise ValueError("Artifactory registry API URL is not configured")
    base = api_url.strip().rstrip('/')
    if not base.startswith('http://') and not base.startswith('https://'):
        base = f"https://{base}"
    return base


def _docker_api_base(api_url: str, repo_key: str) -> str:
    """
    Return the Docker Registry API base URL for a given Artifactory repo key.
    Artifactory uses /api/docker/<repo-key>/v2/... for Docker API (not /<repo-key>/v2/...).
    """
    base = _normalize_base_url(api_url)
    return f"{base}/api/docker/{repo_key}"


def get_repositories_rest(api_url: str, token: str, package_type: str = 'docker') -> List[Tuple[str, str]]:
    """
    List Artifactory repository keys via REST API (like GET /api/repositories).
    Use the registry base URL (e.g. https://repo.example.com/artifactory) to discover
    all Docker repos; user can then select which repo keys to add.

    Args:
        api_url: Artifactory base URL (e.g. https://repo.com.int.zone/artifactory)
        token: Basic auth token (base64 login:password)
        package_type: Filter by package type (default 'docker')

    Returns:
        List of (repo_key, repo_url) e.g. [('a8n-docker', 'https://.../artifactory/a8n-docker'), ...]
    """
    base = _normalize_base_url(api_url)
    url = f"{base}/api/repositories?packageType={package_type}"
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
        logger.error("Artifactory REST api/repositories failed: %s", detail)
        raise RuntimeError(f"Artifactory registry request failed: {detail}") from e

    try:
        data = response.json()
    except ValueError as e:
        logger.error("Artifactory api/repositories invalid JSON: %s", response.text[:200])
        raise RuntimeError(f"Artifactory returned invalid JSON: {e}") from e

    if not isinstance(data, list):
        return []

    result = []
    for r in data:
        key = r.get('key')
        repo_url = r.get('url', '')
        if key and repo_url:
            result.append((key, repo_url.rstrip('/')))
    return result


def get_repositories(api_url: str, token: str, page_size: int = 100, last_repo: str = None) -> Tuple[list, str]:
    """
    Get repositories (image names) from Artifactory Docker registry with pagination.
    Uses Docker Registry V2 _catalog endpoint.

    Args:
        api_url (str): Artifactory registry base URL
        token (str): Basic auth token (base64 login:password)
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
            if e.response.status_code == 404 and "not found" in body.lower():
                detail += (
                    " Make sure the registry API URL includes your Docker repository key, "
                    "e.g. https://your-artifactory/artifactory/docker-local (not .../artifactory only)."
                )
        logger.error("Artifactory _catalog request failed: %s", detail)
        raise RuntimeError(f"Artifactory registry request failed: {detail}") from e

    try:
        data = response.json()
    except ValueError as e:
        logger.error("Artifactory _catalog invalid JSON: %s", response.text[:200])
        raise RuntimeError(f"Artifactory returned invalid JSON: {e}") from e

    repos = data.get('repositories', [])

    # Next page from Link header if present
    next_page = None
    if 'Link' in response.headers:
        link_header = response.headers['Link']
        if 'next' in link_header:
            match = re.search(r'last=([^&>]+)', link_header)
            if match:
                next_page = match.group(1)

    # Full URL for each repo: registry_host/repo_name (for display/pull)
    registry_host = base.split('//')[-1] if '//' in base else base
    return [(repo, f"{registry_host}/{repo}") for repo in repos], next_page


def get_catalog(api_url: str, token: str, repo_key: str, page_size: int = 500, last: Optional[str] = None) -> Tuple[List[str], Optional[str]]:
    """
    List Docker image names (paths) inside an Artifactory Docker repo key.
    Uses Artifactory Docker API path: /api/docker/<repo-key>/v2/_catalog.

    Args:
        api_url: Artifactory base URL (e.g. https://repo.com.int.zone/artifactory)
        token: Basic auth token
        repo_key: Artifactory repo key (e.g. a8n-docker)
        page_size: Max items per page
        last: Last image name from previous page (pagination)

    Returns:
        (list of image names, next_page token or None)
    """
    base = _docker_api_base(api_url, repo_key)
    url = f"{base}/v2/_catalog?n={page_size}"
    if last:
        url += f"&last={last}"
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
        logger.error("Artifactory _catalog (api/docker) failed: %s", detail)
        raise RuntimeError(f"Artifactory catalog request failed: {detail}") from e
    try:
        data = response.json()
    except ValueError as e:
        raise RuntimeError(f"Artifactory returned invalid JSON: {e}") from e
    repos = data.get('repositories', [])
    next_page = None
    if 'Link' in response.headers and 'next' in response.headers.get('Link', ''):
        match = re.search(r'last=([^&>]+)', response.headers['Link'])
        if match:
            next_page = match.group(1)
    return repos, next_page


def get_tags(api_url: str, token: str, repo: str, limit: int = None) -> Generator[str, None, None]:
    """
    Get tags for a repository.

    Args:
        api_url (str): Artifactory registry base URL
        token (str): Basic auth token
        repo (str): Repository (image) name
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
            response = requests.get(url, headers=headers)
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
            logger.error(f"Failed to fetch tags from {url}: {e}")
            break


def get_manifest(api_url: str, token: str, repo: str, tag: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Get manifest for a specific image tag.

    Args:
        api_url (str): Artifactory registry base URL
        token (str): Basic auth token
        repo (str): Repository name
        tag (str): Tag name

    Returns:
        Tuple[Optional[dict], Optional[str]]: Manifest data and Docker-Content-Digest.
    """
    try:
        base = _normalize_base_url(api_url)
        headers = {
            **_auth_headers(token),
            "Accept": "application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"
        }
        response = requests.get(f"{base}/v2/{repo}/manifests/{tag}", headers=headers)
        response.raise_for_status()
        return response.json(), response.headers.get("Docker-Content-Digest")
    except requests.RequestException as e:
        logger.error(f"Failed to get manifest for {repo}:{tag}: {e}")
        return None, None


def is_helm_chart(manifest: dict) -> bool:
    """
    Check if the manifest represents a Helm chart.

    Args:
        manifest (dict): Image manifest data.

    Returns:
        bool: True if the manifest is a Helm chart.
    """
    cfg = manifest.get("config", {}).get("mediaType", "")
    ann = manifest.get("annotations", {}).get("org.opencontainers.artifact.type", "")
    return cfg == "application/vnd.cncf.helm.config.v1+json" or ann == "helm.chart"


def get_chart_digest(manifest: dict) -> Optional[str]:
    """
    Get the digest of the Helm chart layer.

    Args:
        manifest (dict): Image manifest data.

    Returns:
        Optional[str]: Chart digest if found, None otherwise.
    """
    for layer in manifest.get("layers", []):
        if layer.get("mediaType", "").endswith("tar+gzip"):
            return layer["digest"]
    return None


def get_helm_index(api_url: str, token: str, repo_key: str) -> List[Dict[str, Any]]:
    """
    Fetch index.yaml from a native Helm repository in Artifactory and return
    chart version entries. Used when repository_type is 'helm' (packageType=helm).

    Args:
        api_url: Artifactory base URL (e.g. https://repo.example.com/artifactory)
        token: Basic auth token
        repo_key: Helm repo key (e.g. helm-local)

    Returns:
        List of {"chart": chart_name, "version": version, "url": full_tgz_url}.
        URL is normalized to a full URL for downloading the chart.
    """
    base = _normalize_base_url(api_url)
    index_url = f"{base}/{repo_key}/index.yaml"
    headers = _auth_headers(token)
    try:
        response = requests.get(index_url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Failed to fetch Helm index for %s: %s", repo_key, e)
        return []

    try:
        data = yaml.safe_load(response.text)
    except yaml.YAMLError as e:
        logger.warning("Invalid YAML in Helm index for %s: %s", repo_key, e)
        return []

    if not data or not isinstance(data.get("entries"), dict):
        return []

    result = []
    repo_base = f"{base}/{repo_key}".rstrip("/")
    for chart_name, versions in data["entries"].items():
        if not isinstance(versions, list):
            continue
        for entry in versions:
            if not isinstance(entry, dict):
                continue
            version = entry.get("version")
            urls = entry.get("urls") or entry.get("url")
            if not version:
                continue
            if isinstance(urls, list) and urls:
                url_path = urls[0]
            elif isinstance(urls, str):
                url_path = urls
            else:
                continue
            if url_path.startswith("http://") or url_path.startswith("https://"):
                full_url = url_path
            else:
                # Artifactory index may use local://path/to/chart.tgz; strip scheme to get repo-relative path
                if url_path.lower().startswith("local://"):
                    url_path = url_path[7:].lstrip("/")
                full_url = f"{repo_base}/{url_path.lstrip('/')}"
            result.append({"chart": chart_name, "version": version, "url": full_url})
    return result


def get_helm_images_from_native_chart(
    api_url: str, token: str, chart_url: str
) -> List[str]:
    """
    Download a Helm chart .tgz from the given URL and extract image references
    using helm template. Used for native Helm repos (not OCI).

    Args:
        api_url: Unused; kept for signature consistency
        token: Basic auth token (for authenticated download)
        chart_url: Full URL to the chart .tgz file

    Returns:
        List of image references (name:tag) found in the chart templates.
    """
    del api_url  # chart_url is already full
    headers = _auth_headers(token)
    try:
        response = requests.get(chart_url, headers=headers, timeout=60)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to download Helm chart from %s: %s", chart_url, e)
        raise RuntimeError(f"Failed to download Helm chart from {chart_url}: {e}") from e

    return extract_images_from_chart_blob(response.content, chart_url)


def get_helm_images(api_url: str, token: str, repo: str, digest: str) -> List[str]:
    """
    Extract container image references from a Helm chart blob.

    Args:
        api_url (str): Artifactory registry base URL
        token (str): Basic auth token
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


def _artifactory_registry_hostname(registry_url: str) -> Optional[str]:
    raw = (registry_url or "").strip()
    if not raw:
        return None
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    host = urlparse(raw).hostname
    return host.lower() if host else None


def _parse_image_ref_host_name_tag(image_ref: str) -> Optional[Tuple[Optional[str], str, str]]:
    """Split a container image ref into (registry_host_or_none, image_path, tag)."""
    raw = str(image_ref or "").strip()
    if not raw:
        return None
    path = raw
    if "@" in path:
        path = path.rsplit("@", 1)[0]
    tag = "latest"
    if ":" in path.split("/")[-1]:
        path, tag = path.rsplit(":", 1)
    segments = [s for s in path.split("/") if s]
    if not segments:
        return None
    host: Optional[str] = None
    if "." in segments[0] or segments[0] == "localhost" or segments[0].startswith("["):
        host = segments[0]
        name = "/".join(segments[1:]) if len(segments) > 1 else ""
    else:
        name = "/".join(segments)
    if not name:
        return None
    return (host, name, tag)


def _digest_from_docker_pull(pull_ref: str) -> Optional[str]:
    """Pull and inspect locally; uses subdomain-style ref when path-style was given."""
    try:
        from .registry import to_docker_pull_ref

        ref = to_docker_pull_ref(pull_ref)
        subprocess.run(["docker", "pull", ref], capture_output=True, check=True)
        result = subprocess.run(
            ["docker", "inspect", ref],
            capture_output=True,
            check=True,
            text=True,
        )
        inspect_data = json.loads(result.stdout)
        if inspect_data and len(inspect_data) > 0:
            repo_digests = inspect_data[0].get("RepoDigests", [])
            if repo_digests:
                digest = repo_digests[0].split("@")[1]
                logger.info("Got digest %s using Docker inspect for %s", digest, ref)
                return digest
        return None
    except Exception as docker_error:
        logger.error(
            "Failed to get digest using Docker inspect for %s: %s",
            pull_ref,
            docker_error,
        )
        return None


def _digest_via_artifactory_subdomain_api(
    registry_url: str, token: str, image_ref: str, base_hostname: str
) -> Optional[str]:
    """Resolve digest when ref uses Docker subdomain form <repo-key>.<artifactory-host>/image:tag."""
    parsed = _parse_image_ref_host_name_tag(image_ref)
    if not parsed:
        return None
    image_host, image_name, tag = parsed
    if not image_host:
        return None
    ih = image_host.lower()
    bh = base_hostname.lower()
    if ih == bh or not ih.endswith("." + bh):
        return None
    repo_key = ih[: -(len(bh) + 1)]
    if not repo_key or "/" in repo_key:
        return None
    headers = {
        **_auth_headers(token),
        "Accept": "application/vnd.docker.distribution.manifest.v2+json",
    }
    docker_base = _docker_api_base(registry_url, repo_key)
    if not docker_base.startswith("http"):
        docker_base = "https://" + docker_base
    url = f"{docker_base}/v2/{image_name}/manifests/{tag}"
    try:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        digest = response.headers.get("Docker-Content-Digest")
        if digest:
            logger.info(
                "Resolved digest for %s via Artifactory subdomain API (repo_key=%s)",
                image_ref,
                repo_key,
            )
            return digest
    except requests.RequestException as e:
        logger.debug(
            "Artifactory subdomain API miss for %s (repo_key=%s): %s",
            image_ref,
            repo_key,
            e,
        )
    return None


def get_artifactory_image_digest(registry_url: str, token: str, image_ref: str) -> Optional[str]:
    """
    Get image digest from Artifactory Docker registry.
    Artifactory Docker API is at /api/docker/<repo-key>/v2/<image>/manifests/<tag>.
    Supports path-style refs containing the Artifactory base path, subdomain-style refs
    (<repo-key>.<host>/image:tag on the same Artifactory), and falls back to docker pull
    for external registries (Docker Hub, GHCR, etc.).

    Args:
        registry_url: Artifactory registry base URL (e.g. https://repo.com.int.zone/artifactory)
        token: Basic auth token (base64 login:password)
        image_ref: Full image reference (e.g. 'repo.com.int.zone/artifactory/a8n-docker-local/a8n-db:21.0.192')

    Returns:
        str: Image digest or None if not found
    """
    registry = (
        registry_url.split("://", 1)[-1].rstrip("/")
        if "://" in registry_url
        else registry_url.rstrip("/")
    )
    base_hostname = _artifactory_registry_hostname(registry_url)

    if registry in image_ref:
        try:
            rest = image_ref.split(registry, 1)[-1].lstrip("/")
            if ":" not in rest:
                return _digest_from_docker_pull(image_ref)
            path_part, tag = rest.rsplit(":", 1)
            parts = path_part.split("/")
            if not parts:
                return _digest_from_docker_pull(image_ref)
            repo_key = parts[0]
            image_name = "/".join(parts[1:]) if len(parts) > 1 else parts[0]

            headers = {
                **_auth_headers(token),
                "Accept": "application/vnd.docker.distribution.manifest.v2+json",
            }
            docker_base = _docker_api_base(registry_url, repo_key)
            if not docker_base.startswith("http"):
                docker_base = "https://" + docker_base
            url = f"{docker_base}/v2/{image_name}/manifests/{tag}"
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()

            digest = response.headers.get("Docker-Content-Digest")
            if digest:
                return digest

            logger.warning(
                "Could not get digest for image %s from Artifactory API",
                image_ref,
            )
        except Exception as e:
            logger.warning(
                "Failed to get digest from Artifactory API for %s: %s",
                image_ref,
                e,
            )

        logger.info(
            "Trying Docker pull after path-style Artifactory API miss for %s",
            image_ref,
        )
        return _digest_from_docker_pull(image_ref)

    if base_hostname:
        sub = _digest_via_artifactory_subdomain_api(
            registry_url, token, image_ref, base_hostname
        )
        if sub:
            return sub

    logger.info(
        "No Artifactory path/subdomain match for %s; trying docker pull (external or other registry)",
        image_ref,
    )
    return _digest_from_docker_pull(image_ref)
