"""
Registry abstraction: dispatches to ACR or Artifactory based on provider.
Allows the app to support both Azure Container Registry and JFrog Artifactory
as scanning sources with a single interface.
"""

from typing import Generator, List, Optional, Tuple

# Re-use manifest helpers from ACR (same for OCI/Docker)
from .acr import is_helm_chart, get_chart_digest


def get_bearer_token(registry) -> str:
    """Get auth token for the given registry (ACR Bearer or Artifactory Basic)."""
    if registry.provider == 'jfrog':
        from .artifactory import get_bearer_token as art_get_token
        return art_get_token(registry.api_url, registry.login, registry.password)
    from .acr import get_bearer_token as acr_get_token
    return acr_get_token(registry.api_url, registry.login, registry.password)


def get_repositories(registry, page_size: int = 100, last_repo: str = None) -> Tuple[list, str]:
    """
    List repositories with pagination.
    For jfrog: returns both Docker and Helm repo keys; each item is (name, url, package_type).
    For acr: returns (name, url) per repo.
    """
    token = get_bearer_token(registry)
    if registry.provider == 'jfrog':
        from .artifactory import get_repositories_rest
        docker_repos = get_repositories_rest(registry.api_url, token, package_type='docker')
        helm_repos = get_repositories_rest(registry.api_url, token, package_type='helm')
        # Tag each with package_type: (repo_key, repo_url, 'docker'|'helm')
        combined = [(r[0], r[1], 'docker') for r in docker_repos]
        combined.extend([(r[0], r[1], 'helm') for r in helm_repos])
        return (combined, None)
    from .acr import get_repositories as acr_get_repos
    return acr_get_repos(registry.api_url, token, page_size=page_size, last_repo=last_repo)


def get_tags(registry, repo: str, limit: int = None, image_name: str = None) -> Generator[str, None, None]:
    """
    Get tags for a repository. For jfrog, when image_name is set, repo is the repo key
    and we use Artifactory Docker API base /api/docker/<repo_key>.
    """
    token = get_bearer_token(registry)
    if registry.provider == 'jfrog':
        from .artifactory import get_tags as art_get_tags, _docker_api_base
        if image_name is not None:
            docker_base = _docker_api_base(registry.api_url, repo)
            return art_get_tags(docker_base, token, image_name, limit=limit)
        return art_get_tags(registry.api_url, token, repo, limit=limit)
    from .acr import get_tags as acr_get_tags
    return acr_get_tags(registry.api_url, token, repo, limit=limit)


def get_catalog(registry, repo_key: str, page_size: int = 500, last: str = None) -> Tuple[list, Optional[str]]:
    """List Docker image names inside an Artifactory repo key (jfrog only)."""
    if registry.provider != 'jfrog':
        return [], None
    from .artifactory import get_catalog as art_get_catalog
    token = get_bearer_token(registry)
    return art_get_catalog(registry.api_url, token, repo_key, page_size=page_size, last=last)


def get_manifest(registry, repo: str, tag: str, image_name: str = None) -> Tuple[Optional[dict], Optional[str]]:
    """Get manifest for an image tag. For jfrog, when image_name is set, repo is the repo key."""
    token = get_bearer_token(registry)
    if registry.provider == 'jfrog':
        from .artifactory import get_manifest as art_get_manifest, _docker_api_base
        if image_name is not None:
            docker_base = _docker_api_base(registry.api_url, repo)
            return art_get_manifest(docker_base, token, image_name, tag)
        return art_get_manifest(registry.api_url, token, repo, tag)
    from .acr import get_manifest as acr_get_manifest
    return acr_get_manifest(registry.api_url, token, repo, tag)


def image_ref_repo_key(registry_base_url: str, image_ref: str) -> Optional[str]:
    """
    Return the first path segment of image_ref after the registry base (e.g. repo key).
    E.g. base 'repo.com/artifactory', ref 'repo.com/artifactory/a8n-helm-21-public-local/loyalty-program:1.0'
    -> 'a8n-helm-21-public-local'. Returns None if base not in ref.
    """
    if not registry_base_url or not image_ref:
        return None
    base = registry_base_url.strip().rstrip('/')
    if base.startswith('http://') or base.startswith('https://'):
        base = base.split('://', 1)[1]
    if base not in image_ref:
        return None
    rest = image_ref.split(base, 1)[-1].lstrip('/')
    if ':' in rest:
        rest = rest.rsplit(':', 1)[0]
    if not rest:
        return None
    return rest.split('/')[0]


def get_image_digest(registry, image_ref: str) -> Optional[str]:
    """Get image digest from the registry (ACR or Artifactory)."""
    if not registry:
        return None
    if registry.provider == 'jfrog':
        from .artifactory import get_artifactory_image_digest
        return get_artifactory_image_digest(registry.api_url, get_bearer_token(registry), image_ref)
    from .acr import get_acr_image_digest
    return get_acr_image_digest(registry.api_url, get_bearer_token(registry), image_ref)


def build_fallback_image_ref(fallback_repository, image_ref: str) -> Optional[str]:
    """
    Build a candidate image ref for a fallback Docker repository from the original ref.
    image_ref is e.g. 'bad-registry.io/namespace/image:tag'; we use path and tag with fallback repo base.
    """
    if not fallback_repository or not fallback_repository.url:
        return None
    if ":" in image_ref:
        path_part, tag = image_ref.rsplit(":", 1)
    else:
        path_part, tag = image_ref, "latest"
    parts = path_part.split("/")
    path_without_host = "/".join(parts[1:]) if len(parts) > 1 else path_part
    if not path_without_host:
        path_without_host = path_part
    base = fallback_repository.url.strip().rstrip("/")
    if base.startswith("http://") or base.startswith("https://"):
        base = base.split("://", 1)[1]
    return f"{base}/{path_without_host}:{tag}"


def get_helm_images(registry, repo: str, digest: str) -> List[str]:
    """Extract image references from a Helm chart blob."""
    token = get_bearer_token(registry)
    api_url = registry.api_url if registry else None
    if registry and registry.provider == 'jfrog':
        from .artifactory import get_helm_images as art_get_helm_images
        return art_get_helm_images(api_url, token, repo, digest)
    from .acr import get_helm_images as acr_get_helm_images
    return acr_get_helm_images(api_url, token, repo, digest)


def get_helm_chart_versions(registry, repo_key: str) -> list:
    """
    List chart versions from a native Helm repo in Artifactory (index.yaml).
    Returns list of (version, chart_name) for use in scan_repository_tags.
    """
    if registry.provider != 'jfrog':
        return []
    from .artifactory import get_helm_index
    token = get_bearer_token(registry)
    entries = get_helm_index(registry.api_url, token, repo_key)
    return [(e["version"], e["chart"]) for e in entries]


def get_helm_chart_url(registry, repo_key: str, chart_name: str, version: str) -> Optional[str]:
    """Get the .tgz URL for a chart version from Artifactory Helm repo index."""
    if registry.provider != 'jfrog':
        return None
    from .artifactory import get_helm_index
    token = get_bearer_token(registry)
    entries = get_helm_index(registry.api_url, token, repo_key)
    for e in entries:
        if e["chart"] == chart_name and e["version"] == version:
            return e.get("url")
    return None


def get_helm_images_from_native_chart(registry, chart_url: str) -> List[str]:
    """Download Helm chart .tgz from URL and extract image refs (for native Helm repos)."""
    if registry.provider != 'jfrog':
        return []
    from .artifactory import get_helm_images_from_native_chart as art_native
    token = get_bearer_token(registry)
    return art_native(registry.api_url, token, chart_url)
