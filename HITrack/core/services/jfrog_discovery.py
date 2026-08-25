"""Discover JFrog repo keys and persist their scan-ready applications."""

from collections import OrderedDict

from django.utils import timezone

from core.models import Repository
from core.utils.artifactory import get_repositories_rest
from core.utils.registry import get_bearer_token, get_catalog, get_repo_images


def _clean_positive_int(value, name, *, allow_none=False):
    if value is None and allow_none:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        suffix = ' or null' if allow_none else ''
        raise ValueError(f'{name} must be a positive integer{suffix}') from exc
    if parsed < 1:
        suffix = ' or null' if allow_none else ''
        raise ValueError(f'{name} must be a positive integer{suffix}')
    return parsed


def validate_discovery_options(
    *,
    include_docker=True,
    include_helm=True,
    catalog_page_size=500,
    max_projects_per_repo_key=None,
    batch_size=500,
):
    if not include_docker and not include_helm:
        raise ValueError('at least one of include_docker or include_helm must be true')
    return {
        'include_docker': include_docker,
        'include_helm': include_helm,
        'catalog_page_size': _clean_positive_int(
            catalog_page_size,
            'catalog_page_size',
        ),
        'max_projects_per_repo_key': _clean_positive_int(
            max_projects_per_repo_key,
            'max_projects_per_repo_key',
            allow_none=True,
        ),
        'batch_size': _clean_positive_int(batch_size, 'batch_size'),
    }


def _docker_projects(registry, repo_key, *, page_size, max_projects=None):
    """Read the complete paginated Docker catalog for one Artifactory repo key."""
    projects = []
    seen_projects = set()
    seen_page_tokens = set()
    last = None

    while True:
        names, next_page = get_catalog(
            registry,
            repo_key,
            page_size=page_size,
            last=last,
        )
        for name in names:
            normalized = str(name or '').strip().strip('/')
            if normalized and normalized not in seen_projects:
                seen_projects.add(normalized)
                projects.append(normalized)
                if max_projects is not None and len(projects) >= max_projects:
                    return projects

        if not next_page or next_page in seen_page_tokens or next_page == last:
            break
        seen_page_tokens.add(next_page)
        last = next_page

    return projects


def _helm_projects(registry, repo_key, *, max_projects=None):
    projects = []
    seen = set()
    for full_name, _url, _package_type, _repo_key in get_repo_images(
        registry,
        repo_key,
        package_type='helm',
    ):
        prefix = f'{repo_key}/'
        project = full_name[len(prefix):] if full_name.startswith(prefix) else full_name
        project = str(project or '').strip().strip('/')
        if project and project not in seen:
            seen.add(project)
            projects.append(project)
            if max_projects is not None and len(projects) >= max_projects:
                break
    return projects


def _repository_spec(registry, repo_key, project, package_type, activate_new):
    repo_key = str(repo_key or '').strip().strip('/')
    project = str(project or '').strip().strip('/')
    name = f'{repo_key}/{project}'
    base = str(registry.api_url or '').rstrip('/')
    url = f'{base}/{name}'

    if not repo_key or not project:
        raise ValueError('repo key and project name must not be empty')
    if any('\x00' in value for value in (repo_key, project, name, url)):
        raise ValueError('repo key and project name must not contain NUL characters')
    if len(repo_key) > 255:
        raise ValueError('repo key exceeds the 255 character database limit')
    if len(name) > 255:
        raise ValueError('repository name exceeds the 255 character database limit')
    if len(url) > 255:
        raise ValueError('repository URL exceeds the 255 character database limit')

    return {
        'name': name,
        'url': url,
        'repo_key': repo_key,
        'repository_type': package_type,
        'container_registry': registry,
        'status': bool(activate_new),
    }


