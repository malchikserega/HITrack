import re
from urllib.parse import urlparse

from django.db.models import Q

from core.models import ContainerRegistry, Image


IMAGE_REFERENCE_RE = re.compile(
    r'^(?=.{1,255}$)(?:[a-zA-Z0-9.-]+(?::[0-9]+)?/)?'
    r'[a-zA-Z0-9_./-]+(?:[:][a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}|@sha256:[a-fA-F0-9]{64})?$'
)
DOCKER_HUB_HOSTS = {'docker.io', 'index.docker.io', 'registry-1.docker.io'}


def normalize_image_reference(value):
    reference = str(value or '').strip()
    if reference.startswith(('http://', 'https://')):
        parsed = urlparse(reference)
        reference = f'{parsed.netloc}{parsed.path}'.rstrip('/')
    reference = reference.rstrip('/')
    if not reference or not IMAGE_REFERENCE_RE.fullmatch(reference):
        raise ValueError('Enter a valid OCI image reference including its registry and tag or digest.')
    if '/' not in reference:
        raise ValueError('The image reference must include a registry host.')
    return reference


def image_registry_host(reference):
    return reference.split('/', 1)[0].lower()


def registry_host(registry):
    value = str(registry.api_url or '').strip()
    if not value:
        value = registry.name
    if '://' not in value:
        value = f'https://{value}'
    return (urlparse(value).hostname or '').lower()


def find_registry_for_reference(reference, registries=None):
    host = image_registry_host(reference)
    candidates = registries if registries is not None else ContainerRegistry.objects.all()
    for registry in candidates:
        configured_host = registry_host(registry)
        if configured_host == host or ({configured_host, host} <= DOCKER_HUB_HOSTS):
            return registry
    return None


def find_existing_image(reference):
    return Image.objects.filter(
        Q(artifact_reference__iexact=reference) | Q(name__iexact=reference)
    ).order_by('-updated_at').first()


def inspect_image_references(values):
    registries = list(ContainerRegistry.objects.all())
    rows = []
    seen = set()
    for raw_value in values:
        try:
            reference = normalize_image_reference(raw_value)
        except ValueError as exc:
            rows.append({'reference': str(raw_value or '').strip(), 'valid': False, 'error': str(exc)})
            continue
        key = reference.lower()
        if key in seen:
            continue
        seen.add(key)
        image = find_existing_image(reference)
        registry = find_registry_for_reference(reference, registries)
        rows.append({
            'reference': reference,
            'valid': True,
            'exists': image is not None,
            'image': ({
                'uuid': str(image.uuid),
                'name': image.name,
                'scan_status': image.scan_status,
            } if image else None),
            'registry': ({
                'uuid': str(registry.uuid),
                'name': registry.name,
                'provider': registry.provider,
            } if registry else None),
            'scan_supported': True,
            'authenticated_scan': registry is not None,
        })
    return rows
