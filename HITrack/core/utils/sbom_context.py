from __future__ import annotations

from collections import defaultdict, deque
from typing import Iterable
from urllib.parse import parse_qsl, unquote


DEPENDENCY_SCOPE_DIRECT = 'direct'
DEPENDENCY_SCOPE_TRANSITIVE = 'transitive'
DEPENDENCY_SCOPE_UNKNOWN = 'unknown'

PACKAGE_SCOPE_RUNTIME = 'runtime'
PACKAGE_SCOPE_DEVELOPMENT = 'development'
PACKAGE_SCOPE_BUILD = 'build'
PACKAGE_SCOPE_TEST = 'test'
PACKAGE_SCOPE_OPTIONAL = 'optional'
PACKAGE_SCOPE_UNKNOWN = 'unknown'

_PACKAGE_SCOPE_PRIORITY = {
    PACKAGE_SCOPE_UNKNOWN: 0,
    PACKAGE_SCOPE_OPTIONAL: 1,
    PACKAGE_SCOPE_TEST: 2,
    PACKAGE_SCOPE_BUILD: 3,
    PACKAGE_SCOPE_DEVELOPMENT: 4,
    PACKAGE_SCOPE_RUNTIME: 5,
}

_PACKAGE_SCOPE_ALIASES = {
    'runtime': PACKAGE_SCOPE_RUNTIME,
    'production': PACKAGE_SCOPE_RUNTIME,
    'prod': PACKAGE_SCOPE_RUNTIME,
    'development': PACKAGE_SCOPE_DEVELOPMENT,
    'dev': PACKAGE_SCOPE_DEVELOPMENT,
    'build': PACKAGE_SCOPE_BUILD,
    'build-time': PACKAGE_SCOPE_BUILD,
    'test': PACKAGE_SCOPE_TEST,
    'testing': PACKAGE_SCOPE_TEST,
    'optional': PACKAGE_SCOPE_OPTIONAL,
}


def _clean_string(value) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _parse_purl(purl: str) -> dict | None:
    if not purl or not str(purl).startswith('pkg:'):
        return None

    package_reference = str(purl)[4:]
    package_reference, _, _ = package_reference.partition('#')
    package_reference, _, qualifier_string = package_reference.partition('?')
    package_path, _, version = package_reference.partition('@')
    segments = [unquote(segment).strip() for segment in package_path.split('/') if segment.strip()]
    if len(segments) < 2:
        return None

    qualifiers = {
        key.lower(): unquote(value).strip()
        for key, value in parse_qsl(qualifier_string, keep_blank_values=True)
        if key
    }

    return {
        'package_type': segments[0].lower(),
        'namespace': '/'.join(segment for segment in segments[1:-1]) or None,
        'package_name': segments[-1],
        'version': version or None,
        'qualifiers': qualifiers,
    }


def _normalize_package_scope(value) -> str:
    normalized = (_clean_string(value) or '').lower()
    return _PACKAGE_SCOPE_ALIASES.get(normalized, PACKAGE_SCOPE_UNKNOWN)


def _pick_preferred_scope(left: str, right: str) -> str:
    return left if _PACKAGE_SCOPE_PRIORITY.get(left, 0) >= _PACKAGE_SCOPE_PRIORITY.get(right, 0) else right


def _extract_string_from_metadata(metadata, *keys) -> str | None:
    if not isinstance(metadata, dict):
        return None

    for key in keys:
        value = metadata.get(key)
        if isinstance(value, dict):
            nested = _clean_string(value.get('name')) or _clean_string(value.get('value'))
            if nested:
                return nested
            continue
        cleaned = _clean_string(value)
        if cleaned:
            return cleaned
    return None


def _extract_dependency_metadata(relationships, artifact_ids: Iterable[str]) -> dict[str, dict]:
    artifact_id_set = {artifact_id for artifact_id in artifact_ids if artifact_id}
    if not artifact_id_set:
        return {}

    adjacency: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = defaultdict(int)
    package_scope_by_artifact: dict[str, str] = defaultdict(lambda: PACKAGE_SCOPE_UNKNOWN)
    graph_nodes: set[str] = set()

    for relationship in relationships or []:
        if (relationship or {}).get('type') != 'dependency-of':
            continue
        parent = relationship.get('parent')
        child = relationship.get('child')
        if parent not in artifact_id_set or child not in artifact_id_set:
            continue
        if child not in adjacency[parent]:
            adjacency[parent].add(child)
            indegree[child] += 1
        graph_nodes.add(parent)
        graph_nodes.add(child)

        metadata = relationship.get('metadata') or {}
        scope = PACKAGE_SCOPE_UNKNOWN
        for key in ('kind', 'scope', 'dependencyType', 'type'):
            scope = _normalize_package_scope(metadata.get(key))
            if scope != PACKAGE_SCOPE_UNKNOWN:
                break
        if scope != PACKAGE_SCOPE_UNKNOWN:
            package_scope_by_artifact[parent] = _pick_preferred_scope(package_scope_by_artifact[parent], scope)
            package_scope_by_artifact[child] = _pick_preferred_scope(package_scope_by_artifact[child], scope)

    if not graph_nodes:
        return {}

    roots = [artifact_id for artifact_id in artifact_id_set if indegree.get(artifact_id, 0) == 0]
    queue = deque((root, 0) for root in roots)
    depths: dict[str, int] = {}

    while queue:
        artifact_id, depth = queue.popleft()
        current_depth = depths.get(artifact_id)
        if current_depth is not None and current_depth <= depth:
            continue
        depths[artifact_id] = depth
        for child in adjacency.get(artifact_id, ()):
            queue.append((child, depth + 1))

    dependency_metadata = {}
    for artifact_id in artifact_id_set:
        if artifact_id not in graph_nodes:
            dependency_metadata[artifact_id] = {
                'dependency_scope': DEPENDENCY_SCOPE_DIRECT,
                'dependency_depth': 0,
                'package_scope': package_scope_by_artifact[artifact_id],
            }
            continue

        depth = depths.get(artifact_id)
        if depth is None:
            dependency_scope = DEPENDENCY_SCOPE_UNKNOWN
        elif depth == 0:
            dependency_scope = DEPENDENCY_SCOPE_DIRECT
        else:
            dependency_scope = DEPENDENCY_SCOPE_TRANSITIVE

        dependency_metadata[artifact_id] = {
            'dependency_scope': dependency_scope,
            'dependency_depth': depth,
            'package_scope': package_scope_by_artifact[artifact_id],
        }

    return dependency_metadata


