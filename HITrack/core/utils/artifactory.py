"""
JFrog Artifactory Container Registry Scanner

This module provides utility functions for working with JFrog Artifactory
Docker/OCI registries. It uses the Docker Registry HTTP API V2 with Basic
authentication. It handles authentication, data retrieval, and basic
operations with Artifactory container repositories.
"""

# Standard library imports
import base64
import logging
import re
import subprocess
import tempfile
from typing import Any, Dict, Generator, List, Optional, Tuple

# Third-party imports
import requests
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PAGE_SIZE = 500

# Regular expression for finding image references in Helm charts
IMG_RE = re.compile(r'image:\s*["\']?([\w./-]+:[\w.\-]+)')


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
        return []

    fname = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".tgz", delete=False) as f:
            f.write(response.content)
            f.flush()
            fname = f.name
        rendered = subprocess.run(
            ["helm", "template", "scan", fname, "--skip-tests"],
            capture_output=True,
            check=True,
            text=True,
            timeout=120,
        ).stdout
        return sorted(set(IMG_RE.findall(rendered)))
    except (subprocess.SubprocessError, OSError) as e:
        logger.error("Failed to run helm template on chart %s: %s", chart_url, e)
        return []
    finally:
        import os
        if fname and os.path.exists(fname):
            try:
                os.unlink(fname)
            except Exception:
                pass


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
    try:
        base = _normalize_base_url(api_url)
        headers = _auth_headers(token)
        blob_url = f"{base}/v2/{repo}/blobs/{digest}"
        blob = requests.get(blob_url, headers=headers).content
        with tempfile.NamedTemporaryFile(suffix=".tgz") as f:
            f.write(blob)
            f.flush()
            rendered = subprocess.run(
                ["helm", "template", "scan", f.name, "--skip-tests"],
                capture_output=True,
                check=True,
                text=True
            ).stdout
        return sorted(set(IMG_RE.findall(rendered)))
    except (requests.RequestException, subprocess.SubprocessError) as e:
        logger.error(f"Failed to process Helm chart {repo}:{digest}: {e}")
        return []


def get_artifactory_image_digest(registry_url: str, token: str, image_ref: str) -> Optional[str]:
    """
    Get image digest from Artifactory Docker registry.
    Artifactory Docker API is at /api/docker/<repo-key>/v2/<image>/manifests/<tag>.
    Falls back to Docker inspect if API fails (e.g. for public pulls).

    Args:
        registry_url: Artifactory registry base URL (e.g. https://repo.com.int.zone/artifactory)
        token: Basic auth token (base64 login:password)
        image_ref: Full image reference (e.g. 'repo.com.int.zone/artifactory/a8n-docker-local/a8n-db:21.0.192')

    Returns:
        str: Image digest or None if not found
    """
    try:
        registry = registry_url.split('://')[-1].rstrip('/') if '://' in registry_url else registry_url.rstrip('/')
        if registry not in image_ref:
            logger.warning(f"Registry {registry} not in image_ref {image_ref}")
            return None
        rest = image_ref.split(registry, 1)[-1].lstrip('/')
        if ':' not in rest:
            return None
        path_part, tag = rest.rsplit(':', 1)
        parts = path_part.split('/')
        if not parts:
            return None
        # First segment is Docker repo key (e.g. a8n-docker-local), rest is image path (e.g. a8n-db)
        repo_key = parts[0]
        image_name = '/'.join(parts[1:]) if len(parts) > 1 else parts[0]

        headers = {
            **_auth_headers(token),
            'Accept': 'application/vnd.docker.distribution.manifest.v2+json'
        }
        docker_base = _docker_api_base(registry_url, repo_key)
        if not docker_base.startswith('http'):
            docker_base = 'https://' + docker_base
        url = f"{docker_base}/v2/{image_name}/manifests/{tag}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        digest = response.headers.get('Docker-Content-Digest')
        if digest:
            return digest

        logger.warning(f"Could not get digest for image {image_ref} from Artifactory API")
        return None

    except Exception as e:
        logger.warning(f"Failed to get digest from Artifactory API for {image_ref}: {e}")
        logger.info("Trying to get digest using Docker inspect...")
        try:
            subprocess.run(["docker", "pull", image_ref], capture_output=True, check=True)
            result = subprocess.run(
                ["docker", "inspect", image_ref],
                capture_output=True,
                check=True,
                text=True
            )
            import json
            inspect_data = json.loads(result.stdout)
            if inspect_data and len(inspect_data) > 0:
                repo_digests = inspect_data[0].get('RepoDigests', [])
                if repo_digests:
                    digest = repo_digests[0].split('@')[1]
                    logger.info(f"Got digest {digest} using Docker inspect")
                    return digest
            return None
        except Exception as docker_error:
            logger.error(f"Failed to get digest using Docker inspect for {image_ref}: {docker_error}")
            return None
