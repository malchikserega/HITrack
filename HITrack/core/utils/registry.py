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
    """List repositories with pagination. For jfrog uses Artifactory REST API (repo keys)."""
    token = get_bearer_token(registry)
    if registry.provider == 'jfrog':
        from .artifactory import get_repositories_rest
        repos = get_repositories_rest(registry.api_url, token, package_type='docker')
        return (repos, None)
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


def get_image_digest(registry, image_ref: str) -> Optional[str]:
    """Get image digest from the registry (ACR or Artifactory)."""
    if not registry:
        return None
    if registry.provider == 'jfrog':
        from .artifactory import get_artifactory_image_digest
        return get_artifactory_image_digest(registry.api_url, get_bearer_token(registry), image_ref)
    from .acr import get_acr_image_digest
    return get_acr_image_digest(registry.api_url, get_bearer_token(registry), image_ref)


def get_helm_images(registry, repo: str, digest: str) -> List[str]:
    """Extract image references from a Helm chart blob."""
    token = get_bearer_token(registry)
    api_url = registry.api_url if registry else None
    if registry and registry.provider == 'jfrog':
        from .artifactory import get_helm_images as art_get_helm_images
        return art_get_helm_images(api_url, token, repo, digest)
    from .acr import get_helm_images as acr_get_helm_images
    return acr_get_helm_images(api_url, token, repo, digest)