def _extract_artifact_context(artifact, dependency_metadata_by_id) -> dict | None:
    name = _clean_string((artifact or {}).get('name'))
    version = _clean_string((artifact or {}).get('version'))
    if not name or not version:
        return None

    metadata = artifact.get('metadata') or {}
    parsed_purl = _parse_purl(artifact.get('purl') or '')
    qualifiers = (parsed_purl or {}).get('qualifiers', {})
    artifact_id = _clean_string(artifact.get('id'))
    dependency_metadata = dependency_metadata_by_id.get(artifact_id) or {
        'dependency_scope': DEPENDENCY_SCOPE_UNKNOWN,
        'dependency_depth': None,
        'package_scope': PACKAGE_SCOPE_UNKNOWN,
    }

    package_arch = _clean_string(qualifiers.get('arch')) or _extract_string_from_metadata(metadata, 'architecture', 'arch')
    package_distro = _clean_string(qualifiers.get('distro')) or _extract_string_from_metadata(metadata, 'distribution', 'distro')
    package_repo = (
        _clean_string(qualifiers.get('repository'))
        or _clean_string(qualifiers.get('repo'))
        or _extract_string_from_metadata(metadata, 'repository', 'repo')
    )
    package_channel = (
        _clean_string(qualifiers.get('channel'))
        or _clean_string(qualifiers.get('stream'))
        or _extract_string_from_metadata(metadata, 'channel', 'stream')
    )
    source_package = _extract_string_from_metadata(metadata, 'source', 'sourcePackage', 'sourceRpm')
    source_package_version = _extract_string_from_metadata(
        metadata,
        'sourceVersion',
        'sourcePackageVersion',
        'sourceRpmVersion',
    )

    return {
        'name': name,
        'version': version,
        'cataloger': _clean_string(artifact.get('foundBy')) or '',
        'metadata_type': _clean_string(artifact.get('metadataType')) or '',
        'dependency_scope': dependency_metadata['dependency_scope'],
        'dependency_depth': dependency_metadata['dependency_depth'],
        'package_scope': dependency_metadata['package_scope'],
        'package_arch': package_arch,
        'package_distro': package_distro,
        'package_repo': package_repo,
        'package_channel': package_channel,
        'source_package': source_package,
        'source_package_version': source_package_version,
    }


def _merge_artifact_context(existing: dict | None, incoming: dict) -> dict:
    if existing is None:
        return incoming.copy()

    merged = existing.copy()

    existing_depth = merged.get('dependency_depth')
    incoming_depth = incoming.get('dependency_depth')
    if existing_depth is None or (incoming_depth is not None and incoming_depth < existing_depth):
        merged['dependency_depth'] = incoming_depth
        merged['dependency_scope'] = incoming.get('dependency_scope', merged.get('dependency_scope'))
    elif merged.get('dependency_scope') == DEPENDENCY_SCOPE_UNKNOWN and incoming.get('dependency_scope') != DEPENDENCY_SCOPE_UNKNOWN:
        merged['dependency_scope'] = incoming['dependency_scope']

    merged['package_scope'] = _pick_preferred_scope(
        merged.get('package_scope', PACKAGE_SCOPE_UNKNOWN),
        incoming.get('package_scope', PACKAGE_SCOPE_UNKNOWN),
    )

    for field_name in (
        'cataloger',
        'metadata_type',
        'package_arch',
        'package_distro',
        'package_repo',
        'package_channel',
        'source_package',
        'source_package_version',
    ):
        if not merged.get(field_name) and incoming.get(field_name):
            merged[field_name] = incoming[field_name]

    return merged


def build_image_component_context_map(sbom_data) -> dict[tuple[str, str], dict]:
    if not isinstance(sbom_data, dict):
        return {}

    artifacts = sbom_data.get('artifacts') or []
    relationships = sbom_data.get('artifactRelationships') or sbom_data.get('relationships') or []
    dependency_metadata_by_id = _extract_dependency_metadata(
        relationships,
        [artifact.get('id') for artifact in artifacts if isinstance(artifact, dict)],
    )

    context_map: dict[tuple[str, str], dict] = {}
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        extracted = _extract_artifact_context(artifact, dependency_metadata_by_id)
        if not extracted:
            continue
        key = (extracted['name'], extracted['version'])
        context_map[key] = _merge_artifact_context(context_map.get(key), extracted)

    return context_map
