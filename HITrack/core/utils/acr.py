"""
Azure Container Registry (ACR) Scanner

This module provides utility functions for working with Azure Container Registry.
It handles authentication, data retrieval, and basic operations with ACR.
"""

# Standard library imports
import base64
import logging
import re
import subprocess
import tempfile
import urllib.parse
from typing import Generator, List, Optional, Tuple

# Third-party imports
import requests

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
    Get a bearer token for ACR authentication.
    
    Args:
        api_url (str): ACR API URL
        login (str): Login username
        password (str): Login password
        
    Returns:
        str: The bearer token for ACR authentication.
        
    Raises:
        requests.RequestException: If the token request fails.
    """
    try:
        b64 = base64.b64encode(f"{login}:{password}".encode()).decode()
        scope = urllib.parse.quote("repository:*:* registry:catalog:*", safe='')
        svc = api_url.split("//")[1]
        url = f"{api_url}/oauth2/token?service={svc}&scope={scope}"

        response = requests.get(url, headers={"Authorization": f"Basic {b64}"})
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.RequestException as e:
        logger.error(f"Failed to get bearer token: {e}")
        raise


def get_paged_data(url: str, token: str) -> Generator[dict, None, None]:
    """
    Get paginated data from ACR API.
    
    Args:
        url (str): The URL to fetch data from.
        token (str): Bearer token for authentication
        
    Yields:
        dict: JSON response data for each page.
    """
    headers = {"Authorization": f"Bearer {token}"}
    from urllib.parse import urlparse, urljoin

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    while url:
        if url.startswith("/"):
            url = urljoin(base_url, url)
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            yield data
            next_link = response.links.get("next", {}).get("url")
            url = next_link if next_link else None
        except requests.RequestException as e:
            logger.error(f"Failed to fetch data from {url}: {e}")
            logger.error(f"Response content: {getattr(e.response, 'text', None)}")
            break


def get_repositories(api_url: str, token: str, page_size: int = 50, last_repo: str = None) -> Tuple[list, str]:
    """
    Get repositories from ACR with pagination.
    
    Args:
        api_url (str): ACR API URL
        token (str): Bearer token for authentication
        page_size (int): Number of repositories to return
        last_repo (str): Name of the last repository from previous page
        
    Returns:
        Tuple[list, str]: A tuple containing (list of repositories, next page token)
    """
    url = f"{api_url}/v2/_catalog?n={page_size}"
    if last_repo:
        url += f"&last={last_repo}"
        
    response = requests.get(url, headers={'Authorization': f'Bearer {token}'})
    response.raise_for_status()
    
    data = response.json()
    repos = data.get('repositories', [])
    
    # Get the next page token from Link header if present
    next_page = None
    if 'Link' in response.headers:
        link_header = response.headers['Link']
        if 'next' in link_header:
            # Extract the last parameter from the next link
            import re
            match = re.search(r'last=([^&>]+)', link_header)
            if match:
                next_page = match.group(1)
    
    return [(repo, f"{api_url.split('//')[1]}/{repo}") for repo in repos], next_page


def get_tags(api_url: str, token: str, repo: str, limit: int = None) -> Generator[str, None, None]:
    """
    Get all tags for a repository.
    
    Args:
        api_url (str): ACR API URL
        token (str): Bearer token for authentication
        repo (str): Repository name.
        limit (int): Optional limit on the number of tags to return.
        
    Yields:
        str: Tag name.
    """
    count = 0
    page_size = PAGE_SIZE
    if limit is not None and limit < PAGE_SIZE:
        page_size = limit
    for page in get_paged_data(f"{api_url}/v2/{repo}/tags/list?n={page_size}", token):
        if not page or page.get("tags") is None:
            break
        for tag in page.get("tags", []):
            yield tag
            count += 1
            if limit is not None and count >= limit:
                return


def get_manifest(api_url: str, token: str, repo: str, tag: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Get manifest for a specific image tag.
    
    Args:
        api_url (str): ACR API URL
        token (str): Bearer token for authentication
        repo (str): Repository name.
        tag (str): Tag name.
        
    Returns:
        Tuple[Optional[dict], Optional[str]]: Manifest data and digest.
    """
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.oci.image.manifest.v1+json"
        }
        response = requests.get(f"{api_url}/v2/{repo}/manifests/{tag}", headers=headers)
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
    for layer in manifest["layers"]:
        if layer["mediaType"].endswith("tar+gzip"):
            return layer["digest"]
    return None


def get_helm_images(api_url: str, token: str, repo: str, digest: str) -> List[str]:
    """
    Extract container image references from a Helm chart.
    
    Args:
        api_url (str): ACR API URL
        token (str): Bearer token for authentication
        repo (str): Repository name.
        digest (str): Chart digest.
        
    Returns:
        List[str]: List of container image references.
    """
    try:
        headers = {"Authorization": f"Bearer {token}"}
        blob = requests.get(f"{api_url}/v2/{repo}/blobs/{digest}", headers=headers).content
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
