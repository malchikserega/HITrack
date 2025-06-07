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

    while url:
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            yield response.json()
            url = response.links.get("next", {}).get("url")
        except requests.RequestException as e:
            logger.error(f"Failed to fetch data from {url}: {e}")
            break


def get_repositories(api_url: str, token: str) -> Generator[Tuple[str, str, int], None, None]:
    """
    Get all repositories from ACR with their names, full URLs and tag counts.
    
    Args:
        api_url (str): ACR API URL
        token (str): Bearer token for authentication
        
    Yields:
        Tuple[str, str, int]: A tuple containing (repository_name, full_url, tag_count)
    """
    for page in get_paged_data(f"{api_url}/v2/_catalog?n={PAGE_SIZE}", token):
        for repo in page.get("repositories", []):
            # Count tags for this repository
            tag_count = sum(1 for _ in get_tags(api_url, token, repo))
            yield repo, f"{api_url.split('//')[1]}/{repo}", tag_count


def get_tags(api_url: str, token: str, repo: str) -> Generator[str, None, None]:
    """
    Get all tags for a repository.
    
    Args:
        api_url (str): ACR API URL
        token (str): Bearer token for authentication
        repo (str): Repository name.
        
    Yields:
        str: Tag name.
    """
    for page in get_paged_data(f"{api_url}/v2/{repo}/tags/list?n={PAGE_SIZE}", token):
        for tag in page.get("tags", []):
            yield tag


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