def _persist_repositories(registry, specs, *, batch_size=500):
    """Bulk-create discoveries and repair source metadata without changing user status."""
    specs_by_url = OrderedDict((spec['url'], spec) for spec in specs)
    existing_by_url = Repository.objects.filter(
        url__in=specs_by_url,
    ).in_bulk(field_name='url')

    to_create = []
    to_update = []
    conflicts = []
    for url, spec in specs_by_url.items():
        existing = existing_by_url.get(url)
        if existing is None:
            to_create.append(Repository(**spec))
            continue
        if existing.container_registry_id not in (None, registry.pk):
            conflicts.append({
                'scope': 'repository',
                'repository': spec['name'],
                'error': 'canonical URL already belongs to another registry',
            })
            continue

        changed = False
        for field in ('name', 'repo_key', 'repository_type'):
            value = spec[field]
            if getattr(existing, field) != value:
                setattr(existing, field, value)
                changed = True
        if existing.container_registry_id != registry.pk:
            existing.container_registry = registry
            changed = True
        if changed:
            to_update.append(existing)

    if to_create:
        Repository.objects.bulk_create(
            to_create,
            batch_size=batch_size,
            ignore_conflicts=True,
        )
    if to_update:
        updated_at = timezone.now()
        for repository in to_update:
            repository.updated_at = updated_at
        Repository.objects.bulk_update(
            to_update,
            fields=['name', 'repo_key', 'repository_type', 'container_registry', 'updated_at'],
            batch_size=batch_size,
        )

    return {
        'created': len(to_create),
        'existing': len(existing_by_url) - len(conflicts),
        'updated': len(to_update),
        'conflicts': conflicts,
    }


def sync_jfrog_registry_repositories(
    registry,
    *,
    include_docker=True,
    include_helm=True,
    activate_new=True,
    catalog_page_size=500,
    max_projects_per_repo_key=None,
    batch_size=500,
):
    """Synchronize all discoverable JFrog applications for one registry."""
    if registry.provider != 'jfrog':
        raise ValueError('registry must use the jfrog provider')
    if not registry.api_url:
        raise ValueError('JFrog registry has no API URL configured')
    options = validate_discovery_options(
        include_docker=include_docker,
        include_helm=include_helm,
        catalog_page_size=catalog_page_size,
        max_projects_per_repo_key=max_projects_per_repo_key,
        batch_size=batch_size,
    )
    include_docker = options['include_docker']
    include_helm = options['include_helm']
    catalog_page_size = options['catalog_page_size']
    max_projects_per_repo_key = options['max_projects_per_repo_key']
    batch_size = options['batch_size']

    package_types = []
    if include_docker:
        package_types.append('docker')
    if include_helm:
        package_types.append('helm')

    errors = []
    discovered_keys = []
    token = get_bearer_token(registry)
    for package_type in package_types:
        try:
            repo_keys = get_repositories_rest(
                registry.api_url,
                token,
                package_type=package_type,
            )
        except Exception as exc:
            errors.append({
                'scope': 'package_type',
                'package_type': package_type,
                'error': str(exc),
            })
            continue
        for repo_key, _repo_url in repo_keys:
            discovered_keys.append((str(repo_key), package_type))

    # Artifactory should not return duplicates, but de-duplicating makes retries
    # deterministic if a virtual repository appears more than once.
    discovered_keys = list(OrderedDict.fromkeys(discovered_keys))
    specs = []
    successful_keys = 0
    for repo_key, package_type in discovered_keys:
        try:
            if package_type == 'helm':
                projects = _helm_projects(
                    registry,
                    repo_key,
                    max_projects=max_projects_per_repo_key,
                )
            else:
                projects = _docker_projects(
                    registry,
                    repo_key,
                    page_size=catalog_page_size,
                    max_projects=max_projects_per_repo_key,
                )
            successful_keys += 1
        except Exception as exc:
            errors.append({
                'scope': 'repo_key',
                'repo_key': repo_key,
                'package_type': package_type,
                'error': str(exc),
            })
            continue

        for project in projects:
            try:
                specs.append(_repository_spec(
                    registry,
                    repo_key,
                    project,
                    package_type,
                    activate_new,
                ))
            except ValueError as exc:
                errors.append({
                    'scope': 'project',
                    'repo_key': repo_key,
                    'project': str(project),
                    'package_type': package_type,
                    'error': str(exc),
                })

    persistence = _persist_repositories(registry, specs, batch_size=batch_size)
    errors.extend(persistence.pop('conflicts'))

    if not errors:
        registry.last_sync = timezone.now()
        registry.save(update_fields=['last_sync'])

    if errors and not successful_keys:
        sync_status = 'error'
    elif errors:
        sync_status = 'partial'
    else:
        sync_status = 'success'

    return {
        'registry': registry.name,
        'registry_uuid': str(registry.uuid),
        'status': sync_status,
        'repo_keys_discovered': len(discovered_keys),
        'repo_keys_succeeded': successful_keys,
        'projects_discovered': len(specs),
        **persistence,
        'errors': errors,
    }
