"""Minimal Docker Registry HTTP API v2 client for non-ACR OCI registries."""

from __future__ import annotations

import base64
import re
from typing import Generator, Optional, Tuple
from urllib.parse import quote, urljoin, urlparse

import requests


MANIFEST_ACCEPT = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])


def _base_url(api_url: str) -> str:
    value = str(api_url or "").strip().rstrip("/")
    if not value:
        raise ValueError("Registry API URL is required")
    if "://" not in value:
        value = f"https://{value}"
    return value


def _registry_host(api_url: str) -> str:
    return urlparse(_base_url(api_url)).netloc


def _basic_header(login: str, password: str) -> str:
    encoded = base64.b64encode(f"{login}:{password}".encode()).decode()
    return f"Basic {encoded}"


def _parse_bearer_challenge(header: str) -> dict:
    if not header or not header.lower().startswith("bearer "):
        return {}
    values = {}
    for key, value in re.findall(r'(\w+)="([^"]*)"', header[7:]):
        values[key.lower()] = value
    return values


def _request(registry, method: str, path_or_url: str, *, scope: str = "", headers=None):
    base = _base_url(registry.api_url)
    url = path_or_url if path_or_url.startswith(("http://", "https://")) else urljoin(f"{base}/", path_or_url.lstrip("/"))
    request_headers = dict(headers or {})
    if registry.token:
        request_headers["Authorization"] = f"Bearer {registry.token}"
    elif registry.login and registry.password:
        request_headers["Authorization"] = _basic_header(registry.login, registry.password)

    response = requests.request(method, url, headers=request_headers, timeout=60)
    if response.status_code != 401:
        response.raise_for_status()
        return response

    challenge_header = response.headers.get("WWW-Authenticate", "")
    challenge = _parse_bearer_challenge(challenge_header)
    if challenge:
        params = {"service": challenge.get("service", _registry_host(registry.api_url))}
        effective_scope = scope or challenge.get("scope", "")
        if effective_scope:
            params["scope"] = effective_scope
        auth = (registry.login, registry.password) if registry.login and registry.password else None
        token_response = requests.get(challenge["realm"], params=params, auth=auth, timeout=60)
        token_response.raise_for_status()
        payload = token_response.json()
        token = payload.get("token") or payload.get("access_token")
        if not token:
            raise RuntimeError("Registry token endpoint returned no token")
        request_headers["Authorization"] = f"Bearer {token}"
    elif challenge_header.lower().startswith("basic ") and registry.login and registry.password:
        request_headers["Authorization"] = _basic_header(registry.login, registry.password)
    else:
        response.raise_for_status()

    response = requests.request(method, url, headers=request_headers, timeout=60)
    response.raise_for_status()
    return response


def get_repositories(registry, page_size: int = 100, last_repo: str = None) -> Tuple[list, Optional[str]]:
    path = f"/v2/_catalog?n={int(page_size)}"
    if last_repo:
        path += f"&last={quote(last_repo, safe='')}"
    response = _request(registry, "GET", path, scope="registry:catalog:*")
    repositories = response.json().get("repositories") or []
    host = _registry_host(registry.api_url)
    next_page = None
    link = response.links.get("next", {}).get("url")
    if link:
        match = re.search(r"[?&]last=([^&>]+)", link)
        if match:
            next_page = match.group(1)
    return [(name, f"{host}/{name}") for name in repositories], next_page


def get_dockerhub_repositories(registry, page_size: int = 100, last_repo: str = None) -> Tuple[list, Optional[str]]:
    """List repositories in the configured Docker Hub user namespace."""
    if not registry.login:
        raise ValueError("Docker Hub repository discovery requires the namespace in the login field")
    page = int(last_repo or 1)
    url = f"https://hub.docker.com/v2/repositories/{quote(registry.login, safe='')}/?page_size={int(page_size)}&page={page}"
    headers = {}
    if registry.password:
        login_response = requests.post(
            "https://hub.docker.com/v2/users/login",
            json={"username": registry.login, "password": registry.password},
            timeout=60,
        )
        login_response.raise_for_status()
        hub_token = login_response.json().get("token")
        if not hub_token:
            raise RuntimeError("Docker Hub login returned no token")
        headers["Authorization"] = f"Bearer {hub_token}"
    elif registry.token:
        # The token field can hold an already-issued Docker Hub API JWT.
        headers["Authorization"] = f"Bearer {registry.token}"
    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results") or []
    repositories = []
    for row in results:
        namespace = row.get("namespace") or registry.login
        name = row.get("name")
        if name:
            full_name = f"{namespace}/{name}"
            repositories.append((full_name, f"registry-1.docker.io/{full_name}"))
    return repositories, str(page + 1) if payload.get("next") else None


def get_tags(registry, repo: str, limit: int = None) -> Generator[str, None, None]:
    count = 0
    page_size = int(limit or 500)
    url = f"/v2/{quote(repo, safe='/')}/tags/list?n={page_size}"
    scope = f"repository:{repo}:pull"
    while url:
        response = _request(registry, "GET", url, scope=scope)
        payload = response.json()
        for tag in payload.get("tags") or []:
            yield tag
            count += 1
            if limit is not None and count >= limit:
                return
        url = response.links.get("next", {}).get("url")


def get_manifest(registry, repo: str, tag: str) -> Tuple[Optional[dict], Optional[str]]:
    response = _request(
        registry,
        "GET",
        f"/v2/{quote(repo, safe='/')}/manifests/{quote(tag, safe=':@')}",
        scope=f"repository:{repo}:pull",
        headers={"Accept": MANIFEST_ACCEPT},
    )
    return response.json(), response.headers.get("Docker-Content-Digest")


def get_blob(registry, repo: str, digest: str) -> bytes:
    response = _request(
        registry,
        "GET",
        f"/v2/{quote(repo, safe='/')}/blobs/{quote(digest, safe=':')}",
        scope=f"repository:{repo}:pull",
    )
    return response.content


def get_image_digest(registry, image_ref: str) -> Optional[str]:
    host = _registry_host(registry.api_url)
    value = image_ref.split(f"{host}/", 1)[-1]
    if "@" in value:
        repo, reference = value.rsplit("@", 1)
    elif ":" in value.rsplit("/", 1)[-1]:
        repo, reference = value.rsplit(":", 1)
    else:
        repo, reference = value, "latest"
    _manifest, digest = get_manifest(registry, repo, reference)
    return digest
