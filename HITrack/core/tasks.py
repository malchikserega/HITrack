from __future__ import absolute_import, unicode_literals

from hitrack_celery.celery import celery_app
import hashlib
import html
import logging
import os
import re
import subprocess
import time
from datetime import timedelta
from urllib.parse import parse_qsl, unquote, urlparse

import requests
from django.utils import timezone
from typing import List, Dict
from django.db import connection, transaction
from django.db.models import Count, Q
from .utils.status import resolve_repository_tag_processing_status

# Performance and logging configuration
# Set DEBUG_LOGGING=true environment variable to enable debug logging
# Set DEBUG_LOGGING=false or unset to disable debug logging for production
#
# Performance optimizations implemented:
# - Database queries optimized with select_related and prefetch_related
# - Bulk operations for better performance
# - Conditional debug logging to reduce I/O overhead
# - Task retry mechanisms with exponential backoff
# - Performance monitoring task for system health checks

# Configure logging
logger = logging.getLogger(__name__)

# Remove debug logging in production
DEBUG_LOGGING = os.getenv('DEBUG_LOGGING', 'False').lower() == 'true'

# SBOM task: docker pull + Syft/Grype often exceeds global CELERY_TASK_SOFT_TIME_LIMIT (420s)
GENERATE_SBOM_SOFT_TIME_LIMIT = int(os.getenv("HITRACK_SBOM_SOFT_TIME_LIMIT", "3600"))
GENERATE_SBOM_TIME_LIMIT = int(os.getenv("HITRACK_SBOM_TIME_LIMIT", "4200"))

DOCKER_IMAGE_REGEX = re.compile(r'^[a-zA-Z0-9._/-]+(:[a-zA-Z0-9._-]+)?$')
_LINEAGE_SOURCE_PRIORITY = {
    'unknown': 0,
    'package_distro': 1,
    'sbom_distro': 2,
}
_OS_EOL_STATUS_PRIORITY = {
    'unknown': 0,
    'supported': 1,
    'eol': 2,
}

def is_safe_image_ref(image_ref: str) -> bool:
    return bool(DOCKER_IMAGE_REGEX.match(image_ref)) and len(image_ref) < 200


def _apply_image_lineage_fields(image, component_version_purls=None):
    from .utils.lineage import derive_image_lineage, image_lineage_to_update_fields

    if component_version_purls is None:
        component_version_purls = image.component_versions.filter(
            component__type__in=['deb', 'rpm', 'apk']
        ).values_list('purl', flat=True)

    lineage = derive_image_lineage(
        sbom_data=image.sbom_data,
        component_version_purls=component_version_purls,
    )
    desired_fields = image_lineage_to_update_fields(lineage)
    update_fields = []

    for field_name, desired_value in desired_fields.items():
        if getattr(image, field_name) != desired_value:
            setattr(image, field_name, desired_value)
            update_fields.append(field_name)

    if update_fields or image.lineage_updated_at is None:
        image.lineage_updated_at = timezone.now()
        update_fields.append('lineage_updated_at')

    return update_fields


def _copy_image_lineage_fields(source_image, target_image):
    source_priority = _LINEAGE_SOURCE_PRIORITY.get(source_image.lineage_source or 'unknown', 0)
    target_priority = _LINEAGE_SOURCE_PRIORITY.get(target_image.lineage_source or 'unknown', 0)

    if source_priority == 0:
        return []

    should_replace = (
        target_priority == 0
        or source_priority > target_priority
        or (
            source_priority == target_priority
            and (target_image.lineage_updated_at is None or (
                source_image.lineage_updated_at and source_image.lineage_updated_at > target_image.lineage_updated_at
            ))
        )
    )
    if not should_replace:
        return []

    update_fields = []
    for field_name in ('lineage_label', 'lineage_source', 'os_distro_name', 'os_distro_version'):
        source_value = getattr(source_image, field_name)
        if getattr(target_image, field_name) != source_value:
            setattr(target_image, field_name, source_value)
            update_fields.append(field_name)

    if update_fields:
        target_image.lineage_updated_at = source_image.lineage_updated_at or timezone.now()
        update_fields.append('lineage_updated_at')

    return update_fields


def _apply_image_os_eol_fields(image, grype_data=None):
    from .utils.os_eol import derive_image_os_eol_status, image_os_eol_to_update_fields

    image_os_eol = derive_image_os_eol_status(
        grype_data=grype_data if grype_data is not None else image.grype_data,
        os_distro_name=image.os_distro_name,
        lineage_label=image.lineage_label,
    )
    desired_fields = image_os_eol_to_update_fields(image_os_eol)
    update_fields = []

    for field_name, desired_value in desired_fields.items():
        if getattr(image, field_name) != desired_value:
            setattr(image, field_name, desired_value)
            update_fields.append(field_name)

    if update_fields or image.os_eol_checked_at is None:
        image.os_eol_checked_at = timezone.now()
        update_fields.append('os_eol_checked_at')

    return update_fields


def _copy_image_os_eol_fields(source_image, target_image):
    source_priority = _OS_EOL_STATUS_PRIORITY.get(source_image.os_eol_status or 'unknown', 0)
    target_priority = _OS_EOL_STATUS_PRIORITY.get(target_image.os_eol_status or 'unknown', 0)

    if source_priority == 0:
        return []

    should_replace = (
        target_priority == 0
        or source_priority > target_priority
        or (
            source_priority == target_priority
            and (target_image.os_eol_checked_at is None or (
                source_image.os_eol_checked_at and source_image.os_eol_checked_at > target_image.os_eol_checked_at
            ))
        )
    )
    if not should_replace:
        return []

    update_fields = []
    for field_name in ('os_eol_status', 'os_eol_source', 'os_eol_message'):
        source_value = getattr(source_image, field_name)
        if getattr(target_image, field_name) != source_value:
            setattr(target_image, field_name, source_value)
            update_fields.append(field_name)

    if update_fields:
        target_image.os_eol_checked_at = source_image.os_eol_checked_at or timezone.now()
        update_fields.append('os_eol_checked_at')

    return update_fields


def _upsert_image_component_version_contexts(image, sbom_data=None):
    from .models import ComponentVersion, ImageComponentVersionContext
    from .utils.sbom_context import build_image_component_context_map

    current_sbom_data = sbom_data if sbom_data is not None else image.sbom_data
    if not current_sbom_data:
        return {
            'contexts_created': 0,
            'contexts_updated': 0,
            'contexts_deleted': 0,
        }

    context_map = build_image_component_context_map(current_sbom_data)
    component_versions = list(
        ComponentVersion.objects.filter(images=image).select_related('component')
    )
    component_version_by_key = {
        (component_version.component.name, component_version.version): component_version
        for component_version in component_versions
    }
    existing_contexts = {
        context.component_version_id: context
        for context in ImageComponentVersionContext.objects.filter(image=image)
    }

    to_create = []
    to_update = []
    matched_component_version_ids = set()
    now = timezone.now()

    field_names = [
        'cataloger',
        'metadata_type',
        'dependency_scope',
        'dependency_depth',
        'immediate_parent_name',
        'immediate_parent_version',
        'direct_introducer_name',
        'direct_introducer_version',
        'package_scope',
        'package_arch',
        'package_distro',
        'package_repo',
        'package_channel',
        'source_package',
        'source_package_version',
    ]

    for key, context_data in context_map.items():
        component_version = component_version_by_key.get(key)
        if component_version is None:
            continue
        matched_component_version_ids.add(component_version.pk)
        existing_context = existing_contexts.get(component_version.pk)

        if existing_context is None:
            to_create.append(
                ImageComponentVersionContext(
                    image=image,
                    component_version=component_version,
                    **{field_name: context_data.get(field_name) for field_name in field_names},
                )
            )
            continue

        updated = False
        for field_name in field_names:
            desired_value = context_data.get(field_name)
            if getattr(existing_context, field_name) != desired_value:
                setattr(existing_context, field_name, desired_value)
                updated = True
        if updated:
            existing_context.updated_at = now
            to_update.append(existing_context)

    stale_context_ids = [
        context.uuid
        for component_version_id, context in existing_contexts.items()
        if component_version_id not in matched_component_version_ids
    ]
    contexts_deleted = 0
    if stale_context_ids:
        contexts_deleted = ImageComponentVersionContext.objects.filter(uuid__in=stale_context_ids).delete()[0]

    if to_create:
        ImageComponentVersionContext.objects.bulk_create(to_create, batch_size=500)
    if to_update:
        ImageComponentVersionContext.objects.bulk_update(
            to_update,
            field_names + ['updated_at'],
            batch_size=500,
        )

    return {
        'contexts_created': len(to_create),
        'contexts_updated': len(to_update),
        'contexts_deleted': contexts_deleted,
    }


_PKG_VERSION_CACHE_TTL = 3600  # 1 hour
VULNERABILITY_DETAILS_FRESHNESS_HOURS = 24
ENRICHMENT_BATCH_SIZE = 100
CRITICAL_ENRICHMENT_BATCH_SIZE = 50
_DEBIAN_DISTRO_SERIES_MAP = {
    "10": "buster",
    "11": "bullseye",
    "12": "bookworm",
    "13": "trixie",
    "14": "forky",
    "buster": "buster",
    "bullseye": "bullseye",
    "bookworm": "bookworm",
    "trixie": "trixie",
    "forky": "forky",
    "sid": "sid",
    "unstable": "sid",
    "testing": "testing",
    "stable": "stable",
    "oldstable": "oldstable",
}
_UBUNTU_DISTRO_SERIES_MAP = {
    "18.04": "bionic",
    "20.04": "focal",
    "22.04": "jammy",
    "24.04": "noble",
    "24.10": "oracular",
    "25.04": "plucky",
    "25.10": "questing",
    "26.04": "resolute",
    "bionic": "bionic",
    "focal": "focal",
    "jammy": "jammy",
    "noble": "noble",
    "oracular": "oracular",
    "plucky": "plucky",
    "questing": "questing",
    "resolute": "resolute",
    "devel": "devel",
}


def _build_latest_version_cache_key(package_type: str, package_name: str, context: str | None = None) -> str:
    key = f"pkg_ver:{package_type}:{package_name}"
    if context:
        key = f"{key}:{context}"
    return key


def _get_cached_latest_version(package_type: str, package_name: str, context: str | None = None) -> str | None:
    """Check Redis cache for a previously fetched latest package version."""
    from django.core.cache import cache
    return cache.get(_build_latest_version_cache_key(package_type, package_name, context))


def _set_cached_latest_version(package_type: str, package_name: str, version: str, context: str | None = None):
    from django.core.cache import cache
    cache.set(
        _build_latest_version_cache_key(package_type, package_name, context),
        version,
        _PKG_VERSION_CACHE_TTL,
    )


def _parse_purl_metadata(purl: str) -> dict | None:
    if not purl or not str(purl).startswith("pkg:"):
        return None

    package_reference = str(purl)[4:]
    package_reference, _, _ = package_reference.partition("#")
    package_reference, _, qualifier_string = package_reference.partition("?")
    package_path, _, version = package_reference.partition("@")
    segments = [unquote(segment).strip() for segment in package_path.split("/") if segment.strip()]
    if len(segments) < 2:
        return None

    package_type = segments[0].lower()
    namespace_segments = [segment.lower() for segment in segments[1:-1]]
    package_name = segments[-1].lower()
    qualifiers = {
        key.lower(): unquote(value).strip().lower()
        for key, value in parse_qsl(qualifier_string, keep_blank_values=True)
        if key
    }

    full_name = "/".join([*namespace_segments, package_name]) if namespace_segments else package_name
    namespace = "/".join(namespace_segments) if namespace_segments else None

    return {
        "package_type": package_type,
        "package_name": package_name,
        "namespace": namespace,
        "full_name": full_name,
        "version": version,
        "qualifiers": qualifiers,
    }


def _resolve_deb_distribution(metadata: dict) -> tuple[str | None, str | None, str | None]:
    qualifiers = metadata.get("qualifiers") or {}
    namespace = (metadata.get("namespace") or "").split("/", 1)[0].strip().lower()
    distro_value = (qualifiers.get("distro") or "").strip().lower()
    arch = (qualifiers.get("arch") or "").strip().lower() or None

    family = None
    raw_series = ""

    if distro_value.startswith("debian"):
        family = "debian"
        raw_series = distro_value.removeprefix("debian").lstrip("-_/")
    elif distro_value.startswith("ubuntu"):
        family = "ubuntu"
        raw_series = distro_value.removeprefix("ubuntu").lstrip("-_/")
    elif distro_value:
        raw_series = distro_value

    if family is None and namespace in {"debian", "ubuntu"}:
        family = namespace

    if not raw_series:
        raw_series = namespace if namespace not in {"debian", "ubuntu"} else ""

    if family == "debian":
        series = _DEBIAN_DISTRO_SERIES_MAP.get(raw_series)
    elif family == "ubuntu":
        series = _UBUNTU_DISTRO_SERIES_MAP.get(raw_series)
    else:
        series = None

    return family, series, arch


def _extract_deb_version_from_package_page(response_text: str, package_name: str, arch: str | None = None) -> str | None:
    plain_text = html.unescape(response_text or "")

    if arch:
        arch_row_match = re.search(
            rf"{re.escape(arch)}\s+([0-9A-Za-z.+:~\-]+)\s+\d",
            plain_text,
            re.IGNORECASE,
        )
        if arch_row_match:
            return arch_row_match.group(1).strip()

    title_match = re.search(
        rf"(?:#\s*)?Package:\s*{re.escape(package_name)}\s*\(([^)]+)\)",
        plain_text,
        re.IGNORECASE,
    )
    if title_match:
        version_text = title_match.group(1).split(" and others", 1)[0].strip()
        if version_text:
            return version_text

    return None


def _lookup_deb_latest_version_from_packages_site(package_name: str, family: str | None, series: str | None, arch: str | None) -> str | None:
    if not family or not series:
        return None

    if family == "debian":
        path_parts = [series]
        if arch:
            path_parts.append(arch)
        path_parts.append(package_name)
        url = f"https://packages.debian.org/{'/'.join(path_parts)}"
    elif family == "ubuntu":
        url = f"https://packages.ubuntu.com/{series}/{package_name}"
    else:
        return None

    response = requests.get(url, timeout=10)
    if not response.ok:
        return None

    return _extract_deb_version_from_package_page(response.text, package_name, arch=arch)


def _lookup_latest_version_for_purl(purl: str) -> str | None:
    metadata = _parse_purl_metadata(purl)
    if not metadata:
        return None

    package_type = metadata["package_type"]
    package_name = metadata["package_name"]
    full_name = metadata["full_name"]
    cache_context = None

    if package_type == "deb":
        family, series, arch = _resolve_deb_distribution(metadata)
        cache_context = ":".join(part for part in [family, series, arch] if part) or None
        latest_version = _get_cached_latest_version(package_type, package_name, cache_context)
        if latest_version is not None:
            return latest_version

        try:
            latest_version = _lookup_deb_latest_version_from_packages_site(package_name, family, series, arch)
        except Exception:
            latest_version = None

        if latest_version is None:
            try:
                output = subprocess.check_output(
                    ["apt-cache", "policy", package_name],
                    text=True,
                    timeout=5,
                )
                for line in output.splitlines():
                    if "Candidate:" in line:
                        candidate = line.split(":", 1)[1].strip()
                        latest_version = candidate if candidate and candidate != "(none)" else None
                        break
            except Exception:
                latest_version = None

        if latest_version:
            _set_cached_latest_version(package_type, package_name, latest_version, cache_context)
        return latest_version

    latest_version = _get_cached_latest_version(package_type, full_name)
    if latest_version is not None:
        return latest_version

    if package_type == "pypi":
        url = f"https://pypi.org/pypi/{full_name}/json"
        response = requests.get(url, timeout=5)
        if response.ok:
            latest_version = response.json()["info"]["version"]
    elif package_type == "npm":
        url = f"https://registry.npmjs.org/{full_name}"
        response = requests.get(url, timeout=5)
        if response.ok:
            latest_version = response.json()["dist-tags"]["latest"]
    elif package_type == "nuget":
        url = f"https://api.nuget.org/v3-flatcontainer/{full_name}/index.json"
        response = requests.get(url, timeout=5)
        if response.ok:
            versions = response.json().get("versions", [])
            latest_version = versions[-1] if versions else None
    elif package_type == "golang":
        if full_name == "stdlib":
            url = "https://golang.org/dl/?mode=json"
            response = requests.get(url, timeout=5)
            if response.ok:
                versions = response.json()
                stable_versions = [
                    version_info["version"]
                    for version_info in versions
                    if not version_info["version"].endswith("beta")
                    and not version_info["version"].endswith("rc")
                ]
                if stable_versions:
                    latest_version = max(stable_versions).replace("go", "")
        else:
            url = f"https://proxy.golang.org/{full_name}/@latest"
            response = requests.get(url, timeout=5)
            if response.ok:
                latest_version = response.json().get("Version", "").replace("v", "")

    if latest_version:
        _set_cached_latest_version(package_type, full_name, latest_version)
    return latest_version


def _normalize_fix_versions(raw_versions) -> list[str]:
    if not isinstance(raw_versions, list):
        return []

    normalized_versions = []
    seen_versions = set()
    for raw_version in raw_versions:
        version = str(raw_version).strip()
        if not version or version in seen_versions:
            continue
        seen_versions.add(version)
        normalized_versions.append(version)
    return normalized_versions


def _normalize_fix_state(raw_state) -> str | None:
    state = str(raw_state or "").strip().lower()
    return state or None


def _is_deb_component_version(component_version_obj) -> bool:
    component = getattr(component_version_obj, 'component', None)
    component_type = getattr(component, 'type', None)
    if str(component_type or '').lower() == 'deb':
        return True

    metadata = _parse_purl_metadata(getattr(component_version_obj, 'purl', None))
    return bool(metadata and metadata.get('package_type') == 'deb')


def _dpkg_version_gte(left_version: str, right_version: str) -> bool | None:
    if not left_version or not right_version:
        return None

    try:
        result = subprocess.run(
            ['dpkg', '--compare-versions', str(left_version), 'ge', str(right_version)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, OSError):
        return None

    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def _determine_fix_metadata(component_version_obj, vulnerability_data: dict) -> dict:
    fix_data = vulnerability_data.get('fix', {})
    if not isinstance(fix_data, dict):
        fix_data = {}

    fix_versions = _normalize_fix_versions(fix_data.get('versions', []))
    raw_fix_state = str(fix_data.get('state', '') or '').strip() or None
    normalized_fix_state = _normalize_fix_state(raw_fix_state)

    fixable = bool(fix_versions)
    fix_status = 'unknown'

    if fix_versions:
        fix_status = 'available'
        if _is_deb_component_version(component_version_obj):
            latest_repo_version = str(getattr(component_version_obj, 'latest_version', '') or '').strip()
            if latest_repo_version:
                comparisons = [
                    _dpkg_version_gte(latest_repo_version, fix_version)
                    for fix_version in fix_versions
                ]
                known_comparisons = [result for result in comparisons if result is not None]
                if known_comparisons and not any(known_comparisons):
                    fixable = False
                    fix_status = 'not_in_repo'
    elif normalized_fix_state == 'wont-fix':
        fix_status = 'wont_fix'
    elif normalized_fix_state == 'not-fixed':
        fix_status = 'not_fixed'
    elif normalized_fix_state == 'fixed':
        fix_status = 'version_unknown'

    fix_display = ', '.join(fix_versions) if fix_versions else (raw_fix_state or '')
    if fix_status == 'not_in_repo' and fix_display:
        fix_display = f"{fix_display} (not yet in repo)"

    return {
        'fixable': fixable,
        'fix': fix_display,
        'fix_state': raw_fix_state,
        'fix_status': fix_status,
        'fix_versions': fix_versions,
    }


def _run_bulk_component_latest_version_update(
    queryset,
    task_name: str,
    skip_recent_days: int,
    batch_size: int = 50,
) -> dict:
    from datetime import timedelta
    from django.utils import timezone

    logger.info(f"Starting latest versions update for {task_name}")
    start_time = time.time()

    try:
        now = timezone.now()
        cutoff_date = now - timedelta(days=skip_recent_days)

        component_versions = queryset.filter(
            purl__isnull=False,
        ).exclude(
            latest_version_updated_at__gte=cutoff_date,
        ).select_related('component')

        total_count = component_versions.count()
        logger.info(
            f"Found {total_count} component versions to process for {task_name} "
            f"(skipping components updated within last {skip_recent_days} days)"
        )

        updated_count = 0
        skipped_count = 0
        error_count = 0

        for i in range(0, total_count, batch_size):
            batch = component_versions[i:i + batch_size]
            batch_start_time = time.time()
            current_batch = i // batch_size + 1
            total_batches = (total_count + batch_size - 1) // batch_size if total_count else 0

            logger.info(f"Processing batch {current_batch}/{total_batches} ({len(batch)} components)")

            for component_version in batch:
                try:
                    if not component_version.purl:
                        skipped_count += 1
                        continue

                    if (
                        component_version.latest_version_updated_at and
                        (now - component_version.latest_version_updated_at).days < skip_recent_days
                    ):
                        skipped_count += 1
                        continue

                    if DEBUG_LOGGING:
                        logger.debug(
                            f"Processing component version "
                            f"{component_version.component.name}:{component_version.version}"
                        )
                        logger.debug(f"Processing PURL: {component_version.purl}")

                    latest_version = _lookup_latest_version_for_purl(component_version.purl)

                    if latest_version:
                        component_version.latest_version = latest_version
                        component_version.latest_version_updated_at = now
                        component_version.save(update_fields=['latest_version', 'latest_version_updated_at'])
                        updated_count += 1
                        logger.info(
                            f"Updated latest version for "
                            f"{component_version.component.name}:{component_version.version} "
                            f"to {latest_version}"
                        )
                    else:
                        skipped_count += 1

                except Exception as e:
                    error_count += 1
                    logger.error(
                        f"Error processing component version "
                        f"{component_version.component.name}:{component_version.version}: {str(e)}"
                    )
                    continue

            batch_time = time.time() - batch_start_time
            logger.info(f"Completed batch {current_batch}/{total_batches} in {batch_time:.2f}s")

        total_time = time.time() - start_time
        logger.info(f"{task_name} completed in {total_time:.2f} seconds")
        logger.info(f"Updated: {updated_count}, Skipped: {skipped_count}, Errors: {error_count}")

        return {
            "status": "success",
            "task_name": task_name,
            "total_processed": total_count,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "error_count": error_count,
            "processing_time": total_time,
        }

    except Exception as e:
        logger.error(f"Error updating latest versions for {task_name}: {str(e)}")
        return {
            "status": "error",
            "task_name": task_name,
            "error": str(e),
        }


def _is_supported_vulnerability_enrichment_target(vulnerability_id: str, vulnerability_type: str | None = None) -> bool:
    normalized_type = str(vulnerability_type or '').upper()
    normalized_id = str(vulnerability_id or '').upper()
    if normalized_type in {'CVE', 'GHSA'}:
        return True
    return normalized_id.startswith('CVE-') or normalized_id.startswith('GHSA-')


def _dedupe_preserve_order(values):
    seen = set()
    deduped = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _chunked(values, chunk_size):
    for index in range(0, len(values), chunk_size):
        yield values[index:index + chunk_size]


def _build_vulnerability_data_sources(cve_details, exploit_info):
    data_sources = []
    if cve_details:
        if cve_details.get('epss_data_source'):
            data_sources.append(cve_details['epss_data_source'])
        explicit_detail_sources = cve_details.get('_detail_sources')
        if explicit_detail_sources:
            data_sources.extend(explicit_detail_sources)
        cve_detail_fields = {
            'cve_details_score',
            'cve_details_severity',
            'cve_details_published_date',
            'cve_details_updated_date',
            'cve_details_summary',
            'cve_details_references',
        }
        if (
            any(cve_details.get(field) is not None for field in cve_detail_fields)
            and not explicit_detail_sources
        ):
            data_sources.append('CVE-CIRCL')
    if exploit_info:
        if exploit_info.get('cisa_kev_known_exploited'):
            data_sources.append('CISA-KEV')
        if exploit_info.get('exploit_db_available'):
            data_sources.append('Exploit-DB')
        if any('nvd.nist.gov' in link for link in exploit_info.get('exploit_links', [])):
            data_sources.append('NVD')
    return _dedupe_preserve_order(data_sources)


def _normalize_image_digest(digest):
    if not digest:
        return None

    normalized = str(digest).strip()
    if not normalized:
        return None

    if '@' in normalized:
        normalized = normalized.split('@', 1)[-1].strip()
    if not normalized:
        return None

    if ':' not in normalized:
        normalized = f"sha256:{normalized}"

    return normalized


_REGISTRY_LOOKUP_CACHE_TTL = 300


def _registry_host(registry):
    if not registry or not getattr(registry, 'api_url', None):
        return None
    raw = str(registry.api_url).strip()
    if not raw:
        return None
    if '://' not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    return (parsed.netloc or parsed.path or '').strip().lower() or None


def _parse_image_reference(image_ref):
    reference = (image_ref or '').strip()
    if not reference:
        return None

    digest = None
    if '@' in reference:
        reference, raw_digest = reference.split('@', 1)
        digest = _normalize_image_digest(raw_digest)

    host = None
    repository = reference
    if '/' in reference:
        first_segment, remainder = reference.split('/', 1)
        if '.' in first_segment or ':' in first_segment or first_segment == 'localhost':
            host = first_segment.lower()
            repository = remainder

    tag = None
    last_slash = repository.rfind('/')
    last_colon = repository.rfind(':')
    if last_colon > last_slash:
        tag = repository[last_colon + 1:].strip() or None
        repository = repository[:last_colon]

    repository = repository.strip('/')
    if not repository:
        return None

    return {
        "host": host,
        "repository": repository,
        "tag": tag,
        "digest": digest,
    }


def _compose_image_reference(host, repository, tag=None, digest=None):
    base = f"{host}/{repository}".strip('/')
    if digest:
        normalized = _normalize_image_digest(digest)
        return f"{base}@{normalized}" if normalized else base
    if tag:
        return f"{base}:{tag}"
    return base


def _get_cached_registry_repository_names(registry):
    from django.core.cache import cache
    from .utils.registry import get_repositories

    if not registry:
        return set()

    cache_key = f"registry-repositories:{registry.pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        return set(cached)

    names = set()
    last_repo = None
    while True:
        repositories, last_repo = get_repositories(registry, page_size=200, last_repo=last_repo)
        for repository_info in repositories:
            if repository_info and repository_info[0]:
                names.add(repository_info[0])
        if not last_repo:
            break

    cache.set(cache_key, sorted(names), _REGISTRY_LOOKUP_CACHE_TTL)
    return names


def _get_cached_registry_tags(registry, repository_name, limit=200):
    from django.core.cache import cache
    from .utils.registry import get_tags

    if not registry or not repository_name:
        return []

    cache_key = f"registry-tags:{registry.pk}:{repository_name}:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return list(cached)

    tags = list(get_tags(registry, repository_name, limit=limit))
    cache.set(cache_key, tags, _REGISTRY_LOOKUP_CACHE_TTL)
    return tags


def _derive_same_registry_repo_candidates(repository, parsed_ref):
    candidates = []
    repo_path = parsed_ref.get("repository")
    if repo_path:
        candidates.append(repo_path)

    if repo_path and repo_path.startswith("helm/"):
        candidates.append(repo_path.removeprefix("helm/"))

    repository_name = (getattr(repository, 'name', '') or '').strip('/')
    base_repo = repository_name.removeprefix("helm/") if repository_name.startswith("helm/") else repository_name
    base_leaf = base_repo.split('/')[-1] if base_repo else None
    repo_leaf = repo_path.split('/')[-1] if repo_path else None

    if base_repo and repo_leaf:
        candidates.extend([
            f"{base_repo}/{repo_leaf}",
            f"{base_repo}-{repo_leaf}",
        ])

    if base_leaf and repo_leaf and base_leaf != base_repo:
        candidates.extend([
            f"{base_leaf}/{repo_leaf}",
            f"{base_leaf}-{repo_leaf}",
        ])

    if repo_path and repo_leaf and '/' not in repo_path and base_repo:
        candidates.append(f"{base_repo}/{repo_path}")

    return _dedupe_preserve_order(candidates)


def _resolve_repository_tag_image_digest(tag, image_ref, registry):
    from .utils.registry import get_image_digest

    stored_digest = getattr(tag, 'digest', None)
    resolved_digest = _normalize_image_digest(stored_digest)

    if registry:
        try:
            registry_digest = _normalize_image_digest(get_image_digest(registry, image_ref))
        except Exception as exc:
            logger.warning(
                "Failed to resolve image digest for %s from registry %s: %s",
                image_ref,
                getattr(registry, 'name', 'unknown'),
                exc,
            )
            registry_digest = None
        if registry_digest:
            resolved_digest = registry_digest

    if tag is not None and resolved_digest and stored_digest != resolved_digest:
        tag.digest = resolved_digest
        tag.save(update_fields=['digest', 'updated_at'])

    return resolved_digest


def _registry_host(value):
    raw_value = str(value or '').strip()
    if not raw_value:
        return None

    if raw_value.startswith(('http://', 'https://')):
        raw_value = urlparse(raw_value).netloc

    return raw_value.split('/', 1)[0] if raw_value else None


def _parse_image_reference(image_ref):
    raw_reference = str(image_ref or '').strip()
    if not raw_reference:
        return None

    digest = None
    tag = None
    path = raw_reference

    if '@' in path:
        path, digest = path.rsplit('@', 1)
        digest = _normalize_image_digest(digest)

    last_segment = path.rsplit('/', 1)[-1]
    if ':' in last_segment:
        path, tag = path.rsplit(':', 1)

    segments = [segment for segment in path.split('/') if segment]
    if not segments:
        return None

    host = None
    if len(segments) > 1 and (
        '.' in segments[0] or ':' in segments[0] or segments[0] == 'localhost'
    ):
        host = segments[0]
        repository = '/'.join(segments[1:])
    else:
        repository = '/'.join(segments)

    return {
        'host': host,
        'repository': repository,
        'tag': tag,
        'digest': digest,
    }


def _compose_image_reference(host, repository, tag=None, digest=None):
    if not repository:
        return None

    base = f"{host}/{repository}" if host else repository
    normalized_digest = _normalize_image_digest(digest)
    if normalized_digest:
        return f"{base}@{normalized_digest}"
    if tag:
        return f"{base}:{tag}"
    return base


def _repository_path_from_url(repository_url):
    parsed = _parse_image_reference(repository_url)
    if parsed:
        return parsed['repository']

    raw_url = str(repository_url or '').strip()
    if not raw_url:
        return None
    if raw_url.startswith(('http://', 'https://')):
        parsed_url = urlparse(raw_url)
        return parsed_url.path.lstrip('/') or None
    return raw_url.split('/', 1)[1] if '/' in raw_url else None


def _derive_same_registry_image_candidates(repository, registry, image_ref):
    parsed_ref = _parse_image_reference(image_ref)
    if not parsed_ref or not parsed_ref.get('repository'):
        return [image_ref]

    registry_host = (
        _registry_host(getattr(registry, 'api_url', None))
        or parsed_ref.get('host')
        or _registry_host(repository.url)
    )
    repo_path = parsed_ref['repository']

    candidate_paths = [repo_path]
    if repo_path.startswith('helm/'):
        candidate_paths.append(repo_path.removeprefix('helm/'))

    for chart_repo_path in filter(None, [repository.name, _repository_path_from_url(repository.url)]):
        if repo_path == chart_repo_path and chart_repo_path.startswith('helm/'):
            candidate_paths.append(chart_repo_path.removeprefix('helm/'))
        if repo_path.startswith(f"{chart_repo_path}/") and chart_repo_path.startswith('helm/'):
            candidate_paths.append(
                f"{chart_repo_path.removeprefix('helm/')}{repo_path[len(chart_repo_path):]}"
            )

    candidates = []
    for candidate_path in _dedupe_preserve_order(candidate_paths):
        candidate_ref = _compose_image_reference(
            registry_host or parsed_ref.get('host'),
            candidate_path,
            tag=parsed_ref.get('tag'),
            digest=parsed_ref.get('digest'),
        )
        if candidate_ref:
            candidates.append(candidate_ref)

    return _dedupe_preserve_order(candidates or [image_ref])


def _resolve_helm_image_location(repository, repo_tag, registry, image_ref):
    from .models import ContainerRegistry, Image
    from .utils.registry import (
        build_fallback_image_ref,
        build_fallback_image_ref_from_url,
        get_image_digest,
        to_docker_pull_ref,
    )

    chart_ref = _repository_tag_image_ref(repository, repo_tag, registry)
    existing_image = (
        Image.objects.filter(name=image_ref)
        .order_by('-updated_at')
        .first()
    )
    if existing_image and (
        _has_completed_image_payload(existing_image)
        or (
            existing_image.digest
            and existing_image.artifact_reference
            and existing_image.artifact_reference != chart_ref
        )
    ):
        return (
            existing_image.name,
            _normalize_image_digest(existing_image.digest),
            existing_image.artifact_reference or existing_image.name,
            None,
        )

    if registry:
        try:
            original_digest = _normalize_image_digest(
                get_image_digest(registry, image_ref)
            )
        except Exception as exc:
            logger.warning(
                "Failed to resolve Helm child image digest for original ref %s: %s",
                image_ref,
                exc,
            )
            original_digest = None
        if original_digest:
            resolved_pull_ref = (
                to_docker_pull_ref(image_ref)
                if "/artifactory/" in image_ref
                else image_ref
            )
            return (
                resolved_pull_ref,
                original_digest,
                resolved_pull_ref,
                None,
            )

    candidate_refs = _derive_same_registry_image_candidates(repository, registry, image_ref)

    for candidate_ref in candidate_refs:
        try:
            candidate_digest = _normalize_image_digest(get_image_digest(registry, candidate_ref))
        except Exception as exc:
            logger.warning(
                "Failed to resolve Helm child image digest for %s via %s: %s",
                candidate_ref,
                getattr(registry, 'name', 'unknown'),
                exc,
            )
            candidate_digest = None

        if candidate_digest:
            resolved_pull_ref = to_docker_pull_ref(candidate_ref)
            return (
                resolved_pull_ref,
                candidate_digest,
                resolved_pull_ref,
                None,
            )

    fallback_repositories = list(
        repository.image_fallback_repositories.filter(
            repository_type='docker',
            container_registry__isnull=False,
        ).select_related('container_registry')
    )
    for candidate_ref in candidate_refs:
        for fallback_repository in fallback_repositories:
            if not fallback_repository.container_registry:
                continue
            fallback_ref = build_fallback_image_ref(fallback_repository, candidate_ref)
            if not fallback_ref:
                continue
            fallback_digest = _normalize_image_digest(
                get_image_digest(fallback_repository.container_registry, fallback_ref)
            )
            if fallback_digest:
                resolved_pull_ref = to_docker_pull_ref(fallback_ref)
                return (
                    resolved_pull_ref,
                    fallback_digest,
                    resolved_pull_ref,
                    None,
                )

    for candidate_ref in candidate_refs:
        for fallback_entry in (getattr(registry, 'image_fallback_repositories', None) or []):
            fallback_url = fallback_entry.get('url') if isinstance(fallback_entry, dict) else None
            auth_registry_uuid = fallback_entry.get('registry_uuid') if isinstance(fallback_entry, dict) else None
            if not fallback_url or not auth_registry_uuid:
                continue
            auth_registry = ContainerRegistry.objects.filter(uuid=auth_registry_uuid).first()
            if not auth_registry:
                continue
            fallback_ref = build_fallback_image_ref_from_url(fallback_url, candidate_ref)
            if not fallback_ref:
                continue
            fallback_digest = _normalize_image_digest(get_image_digest(auth_registry, fallback_ref))
            if fallback_digest:
                resolved_pull_ref = to_docker_pull_ref(fallback_ref)
                return (
                    resolved_pull_ref,
                    fallback_digest,
                    resolved_pull_ref,
                    None,
                )

    return (
        None,
        None,
        None,
        (
            f"Could not resolve Helm child image {image_ref} in registry {getattr(registry, 'name', 'unknown')}. "
            f"Tried: {', '.join(candidate_refs)}"
        ),
    )


def _select_sbom_pull_reference(image, art_type='docker'):
    chart_refs = set()
    if art_type == 'helm':
        for linked_tag in image.repository_tags.all():
            repository = getattr(linked_tag, 'repository', None)
            if not repository or repository.repository_type != 'helm':
                continue
            chart_refs.add(
                _repository_tag_image_ref(
                    repository,
                    linked_tag,
                    getattr(repository, 'container_registry', None),
                )
            )

    candidates = []
    artifact_ref = (image.artifact_reference or '').strip()
    image_name = (image.name or '').strip()

    if art_type == 'helm':
        if artifact_ref and artifact_ref not in chart_refs and not artifact_ref.startswith(("http://", "https://")):
            candidates.append(artifact_ref)
        if image_name:
            candidates.append(image_name)
    else:
        if artifact_ref and not artifact_ref.startswith(("http://", "https://")):
            candidates.append(artifact_ref)
        if image_name:
            candidates.append(image_name)

    for candidate in _dedupe_preserve_order(candidates):
        if is_safe_image_ref(candidate):
            return candidate

    fallback_ref = image_name or artifact_ref
    return fallback_ref


def _reconcile_helm_tag_images(repo_tag, keep_image_ids):
    keep_ids = set(keep_image_ids or [])
    repository = repo_tag.repository
    registry = repository.container_registry
    chart_ref = _repository_tag_image_ref(repository, repo_tag, registry)
    current_images = list(repo_tag.images.all())

    if keep_ids:
        repo_tag.images.set(list(keep_ids))
    else:
        repo_tag.images.clear()

    removed_count = 0
    deleted_count = 0

    for image in current_images:
        if image.pk in keep_ids:
            continue
        if image.artifact_reference != chart_ref:
            continue

        removed_count += 1
        if (
            not image.repository_tags.exclude(pk=repo_tag.pk).exists()
            and image.sbom_data is None
            and image.grype_data is None
            and not image.component_versions.exists()
            and not image.component_locations.exists()
        ):
            image.delete()
            deleted_count += 1

    return {
        'removed_count': removed_count,
        'deleted_count': deleted_count,
    }


def _has_completed_image_scan(image):
    return (
        image.scan_status == 'success' and
        image.sbom_data is not None and
        image.grype_data is not None
    )


def _has_completed_image_payload(image):
    return image.sbom_data is not None and image.grype_data is not None


def _image_identity_lock_key(name, digest):
    normalized_digest = _normalize_image_digest(digest) or '<no-digest>'
    lock_bytes = hashlib.blake2b(
        f"{name}|{normalized_digest}".encode('utf-8'),
        digest_size=8,
    ).digest()
    return int.from_bytes(lock_bytes, byteorder='big', signed=True)


def _acquire_image_identity_lock(name, digest):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s)",
            [_image_identity_lock_key(name, digest)],
        )


def _equivalent_images_queryset(name, digest):
    from .models import Image

    queryset = Image.objects.filter(name=name)
    normalized_digest = _normalize_image_digest(digest)
    if normalized_digest:
        return queryset.filter(digest=normalized_digest)
    return queryset.filter(Q(digest__isnull=True) | Q(digest=''))


def _pick_preferred_image(images):
    if not images:
        return None

    status_rank = {
        'success': 0,
        'in_process': 1,
        'pending': 2,
        'error': 3,
        'none': 4,
    }

    return min(
        images,
        key=lambda image: (
            status_rank.get(image.scan_status, 99),
            0 if image.grype_data is not None else 1,
            0 if image.sbom_data is not None else 1,
            0 if image.digest else 1,
            image.created_at,
            str(image.pk),
        ),
    )


def _get_or_create_canonical_image(name, digest=None, artifact_reference=None):
    from .models import Image

    normalized_digest = _normalize_image_digest(digest)

    with transaction.atomic():
        _acquire_image_identity_lock(name, normalized_digest)
        matching_images = list(
            _equivalent_images_queryset(name, normalized_digest).select_for_update()
        )
        image = _pick_preferred_image(matching_images)
        created = False

        if image is None and normalized_digest:
            digestless_images = list(
                _equivalent_images_queryset(name, None).select_for_update()
            )
            digestless_image = _pick_preferred_image(digestless_images)
            conflicting_digest_exists = Image.objects.filter(name=name).exclude(
                Q(digest=normalized_digest) | Q(digest__isnull=True) | Q(digest='')
            ).exists()
            if digestless_image and not conflicting_digest_exists:
                image = digestless_image

        if image is None:
            image = Image.objects.create(
                name=name,
                digest=normalized_digest,
                artifact_reference=artifact_reference,
            )
            created = True
        else:
            updated_fields = []
            if normalized_digest and image.digest != normalized_digest:
                image.digest = normalized_digest
                updated_fields.append('digest')
            if artifact_reference and artifact_reference != image.artifact_reference:
                if not image.artifact_reference or not artifact_reference.startswith(("http://", "https://")):
                    image.artifact_reference = artifact_reference
                    updated_fields.append('artifact_reference')
            if updated_fields:
                image.save(update_fields=updated_fields + ['updated_at'])

        return image, created


def _propagate_image_completion_to_equivalent_images(image):
    from .models import ComponentLocation, ImageComponentVersionContext

    duplicate_images = list(
        _equivalent_images_queryset(image.name, image.digest)
        .exclude(pk=image.pk)
        .prefetch_related('repository_tags', 'component_versions', 'component_locations', 'component_contexts')
    )
    if not duplicate_images:
        return list(image.repository_tags.values_list('pk', flat=True))

    source_component_versions = list(image.component_versions.values_list('pk', flat=True))
    source_locations = list(
        image.component_locations.select_related('component_version').all()
    )
    source_contexts = list(
        image.component_contexts.select_related('component_version').all()
    )
    related_tag_ids = set(image.repository_tags.values_list('pk', flat=True))

    for duplicate in duplicate_images:
        related_tag_ids.update(duplicate.repository_tags.values_list('pk', flat=True))

        if source_component_versions:
            duplicate.component_versions.add(*source_component_versions)
        for location in source_locations:
            ComponentLocation.objects.get_or_create(
                component_version=location.component_version,
                image=duplicate,
                path=location.path,
                defaults={
                    'layer_id': location.layer_id,
                    'access_path': location.access_path,
                    'evidence_type': location.evidence_type,
                    'annotations': location.annotations,
                },
            )
        for context in source_contexts:
            _merge_component_context_into_image(context, duplicate)

        update_fields = []
        if duplicate.digest != image.digest:
            duplicate.digest = image.digest
            update_fields.append('digest')
        if duplicate.sbom_data != image.sbom_data:
            duplicate.sbom_data = image.sbom_data
            update_fields.append('sbom_data')
        if duplicate.grype_data != image.grype_data:
            duplicate.grype_data = image.grype_data
            update_fields.append('grype_data')
        if duplicate.scan_status != 'success':
            duplicate.scan_status = 'success'
            update_fields.append('scan_status')
        update_fields.extend(_copy_image_lineage_fields(image, duplicate))
        update_fields.extend(_copy_image_os_eol_fields(image, duplicate))
        if update_fields:
            duplicate.save(update_fields=sorted(set(update_fields)) + ['updated_at'])

    return list(related_tag_ids)


def _merge_component_location_into_image(source_location, target_image):
    from .models import ComponentLocation

    target_location, created = ComponentLocation.objects.get_or_create(
        component_version=source_location.component_version,
        image=target_image,
        path=source_location.path,
        defaults={
            'layer_id': source_location.layer_id,
            'access_path': source_location.access_path,
            'evidence_type': source_location.evidence_type,
            'annotations': source_location.annotations,
        },
    )
    if created:
        return True

    updated_fields = []
    for field_name in ('layer_id', 'access_path', 'evidence_type', 'annotations'):
        current_value = getattr(target_location, field_name)
        incoming_value = getattr(source_location, field_name)
        if not current_value and incoming_value:
            setattr(target_location, field_name, incoming_value)
            updated_fields.append(field_name)
    if updated_fields:
        target_location.save(update_fields=updated_fields)

    return False


def _merge_component_context_into_image(source_context, target_image):
    from .models import ImageComponentVersionContext

    target_context, created = ImageComponentVersionContext.objects.get_or_create(
        component_version=source_context.component_version,
        image=target_image,
        defaults={
            'cataloger': source_context.cataloger,
            'metadata_type': source_context.metadata_type,
            'dependency_scope': source_context.dependency_scope,
            'dependency_depth': source_context.dependency_depth,
            'immediate_parent_name': source_context.immediate_parent_name,
            'immediate_parent_version': source_context.immediate_parent_version,
            'direct_introducer_name': source_context.direct_introducer_name,
            'direct_introducer_version': source_context.direct_introducer_version,
            'package_scope': source_context.package_scope,
            'package_arch': source_context.package_arch,
            'package_distro': source_context.package_distro,
            'package_repo': source_context.package_repo,
            'package_channel': source_context.package_channel,
            'source_package': source_context.source_package,
            'source_package_version': source_context.source_package_version,
        },
    )
    if created:
        return True

    updated_fields = []
    for field_name in (
        'cataloger',
        'metadata_type',
        'immediate_parent_name',
        'immediate_parent_version',
        'direct_introducer_name',
        'direct_introducer_version',
        'package_arch',
        'package_distro',
        'package_repo',
        'package_channel',
        'source_package',
        'source_package_version',
    ):
        current_value = getattr(target_context, field_name)
        incoming_value = getattr(source_context, field_name)
        if not current_value and incoming_value:
            setattr(target_context, field_name, incoming_value)
            updated_fields.append(field_name)

    current_depth = target_context.dependency_depth
    incoming_depth = source_context.dependency_depth
    if current_depth is None or (incoming_depth is not None and incoming_depth < current_depth):
        target_context.dependency_depth = incoming_depth
        target_context.dependency_scope = source_context.dependency_scope
        target_context.immediate_parent_name = source_context.immediate_parent_name
        target_context.immediate_parent_version = source_context.immediate_parent_version
        target_context.direct_introducer_name = source_context.direct_introducer_name
        target_context.direct_introducer_version = source_context.direct_introducer_version
        updated_fields.extend([
            'dependency_depth',
            'dependency_scope',
            'immediate_parent_name',
            'immediate_parent_version',
            'direct_introducer_name',
            'direct_introducer_version',
        ])
    elif target_context.dependency_scope == 'unknown' and source_context.dependency_scope != 'unknown':
        target_context.dependency_scope = source_context.dependency_scope
        updated_fields.append('dependency_scope')

    scope_priority = {
        'unknown': 0,
        'optional': 1,
        'test': 2,
        'build': 3,
        'development': 4,
        'runtime': 5,
    }
    if scope_priority.get(source_context.package_scope or 'unknown', 0) > scope_priority.get(target_context.package_scope or 'unknown', 0):
        target_context.package_scope = source_context.package_scope
        updated_fields.append('package_scope')

    if updated_fields:
        target_context.save(update_fields=sorted(set(updated_fields)) + ['updated_at'])

    return False


def _merge_duplicate_image_group(images, normalized_digest):
    if len(images) <= 1:
        return None

    status_rank = {
        'success': 0,
        'in_process': 1,
        'pending': 2,
        'error': 3,
        'none': 4,
    }

    primary = _pick_preferred_image(images)
    duplicate_images = [image for image in images if image.pk != primary.pk]
    if not duplicate_images:
        return None

    related_tag_ids = set(primary.repository_tags.values_list('pk', flat=True))
    primary_tag_ids = set(related_tag_ids)
    primary_component_version_ids = set(primary.component_versions.values_list('pk', flat=True))

    merged_tag_links = 0
    merged_component_links = 0
    merged_locations = 0
    merged_contexts = 0
    normalized_images = 0
    deleted_images = 0

    update_fields = []
    if primary.digest != normalized_digest:
        primary.digest = normalized_digest
        update_fields.append('digest')
        normalized_images += 1

    for duplicate in duplicate_images:
        duplicate_tag_ids = set(duplicate.repository_tags.values_list('pk', flat=True))
        new_tag_ids = list(duplicate_tag_ids - primary_tag_ids)
        if new_tag_ids:
            primary.repository_tags.add(*new_tag_ids)
            merged_tag_links += len(new_tag_ids)
            primary_tag_ids.update(new_tag_ids)
        related_tag_ids.update(duplicate_tag_ids)

        duplicate_component_version_ids = set(
            duplicate.component_versions.values_list('pk', flat=True)
        )
        new_component_version_ids = list(
            duplicate_component_version_ids - primary_component_version_ids
        )
        if new_component_version_ids:
            primary.component_versions.add(*new_component_version_ids)
            merged_component_links += len(new_component_version_ids)
            primary_component_version_ids.update(new_component_version_ids)

        for location in duplicate.component_locations.select_related('component_version').all():
            if _merge_component_location_into_image(location, primary):
                merged_locations += 1
        for context in duplicate.component_contexts.select_related('component_version').all():
            if _merge_component_context_into_image(context, primary):
                merged_contexts += 1

        if not primary.artifact_reference and duplicate.artifact_reference:
            primary.artifact_reference = duplicate.artifact_reference
            update_fields.append('artifact_reference')
        if primary.sbom_data is None and duplicate.sbom_data is not None:
            primary.sbom_data = duplicate.sbom_data
            update_fields.append('sbom_data')
        if primary.grype_data is None and duplicate.grype_data is not None:
            primary.grype_data = duplicate.grype_data
            update_fields.append('grype_data')
        if duplicate.digest != normalized_digest:
            duplicate.digest = normalized_digest
            duplicate.save(update_fields=['digest', 'updated_at'])
            normalized_images += 1
        if status_rank.get(duplicate.scan_status, 99) < status_rank.get(primary.scan_status, 99):
            primary.scan_status = duplicate.scan_status
            update_fields.append('scan_status')
        update_fields.extend(_copy_image_lineage_fields(duplicate, primary))
        update_fields.extend(_copy_image_os_eol_fields(duplicate, primary))

    update_fields.extend(_apply_image_lineage_fields(primary))
    update_fields.extend(_apply_image_os_eol_fields(primary))
    if update_fields:
        primary.save(update_fields=sorted(set(update_fields)) + ['updated_at'])

    for duplicate in duplicate_images:
        duplicate.delete()
        deleted_images += 1

    if related_tag_ids:
        _sync_repository_tag_processing_statuses(list(related_tag_ids))

    return {
        'primary_image_uuid': str(primary.uuid),
        'duplicate_groups_merged': 1,
        'duplicate_images_deleted': deleted_images,
        'repository_tag_links_merged': merged_tag_links,
        'component_version_links_merged': merged_component_links,
        'component_locations_merged': merged_locations,
        'component_contexts_merged': merged_contexts,
        'images_normalized': normalized_images,
    }


def _capture_repository_tag_scan_snapshot(tag_id):
    from .models import RepositoryTag, RepositoryTagScanSnapshot
    from .utils.analytics import (
        build_repository_tag_scan_summary,
        compare_vulnerability_states,
    )

    tag = RepositoryTag.objects.get(pk=tag_id)
    current_summary = build_repository_tag_scan_summary(tag)
    previous_snapshot = tag.scan_snapshots.order_by('-created_at').first()
    previous_state = previous_snapshot.vulnerability_state if previous_snapshot else {}
    delta = compare_vulnerability_states(previous_state, current_summary['vulnerability_state'])
    risk_score_delta = current_summary['weighted_risk_score'] - (
        previous_snapshot.weighted_risk_score if previous_snapshot else 0.0
    )

    return RepositoryTagScanSnapshot.objects.create(
        repository_tag=tag,
        processing_status=current_summary['processing_status'],
        total_images=current_summary['total_images'],
        successful_images=current_summary['successful_images'],
        unique_vulnerabilities_count=current_summary['unique_vulnerabilities_count'],
        weighted_risk_score=current_summary['weighted_risk_score'],
        previous_unique_vulnerabilities_count=delta['previous_unique_vulnerabilities_count'],
        new_vulnerabilities_count=delta['new_vulnerabilities_count'],
        fixed_vulnerabilities_count=delta['fixed_vulnerabilities_count'],
        severity_increased_count=delta['severity_increased_count'],
        new_kev_relevant_count=delta['new_kev_relevant_count'],
        risk_score_delta=round(risk_score_delta, 2),
        has_changes=delta['has_changes'] or round(risk_score_delta, 2) != 0,
        fixability_breakdown=current_summary['fixability_breakdown'],
        vulnerability_state=current_summary['vulnerability_state'],
        delta_summary=delta['delta_summary'],
    )


def _sync_repository_tag_processing_statuses(tag_ids):
    from .models import RepositoryTag

    if not tag_ids:
        return {}

    status_rows = RepositoryTag.objects.filter(
        pk__in=tag_ids
    ).annotate(
        total_images_count=Count('images', distinct=True),
        pending_images_count=Count('images', filter=Q(images__scan_status='pending'), distinct=True),
        in_process_images_count=Count('images', filter=Q(images__scan_status='in_process'), distinct=True),
        error_images_count=Count('images', filter=Q(images__scan_status='error'), distinct=True),
        success_images_count=Count('images', filter=Q(images__scan_status='success'), distinct=True),
    ).only('uuid', 'processing_status')

    now = timezone.now()
    updated_tags = []
    resolved_statuses = {}
    snapshot_tag_ids = []

    for tag in status_rows:
        new_status = resolve_repository_tag_processing_status(
            tag.processing_status,
            tag.total_images_count or 0,
            tag.pending_images_count or 0,
            tag.in_process_images_count or 0,
            tag.error_images_count or 0,
            tag.success_images_count or 0,
        )
        resolved_statuses[str(tag.pk)] = new_status
        if tag.processing_status != new_status:
            if new_status == 'success':
                snapshot_tag_ids.append(tag.pk)
            tag.processing_status = new_status
            tag.updated_at = now
            updated_tags.append(tag)

    if updated_tags:
        RepositoryTag.objects.bulk_update(updated_tags, ['processing_status', 'updated_at'])

    for tag_id in snapshot_tag_ids:
        try:
            _capture_repository_tag_scan_snapshot(tag_id)
        except Exception as exc:
            logger.error("Failed to capture repository tag snapshot for %s: %s", tag_id, exc)

    return resolved_statuses

@celery_app.task(
    bind=True,
    max_retries=1,
    name="Generate SBOM and Create Components",
    soft_time_limit=GENERATE_SBOM_SOFT_TIME_LIMIT,
    time_limit=GENERATE_SBOM_TIME_LIMIT,
)
def generate_sbom_and_create_components(self, image_uuid: str, art_type: str="docker", scan_run_uuid: str | None = None):
    """
    Generate SBOM data for an image using Syft.
    This task can be retried up to 1 times if it fails.
    """
    from .models import Image, ContainerRegistry
    import subprocess
    import json
    import tempfile
    import os
    from .utils.registry import get_bearer_token, get_image_digest

    logger.info(f"Starting SBOM generation for image {image_uuid}")
    
    try:
        # Get image with prefetched related data
        image = Image.objects.select_related().prefetch_related(
            'repository_tags__repository__container_registry',
            'component_versions__component',
            'component_versions__vulnerabilities'
        ).get(uuid=image_uuid)
        
        # A durable lease makes retries and duplicate Celery deliveries idempotent.
        from .services.scans import claim_scan, queue_scan
        if scan_run_uuid:
            scan_run, claimed = claim_scan(scan_run_uuid)
        else:
            scan_run, created = queue_scan(image)
            claimed = created and claim_scan(scan_run.uuid)[1]
        if not claimed:
            logger.warning(f"Image {image_uuid} is already being scanned")
            return {
                "status": "skipped", 
                "task_name": "Generate SBOM and Create Components",
                "image_uuid": str(image_uuid),
                "reason": "already in process",
                "message": f"Image {image_uuid} is already being processed",
                "current_status": image.scan_status,
                "timestamp": timezone.now().isoformat()
            }

        # Update status to in_process
        image.scan_status = 'in_process'
        image.save()
        
        image_ref = _select_sbom_pull_reference(image, art_type=art_type)
        if not is_safe_image_ref(image_ref):
            logger.error(f"Unsafe image_ref: {image_ref}")
            image.scan_status = 'error'
            image.save()
            raise ValueError("Unsafe image reference")

        # Get registry token if available
        registry = None
        token = None
        if image.repository_tags.exists():
            registry = image.repository_tags.first().repository.container_registry
            if registry:
                token = get_bearer_token(registry)

        # Try to pull image
        try:
            logger.info(f"Pulling image {image_ref}")
            subprocess.run(["docker", "pull", image_ref], capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            if token and registry:
                # Try with registry authentication
                registry_host = image_ref.split('/')[0]
                logger.info(f"First pull failed, trying with registry authentication for {registry_host}")
                # Artifactory uses username/password; ACR uses token with special username
                if getattr(registry, 'provider', None) == 'jfrog':
                    login_process = subprocess.Popen(
                        ["docker", "login", registry_host, "-u", registry.login, "--password-stdin"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    _, stderr = login_process.communicate(input=registry.password)
                else:
                    login_process = subprocess.Popen(
                        ["docker", "login", registry_host, "-u", "00000000-0000-0000-0000-000000000000", "--password-stdin"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    _, stderr = login_process.communicate(input=token)
                
                # Check if login failed
                if login_process.returncode != 0:
                    # Check if it's a keychain error (credentials already exist) - this is not critical
                    is_keychain_error = (
                        "already exists in the keychain" in stderr or
                        "error storing credentials" in stderr or
                        "exit status 1" in stderr
                    )
                    
                    if is_keychain_error:
                        # Credentials might already be stored, try to pull anyway
                        logger.warning(f"Keychain error during login (credentials may already exist): {stderr}")
                        logger.info(f"Attempting to pull image {image_ref} anyway (credentials may already be valid)")
                    else:
                        # Real login error
                        logger.error(f"Failed to login to registry {registry_host}: {stderr}")
                        image.scan_status = 'error'
                        image.save()
                        raise
                
                # Retry pull after login (or if keychain error occurred, try anyway)
                logger.info(f"Retrying pull for {image_ref}")
                try:
                    subprocess.run(["docker", "pull", image_ref], capture_output=True, check=True)
                except subprocess.CalledProcessError as pull_error:
                    # If pull still fails after login attempt, it's a real error
                    logger.error(f"Failed to pull image {image_ref} even after login attempt")
                    image.scan_status = 'error'
                    image.save()
                    raise
            else:
                logger.error(f"Failed to pull image {image_ref} and no registry credentials available")
                image.scan_status = 'error'
                image.save()
                raise

        # Get image SHA if not already set
        if not image.digest:
            logger.info(f"Getting SHA for image {image_ref}")
            result = subprocess.run(
                ["docker", "inspect", image_ref],
                capture_output=True,
                check=True,
                text=True
            )
            inspect_data = json.loads(result.stdout)
            if inspect_data and len(inspect_data) > 0:
                repo_digests = inspect_data[0].get('RepoDigests', [])
                if repo_digests:
                    image.digest = repo_digests[0].split('@')[1]
                    image.save()
                    logger.info(f"Set image SHA to {image.digest}")

        # Generate SBOM
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
            temp_file_path = temp_file.name

        try:
            logger.info(f"Running Syft command for image {image_ref}")
            result = subprocess.run(
                ["syft", image_ref, "--output", f"json={temp_file_path}"],
                capture_output=True,
                check=True,
                text=True
            )

            # Read and save SBOM data
            with open(temp_file_path, 'r') as f:
                image.sbom_data = json.load(f)
            # Keep an immutable raw copy through Django storage. Existing JSON fields
            # remain a backwards-compatible read cache during the migration period.
            from .services.scans import store_raw_artifact
            store_raw_artifact(image, 'sbom', image.sbom_data, scan_run=scan_run)
            # Reset stale Grype data so the follow-up vulnerability scan is always rerun.
            image.grype_data = None
            image.scan_status = 'in_process'
            lineage_update_fields = _apply_image_lineage_fields(image)
            eol_update_fields = _apply_image_os_eol_fields(image, grype_data=None)
            image.save(
                update_fields=[
                    'sbom_data',
                    'grype_data',
                    'scan_status',
                    *lineage_update_fields,
                    *eol_update_fields,
                    'updated_at',
                ]
            )
            
            logger.info(f"Successfully generated SBOM for image {image_uuid}")

            # Schedule SBOM parsing
            parse_sbom_and_create_components.delay(str(image_uuid), str(scan_run.uuid))
            logger.info(f"Scheduled SBOM parsing for image {image_uuid}")

            return {
                "status": "success",
                "task_name": "Generate SBOM and Create Components",
                "image_uuid": str(image_uuid),
                "image_name": image_ref,
                "digest": image.digest,
                "art_type": art_type,
                "sbom_generated": True,
                "sbom_parsing_scheduled": True,
                "message": f"SBOM successfully generated for image {image_ref}",
                "next_steps": ["SBOM parsing scheduled", "Grype scan will be triggered after parsing"],
                "timestamp": timezone.now().isoformat()
            }

        finally:
            # Clean up
            try:
                logger.info(f"Removing image {image_ref}")
                subprocess.run(["docker", "rmi", image_ref], capture_output=True)
            except Exception as e:
                logger.warning(f"Failed to remove image {image_ref}: {str(e)}")
            
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    except Image.DoesNotExist:
        logger.error(f"Image with UUID {image_uuid} not found")
        return {
            "status": "error",
            "task_name": "Generate SBOM and Create Components",
            "image_uuid": str(image_uuid),
            "error": f"Image with UUID {image_uuid} not found",
            "error_type": "ImageNotFound",
            "message": "Specified image does not exist in database",
            "suggestion": "Verify image UUID and ensure image exists before processing",
            "timestamp": timezone.now().isoformat()
        }
    except Exception as e:
        if 'scan_run' in locals():
            from .services.scans import finish_scan
            finish_scan(scan_run.uuid, error=str(e))
        error_msg = f"Error generating SBOM for image {image_uuid}: {str(e)}"
        logger.error(error_msg)
        
        # Try to update image status to error
        try:
            image = Image.objects.get(uuid=image_uuid)
            image.scan_status = 'error'
            image.save()
            _sync_repository_tag_processing_statuses(
                list(image.repository_tags.values_list('pk', flat=True))
            )
        except Exception as save_error:
            logger.error(f"Failed to update image status: {str(save_error)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        else:
            logger.error(f"Max retries exceeded for image {image_uuid}")
            return {
                "status": "error",
                "task_name": "Generate SBOM and Create Components",
                "image_uuid": str(image_uuid),
                "error": error_msg,
                "error_type": "MaxRetriesExceeded",
                "max_retries_exceeded": True,
                "message": f"Failed to generate SBOM after {self.max_retries} attempts",
                "suggestion": "Check image accessibility, registry credentials, and system resources",
                "timestamp": timezone.now().isoformat()
            }

@celery_app.task(name="Periodic Repository Scan")
def periodic_repository_scan():
    """
    Queue latest-only scans for all active repositories.
    Intended to be scheduled via django-celery-beat / Django admin.
    """
    from .models import Repository
    logger.info("Starting periodic repository scan for active repositories (latest_only=True)")
    results = []
    active_repositories = Repository.objects.filter(status=True).select_related('container_registry')
    logger.info(f"Found {active_repositories.count()} active repositories")

    for repository in active_repositories:
        try:
            logger.info(f"Queueing latest-tag scan for repository: {repository.name}")

            if not repository.container_registry:
                logger.warning(f"No registry configured for repository {repository.name}, skipping")
                results.append({
                    "repository": repository.name,
                    "repository_uuid": str(repository.uuid),
                    "status": "skipped",
                    "reason": "no_container_registry",
                })
                continue

            if repository.scan_status == 'in_process':
                logger.info(f"Repository {repository.name} is already being scanned, skipping")
                results.append({
                    "repository": repository.name,
                    "repository_uuid": str(repository.uuid),
                    "status": "skipped",
                    "reason": "scan_already_in_process",
                })
                continue

            repository.scan_status = 'pending'
            repository.save()

            async_result = scan_repository_tags.apply_async(
                args=[str(repository.uuid)],
                kwargs={
                    'latest_only': True,
                    'process_existing': True,
                },
            )

            results.append({
                "repository": repository.name,
                "repository_uuid": str(repository.uuid),
                "status": "queued",
                "task_id": async_result.id,
                "latest_only": True,
                "process_existing": True,
            })

        except Exception as e:
            logger.error(f"Error queueing repository {repository.name}: {str(e)}")
            try:
                repository.scan_status = 'error'
                repository.save()
            except Exception:
                pass
            results.append({
                "repository": repository.name,
                "repository_uuid": str(repository.uuid),
                "status": "error",
                "error": str(e),
            })

    total_repositories = len(results)
    queued_repositories = len([r for r in results if r['status'] == 'queued'])
    skipped_repositories = len([r for r in results if r['status'] == 'skipped'])
    failed_repositories = len([r for r in results if r['status'] == 'error'])

    return {
        "status": "queued",
        "task_name": "Periodic Repository Scan",
        "timestamp": timezone.now().isoformat(),
        "summary": {
            "total_repositories_seen": active_repositories.count(),
            "repositories_handled": total_repositories,
            "queued_repositories": queued_repositories,
            "skipped_repositories": skipped_repositories,
            "failed_repositories": failed_repositories,
        },
        "results": results,
        "message": (
            f"Periodic latest-tag scan queued for {queued_repositories} repositories; "
            f"{skipped_repositories} skipped, {failed_repositories} failed to queue"
        ),
    }

@celery_app.task(name="Scan Repository")
def scan_repository(repository_name: str, repository_url: str, scan_option: str):
    """
    Scan a repository for tags and determine its type (Helm or Docker).
    """
    from .models import Repository, RepositoryTag, ContainerRegistry
    from .utils.registry import get_tags, get_manifest, is_helm_chart, get_bearer_token
    from datetime import datetime

    logger.info(f"Starting repository scan for {repository_name}")

    try:
        # Get registry name from repository URL
        registry_name = repository_url.split('/')[0]
        try:
            registry = ContainerRegistry.objects.get(api_url__contains=registry_name)
        except ContainerRegistry.DoesNotExist:
            # Fallback: try ACR then Artifactory so both registries are supported
            try:
                registry = ContainerRegistry.objects.get(provider='acr')
                logger.warning(f"No ContainerRegistry found for {registry_name}, using default ACR")
            except ContainerRegistry.DoesNotExist:
                registry = ContainerRegistry.objects.get(provider='jfrog')
                logger.warning(f"No ContainerRegistry found for {registry_name}, using default Artifactory")

        # Get or create repository
        repository, created = Repository.objects.get_or_create(
            name=repository_name,
            defaults={
                'url': repository_url,
                'repository_type': 'docker',  # Default type
                'container_registry': registry,
                'status': True
            }
        )

        # If repository was not created, update its registry and status
        if not created:
            repository.container_registry = registry
            repository.status = True
            repository.save()

        # Get all tags (ACR or Artifactory)
        all_tags = list(get_tags(registry, repository_name, limit=30))
        if scan_option == 'last':
            tags_to_scan = all_tags[-1:] if all_tags else []
        elif scan_option == 'last10':
            tags_to_scan = all_tags[-10:] if all_tags else []
        else:  # 'all'
            tags_to_scan = all_tags[-30:] if all_tags else []

        logger.info(f"Found {len(tags_to_scan)} tags to scan for repository {repository_name}")

        # Check repository type using the first tag
        if tags_to_scan:
            first_tag = tags_to_scan[0]
            manifest, _ = get_manifest(registry, repository_name, first_tag)
            if manifest and is_helm_chart(manifest):
                repository.repository_type = 'helm'
                repository.save()
                logger.info(f"Repository {repository_name} identified as Helm chart")

        # Create tags in bulk (skip existing)
        if tags_to_scan:
            existing_tags = set(
                RepositoryTag.objects.filter(
                    repository=repository, tag__in=tags_to_scan
                ).values_list('tag', flat=True)
            )
            new_tag_objs = [
                RepositoryTag(tag=t, repository=repository)
                for t in tags_to_scan if t not in existing_tags
            ]
            if new_tag_objs:
                RepositoryTag.objects.bulk_create(new_tag_objs, ignore_conflicts=True)

        repository.last_scanned = datetime.now()
        repository.save()
        logger.info(f"Successfully scanned repository {repository_name}")
        
        return {
            "status": "success",
            "task_name": "Scan Repository",
            "repository_name": repository_name,
            "repository_url": repository_url,
            "scan_option": scan_option,
            "repository_type": repository.repository_type,
            "repository_created": created,
            "tags_processed": len(tags_to_scan),
            "total_tags_available": len(all_tags),
            "registry_provider": registry.provider,
            "last_scanned": repository.last_scanned.isoformat() if repository.last_scanned else None,
            "message": f"Successfully scanned repository {repository_name}",
            "details": {
                "tags_scanned": tags_to_scan,
                "repository_status": repository.status,
                "scan_timestamp": datetime.now().isoformat()
            }
        }

    except Exception as e:
        logger.error(f"Error scanning repository {repository_name}: {str(e)}")
        if repository:
            repository.status = False
            repository.save()
        raise

@celery_app.task(name="Process All Tags")
def process_all_tags():
    """
    Process all tags from active repositories and create images if they don't exist.
    This task can be manually triggered.
    """
    from .models import Repository, RepositoryTag
    from .utils.registry import (
        get_manifest,
        is_helm_chart,
        get_chart_digest,
        get_helm_images,
        get_helm_chart_url,
        get_helm_images_from_native_chart,
    )

    logger.info("Starting processing of all tags from active repositories")

    results = []
    active_repositories = Repository.objects.filter(status=True).select_related(
        'container_registry'
    ).prefetch_related(
        'image_fallback_repositories',
        'image_fallback_repositories__container_registry',
    )
    logger.info(f"Found {active_repositories.count()} active repositories")

    for repository in active_repositories:
        try:
            logger.info(f"Processing repository: {repository.name}")
            repository_tags = RepositoryTag.objects.filter(repository=repository).select_related('repository')
            logger.info(f"Found {repository_tags.count()} tags for repository {repository.name}")

            # Get registry (for token and provider-specific digest)
            registry = repository.container_registry

            processed_tags = []
            for repo_tag in repository_tags:
                # For Docker images, just create the record
                if repository.repository_type == 'docker':
                    image_ref = _repository_tag_image_ref(repository, repo_tag, registry)
                    image_digest = _resolve_repository_tag_image_digest(
                        repo_tag,
                        image_ref,
                        registry,
                    )
                    image, created = _get_or_create_canonical_image(
                        name=image_ref,
                        digest=image_digest,
                        artifact_reference=image_ref,
                    )
                    image.repository_tags.add(repo_tag)
                    logger.info(f"{'Created' if created else 'Linked'} Docker image {image_ref}")
                else:
                    # For Helm: native Helm (Artifactory) or OCI manifest
                    image_refs = []
                    if repository.repository_type == 'helm' and registry.provider == 'jfrog':
                        if repository.repo_key:
                            rk = repository.repo_key
                            chart_name = repository.name[len(rk) + 1:] if repository.name.startswith(rk + '/') else repository.name
                        else:
                            chart_name = (getattr(repo_tag, 'image_path', None) or '').strip()
                        helm_repo_key = repository.repo_key or repository.name
                        chart_url = get_helm_chart_url(registry, helm_repo_key, chart_name, repo_tag.tag)
                        if chart_url:
                            try:
                                image_refs = get_helm_images_from_native_chart(registry, chart_url)
                            except Exception as exc:
                                logger.error(
                                    "Failed Helm image discovery for %s:%s: %s",
                                    repository.name,
                                    repo_tag.tag,
                                    exc,
                                )
                                repo_tag.processing_status = 'error'
                                repo_tag.save(update_fields=['processing_status', 'updated_at'])
                                continue
                        else:
                            logger.error(
                                "Could not resolve chart URL for Helm tag %s:%s",
                                repository.name,
                                repo_tag.tag,
                            )
                            repo_tag.processing_status = 'error'
                            repo_tag.save(update_fields=['processing_status', 'updated_at'])
                            continue
                    else:
                        if repository.repo_key:
                            rk = repository.repo_key
                            img_name = repository.name[len(rk) + 1:] if repository.name.startswith(rk + '/') else repository.name
                        else:
                            img_name = getattr(repo_tag, 'image_path', None) or None
                        repo_for_manifest = repository.repo_key or repository.name
                        manifest, digest = get_manifest(registry, repo_for_manifest, repo_tag.tag, image_name=img_name)
                        if not manifest:
                            logger.warning(f"Could not get manifest for {repository.name}:{repo_tag.tag}")
                            repo_tag.processing_status = 'error'
                            repo_tag.save(update_fields=['processing_status', 'updated_at'])
                            continue
                        if is_helm_chart(manifest):
                            chart_digest = get_chart_digest(manifest)
                            if chart_digest:
                                try:
                                    image_refs = list(get_helm_images(registry, repository.name, chart_digest))
                                except Exception as exc:
                                    logger.error(
                                        "Failed Helm image discovery for %s:%s: %s",
                                        repository.name,
                                        repo_tag.tag,
                                        exc,
                                    )
                                    repo_tag.processing_status = 'error'
                                    repo_tag.save(update_fields=['processing_status', 'updated_at'])
                                    continue
                            else:
                                logger.error(
                                    "Could not extract chart digest for Helm tag %s:%s",
                                    repository.name,
                                    repo_tag.tag,
                                )
                                repo_tag.processing_status = 'error'
                                repo_tag.save(update_fields=['processing_status', 'updated_at'])
                                continue
                        else:
                            logger.error(
                                "Manifest for %s:%s is not recognized as a Helm chart",
                                repository.name,
                                repo_tag.tag,
                            )
                            repo_tag.processing_status = 'error'
                            repo_tag.save(update_fields=['processing_status', 'updated_at'])
                            continue

                    for image_ref in image_refs:
                        resolved_image_ref, image_digest, _resolved_artifact_ref, resolution_error = _resolve_helm_image_location(
                            repository,
                            repo_tag,
                            registry,
                            image_ref,
                        )
                        if resolution_error:
                            logger.error(
                                "Failed Helm image resolution for %s:%s -> %s: %s",
                                repository.name,
                                repo_tag.tag,
                                image_ref,
                                resolution_error,
                            )
                            repo_tag.processing_status = 'error'
                            repo_tag.save(update_fields=['processing_status', 'updated_at'])
                            continue
                        # Create or get image with proper digest
                        artifact_ref = f"{repository.url}:{repo_tag.tag}"
                        if image_digest:
                            image = Image.objects.filter(name=resolved_image_ref, digest=image_digest).first()
                            if image:
                                created = False
                            else:
                                existing_image = Image.objects.filter(name=resolved_image_ref).exclude(digest=image_digest).first()
                                if existing_image:
                                    image = Image.objects.create(
                                        name=resolved_image_ref,
                                        digest=image_digest,
                                        artifact_reference=artifact_ref
                                    )
                                    created = True
                                else:
                                    image = Image.objects.create(
                                        name=resolved_image_ref,
                                        digest=image_digest,
                                        artifact_reference=artifact_ref
                                    )
                                    created = True
                        else:
                            image = Image.objects.filter(name=resolved_image_ref).first()
                            if image:
                                created = False
                            else:
                                image = Image.objects.create(
                                    name=resolved_image_ref,
                                    digest=None,
                                    artifact_reference=artifact_ref
                                )
                                created = True
                        image.repository_tags.add(repo_tag)
                        logger.info(
                            "%s Helm image %s with digest %s",
                            'Created' if created else 'Linked',
                            resolved_image_ref,
                            image_digest,
                        )

                processed_tags.append(repo_tag.tag)

            results.append({
                "repository": repository.name,
                "status": "success",
                "tags_processed": len(processed_tags)
            })

        except Exception as e:
            logger.error(f"Error processing repository {repository.name}: {str(e)}")
            results.append({
                "repository": repository.name,
                "status": "error",
                "error": str(e)
            })

    # Calculate summary statistics
    total_repositories = len(results)
    successful_repositories = len([r for r in results if r['status'] == 'success'])
    failed_repositories = len([r for r in results if r['status'] == 'error'])
    total_tags_processed = sum([r.get('tags_processed', 0) for r in results if r['status'] == 'success'])
    
    return {
        "status": "completed",
        "task_name": "Process All Tags",
        "summary": {
            "total_repositories_processed": total_repositories,
            "successful_repositories": successful_repositories,
            "failed_repositories": failed_repositories,
            "total_tags_processed": total_tags_processed,
            "success_rate": f"{(successful_repositories / total_repositories * 100):.1f}%" if total_repositories > 0 else "0%"
        },
        "results": results,
        "message": f"Tag processing completed: {successful_repositories}/{total_repositories} repositories processed successfully, {total_tags_processed} tags processed"
    }

@celery_app.task(name="Parse SBOM and Create Components")
def parse_sbom_and_create_components(image_uuid: str, scan_run_uuid: str | None = None):
    """
    Parse SBOM data from an image and create corresponding components and component versions.
    This task should be called after SBOM generation is complete.
    """
    from .models import Image, Component, ComponentVersion
    from .services.purl import component_identity
    from django.db import transaction
    from django.db.models import Q
    from collections import defaultdict
    import time

    logger.info(f"Starting SBOM parsing for image {image_uuid}")
    start_time = time.time()

    try:
        # Get image with prefetched related data
        image = Image.objects.select_related().prefetch_related(
            'component_versions__component',
            'component_versions__vulnerabilities'
        ).get(uuid=image_uuid)
        logger.info(f"Found image: {image.name} (digest: {image.digest})")
        
        if not image.sbom_data:
            logger.warning(f"No SBOM data found for image {image_uuid}")
            return {
                "status": "error",
                "task_name": "Parse SBOM and Create Components",
                "image_uuid": str(image_uuid),
                "error": "No SBOM data found",
                "error_type": "MissingSBOMData",
                "message": "Image does not have SBOM data for parsing",
                "suggestion": "Ensure SBOM generation task completed successfully before parsing",
                "timestamp": timezone.now().isoformat()
            }

        if image.scan_status not in ['success', 'in_process']:
            logger.warning(f"Image {image_uuid} scan status is not success: {image.scan_status}")
            return {
                "status": "error",
                "task_name": "Parse SBOM and Create Components",
                "image_uuid": str(image_uuid),
                "error": f"Image scan status is {image.scan_status}",
                "error_type": "InvalidScanStatus",
                "message": f"Image scan status '{image.scan_status}' is not valid for SBOM parsing",
                "suggestion": "Wait for SBOM generation to complete or check image scan status",
                "timestamp": timezone.now().isoformat()
            }

        # Process artifacts in batches
        BATCH_SIZE = 1000
        components_created = 0
        versions_created = 0
        components_updated = 0
        artifacts = image.sbom_data.get('artifacts', [])
        total_artifacts = len(artifacts)

        logger.info(f"Found {total_artifacts} artifacts in SBOM")
        logger.info(f"Processing artifacts in batches of {BATCH_SIZE}")

        # Process artifacts in batches
        for i in range(0, total_artifacts, BATCH_SIZE):
            batch_start_time = time.time()
            batch = artifacts[i:i + BATCH_SIZE]
            current_batch = i//BATCH_SIZE + 1
            total_batches = (total_artifacts + BATCH_SIZE - 1)//BATCH_SIZE
            
            logger.info(f"Processing batch {current_batch}/{total_batches} ({len(batch)} artifacts)")
            
            # Collect unique component names and versions
            component_data = {}
            skipped_artifacts = 0
            for artifact in batch:
                name = artifact.get('name')
                version = artifact.get('version')
                component_type = artifact.get('type', 'unknown')
                purl = artifact.get('purl')
                cpes = artifact.get('cpes', [])

                if not name or not version:
                    skipped_artifacts += 1
                    continue

                identity = component_identity(purl, component_type, name)
                if identity not in component_data:
                    component_data[identity] = {
                        'name': name,
                        'type': component_type,
                        'identity': identity,
                        'versions': {},
                        'purl': purl
                    }

                component_data[identity]['versions'][version] = {
                    'purl': purl,
                    'cpes': cpes
                }

            if skipped_artifacts:
                logger.warning(f"Skipped {skipped_artifacts} artifacts in batch {current_batch} due to missing name or version")

            logger.info(f"Found {len(component_data)} unique components in batch {current_batch}")

            # Get existing components
            existing_components = {
                c.identity: c for c in Component.objects.filter(identity__in=component_data.keys())
            }
            logger.info(f"Found {len(existing_components)} existing components in batch {current_batch}")

            # Initialize lists for bulk operations
            components_to_create = []
            components_to_update = []
            component_versions_to_create = []
            component_versions_to_update = []

            # Prepare components for creation/update
            for identity, data in component_data.items():
                if identity in existing_components:
                    component = existing_components[identity]
                    # Update component if needed
                    if data['type'] != 'unknown' and component.type == 'unknown':
                        component.type = data['type']
                        components_to_update.append(component)
                else:
                    # Create new component
                    components_to_create.append(Component(
                        name=data['name'], type=data['type'], identity=identity,
                    ))

            logger.info(f"Prepared {len(components_to_create)} components for creation and {len(components_to_update)} for update in batch {current_batch}")

            # Bulk create/update components
            with transaction.atomic():
                if components_to_create:
                    created_components = Component.objects.bulk_create(components_to_create)
                    components_created += len(created_components)
                    logger.info(f"Created {len(created_components)} new components in batch {current_batch}")
                    # Add new components to existing_components dict
                    existing_components.update({c.identity: c for c in created_components})

                if components_to_update:
                    Component.objects.bulk_update(
                        components_to_update,
                        ['type']
                    )
                    components_updated += len(components_to_update)
                    logger.info(f"Updated {len(components_to_update)} existing components in batch {current_batch}")

                batch_versions = {
                    version
                    for data in component_data.values()
                    for version in data['versions'].keys()
                }
                existing_versions = {
                    f"{cv.component.identity}:{cv.version}": cv
                    for cv in ComponentVersion.objects.filter(
                        component_id__in=[component.pk for component in existing_components.values()],
                        version__in=batch_versions,
                    ).select_related('component')
                }
                logger.info(f"Found {len(existing_versions)} existing component versions in batch {current_batch}")

                # Prepare component versions
                for identity, data in component_data.items():
                    component = existing_components[identity]
                    for version, version_data in data['versions'].items():
                        version_key = f"{identity}:{version}"
                        if version_key not in existing_versions:
                            component_versions_to_create.append(ComponentVersion(
                                component=component,
                                version=version,
                                purl=version_data['purl'],
                                cpes=version_data['cpes']
                            ))
                        else:
                            # Update existing version if purl or cpes are missing
                            version_obj = existing_versions[version_key]
                            if (version_data['purl'] and not version_obj.purl) or \
                               (version_data['cpes'] and not version_obj.cpes):
                                version_obj.purl = version_data['purl'] or version_obj.purl
                                version_obj.cpes = version_data['cpes'] or version_obj.cpes
                                component_versions_to_update.append(version_obj)

                logger.info(f"Prepared {len(component_versions_to_create)} component versions for creation in batch {current_batch}")

                # Bulk create component versions
                if component_versions_to_create:
                    version_keys_before = set(existing_versions.keys())
                    ComponentVersion.objects.bulk_create(
                        component_versions_to_create,
                        ignore_conflicts=True,
                    )
                    logger.info(
                        f"Attempted to create {len(component_versions_to_create)} component versions in batch {current_batch}"
                    )

                if component_versions_to_update:
                    versions_to_update_by_pk = {cv.pk: cv for cv in component_versions_to_update}
                    ComponentVersion.objects.bulk_update(
                        list(versions_to_update_by_pk.values()),
                        ['purl', 'cpes'],
                    )
                    logger.info(
                        f"Updated {len(versions_to_update_by_pk)} existing component versions in batch {current_batch}"
                    )

                refreshed_versions = {
                    f"{cv.component.identity}:{cv.version}": cv
                    for cv in ComponentVersion.objects.filter(
                        component_id__in=[component.pk for component in existing_components.values()],
                        version__in=batch_versions,
                    ).select_related('component')
                }
                if component_versions_to_create:
                    versions_created += len(set(refreshed_versions.keys()) - version_keys_before)
                    logger.info(
                        f"Resolved {len(refreshed_versions)} component versions after create in batch {current_batch}"
                    )
                existing_versions = refreshed_versions

                # Link image to component versions in one query.  `images.add()` in
                # this loop used to emit one INSERT per SBOM artifact.
                image_version_pks = set(image.component_versions.values_list('pk', flat=True))
                through_model = ComponentVersion.images.through
                links_to_create = []
                for identity, data in component_data.items():
                    for version, version_data in data['versions'].items():
                        version_key = f"{identity}:{version}"
                        version_obj = existing_versions[version_key]
                        if version_obj.pk not in image_version_pks:
                            links_to_create.append(
                                through_model(componentversion_id=version_obj.pk, image_id=image.pk)
                            )
                            image_version_pks.add(version_obj.pk)
                if links_to_create:
                    through_model.objects.bulk_create(links_to_create, ignore_conflicts=True)

                lineage_update_fields = _apply_image_lineage_fields(
                    image,
                    component_version_purls=[
                        version_data.get('purl')
                        for data in component_data.values()
                        for version_data in data['versions'].values()
                    ],
                )
                if lineage_update_fields:
                    image.save(update_fields=lineage_update_fields + ['updated_at'])

            batch_time = time.time() - batch_start_time
            logger.info(f"Completed batch {current_batch}/{total_batches} in {batch_time:.2f} seconds")

        context_summary = _upsert_image_component_version_contexts(image)
        logger.info(
            "Updated image component contexts for %s: created=%s updated=%s deleted=%s",
            image_uuid,
            context_summary['contexts_created'],
            context_summary['contexts_updated'],
            context_summary['contexts_deleted'],
        )

        total_time = time.time() - start_time
        logger.info(f"SBOM parsing completed in {total_time:.2f} seconds")
        logger.info(f"Summary:")
        logger.info(f"- Total artifacts processed: {total_artifacts}")
        logger.info(f"- Components created: {components_created}")
        logger.info(f"- Components updated: {components_updated}")
        logger.info(f"- Component versions created: {versions_created}")

        # Schedule Grype scan after successful SBOM processing
        scan_image_with_grype.delay(str(image_uuid), scan_run_uuid)
        logger.info(f"Scheduled Grype scan for image {image_uuid}")

        return {
            "status": "success",
            "task_name": "Parse SBOM and Create Components",
            "image_uuid": str(image_uuid),
            "image_name": image.name,
            "image_digest": image.digest,
            "summary": {
                "total_artifacts_processed": total_artifacts,
                "components_created": components_created,
                "components_updated": components_updated,
                "versions_created": versions_created,
                "total_batches_processed": (total_artifacts + BATCH_SIZE - 1) // BATCH_SIZE
            },
            "processing_time": total_time,
            "processing_time_formatted": f"{total_time:.2f} seconds",
            "grype_scan_scheduled": True,
            "message": f"SBOM parsing completed successfully for image {image.name}",
            "next_steps": ["Grype vulnerability scan scheduled"],
            "timestamp": timezone.now().isoformat()
        }

    except Image.DoesNotExist:
        logger.error(f"Image with UUID {image_uuid} not found")
        return {
            "status": "error",
            "task_name": "Parse SBOM and Create Components",
            "image_uuid": str(image_uuid),
            "error": f"Image with UUID {image_uuid} not found",
            "error_type": "ImageNotFound",
            "message": "Specified image does not exist in database",
            "suggestion": "Verify image UUID and ensure image exists before parsing",
            "timestamp": timezone.now().isoformat()
        }
    except Exception as e:
        if scan_run_uuid:
            from .services.scans import finish_scan
            finish_scan(scan_run_uuid, error=str(e))
        logger.error(f"Error parsing SBOM for image {image_uuid}: {str(e)}")
        try:
            image = Image.objects.get(uuid=image_uuid)
            image.scan_status = 'error'
            image.save(update_fields=['scan_status', 'updated_at'])
            _sync_repository_tag_processing_statuses(
                list(image.repository_tags.values_list('pk', flat=True))
            )
        except Exception as save_error:
            logger.error(f"Failed to update image status after SBOM parsing error: {str(save_error)}")
        return {
            "status": "error",
            "task_name": "Parse SBOM and Create Components",
            "image_uuid": str(image_uuid),
            "error": str(e),
            "error_type": type(e).__name__,
            "message": f"Unexpected error occurred during SBOM parsing: {str(e)}",
            "suggestion": "Check system resources, database connectivity, and SBOM data integrity",
            "timestamp": timezone.now().isoformat()
        }

@celery_app.task(name="Update Components Latest Versions")
def update_components_latest_versions(image_uuid: str):
    """
    Update latest versions for all component versions in an image.
    This task can be triggered manually through the API.
    """
    from .models import Image, ComponentVersion

    logger.info(f"Starting latest versions update for image {image_uuid}")
    start_time = time.time()

    try:
        image = Image.objects.prefetch_related(
            'component_versions__component'
        ).get(uuid=image_uuid)
        component_versions = list(image.component_versions.all())
        total_component_versions = len(component_versions)
        logger.info(f"Found {len(component_versions)} component versions to process")
        updated_count = 0
        versions_to_update = []
        for component_version in component_versions:
            try:
                now = timezone.now()
                if (
                    component_version.latest_version_updated_at and
                    (now - component_version.latest_version_updated_at).days <= 4
                ):
                    logger.info(
                        f"Skipped update for {component_version.component.name}:{component_version.version} (last updated {component_version.latest_version_updated_at})"
                    )
                    continue
                if not component_version.purl:
                    logger.info(f"No PURL found for component version {component_version.component.name}:{component_version.version}")
                    continue
                logger.info(f"Processing component version {component_version.component.name}:{component_version.version}")
                if DEBUG_LOGGING:
                    logger.debug(f"Processing PURL: {component_version.purl}")
                latest_version = _lookup_latest_version_for_purl(component_version.purl)
                if latest_version:
                    component_version.latest_version = latest_version
                    component_version.latest_version_updated_at = now
                    versions_to_update.append(component_version)
                    updated_count += 1
                    logger.info(
                        f"Updated latest version for {component_version.component.name}:{component_version.version} to {latest_version} (updated_at={now})"
                    )
            except Exception as e:
                logger.warning(
                    f"Error processing component version {component_version.component.name}:{component_version.version}: {str(e)}"
                )
                continue
        if versions_to_update:
            ComponentVersion.objects.bulk_update(
                versions_to_update,
                ['latest_version', 'latest_version_updated_at'],
                batch_size=200
            )
        total_time = time.time() - start_time
        logger.info(f"Latest versions update completed in {total_time:.2f} seconds")
        logger.info(f"Updated latest versions for {updated_count} component versions")
        return {
            "status": "success",
            "task_name": "Update Components Latest Versions",
            "image_uuid": str(image_uuid),
            "image_name": image.name,
            "summary": {
                "total_component_versions_processed": total_component_versions,
                "component_versions_updated": updated_count,
                "component_versions_skipped": total_component_versions - updated_count,
                "update_rate": f"{(updated_count / total_component_versions * 100):.1f}%" if total_component_versions > 0 else "0%"
            },
            "processing_time": total_time,
            "processing_time_formatted": f"{total_time:.2f} seconds",
            "message": f"Latest versions updated for {updated_count} component versions in image {image.name}",
            "timestamp": timezone.now().isoformat()
        }
    except Image.DoesNotExist:
        logger.error(f"Image with UUID {image_uuid} not found")
        return {
            "status": "error",
            "task_name": "Update Components Latest Versions",
            "image_uuid": str(image_uuid),
            "error": f"Image with UUID {image_uuid} not found",
            "error_type": "ImageNotFound",
            "message": "Specified image does not exist in database",
            "suggestion": "Verify image UUID and ensure image exists before updating component versions",
            "timestamp": timezone.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error updating latest versions for image {image_uuid}: {str(e)}")
        return {
            "status": "error",
            "task_name": "Update Components Latest Versions",
            "image_uuid": str(image_uuid),
            "error": str(e),
            "error_type": type(e).__name__,
            "message": f"Unexpected error occurred during latest versions update: {str(e)}",
            "suggestion": "Check network connectivity, external API availability, and system resources",
            "timestamp": timezone.now().isoformat()
        }

@celery_app.task(name="Process Grype Scan Results")
def process_grype_scan_results(image_uuid: str, scan_results: dict, scan_run_uuid: str | None = None):
    """
    Process Grype scan results for an image and update the database with vulnerability information.
    Optimized for bulk operations and safe parallel execution.
    """
    from .models import Image, Component, ComponentVersion, Vulnerability, ComponentVersionVulnerability, VulnerabilityDetails, ComponentLocation
    from .services.purl import component_identity
    from django.db import IntegrityError
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"Processing Grype scan results for image {image_uuid}")

    try:
        image = Image.objects.get(uuid=image_uuid)
        matches = scan_results.get('matches', [])
        eol_update_fields = _apply_image_os_eol_fields(image, grype_data=scan_results)

        # Collect unique names/versions/ids
        component_names = set()
        component_versions_set = set()
        vuln_ids = set()
        for match in matches:
            artifact = match.get('artifact', {})
            component_name = artifact.get('name')
            component_version = artifact.get('version')
            if component_name:
                component_names.add(component_name)
            if component_name and component_version:
                component_versions_set.add((component_name, component_version))
            vulnerability_data = match.get('vulnerability', {})
            vuln_id = vulnerability_data.get('id', '')
            if vuln_id:
                vuln_ids.add(vuln_id)

        # Bulk create Components with optimized query
        existing_components = {c.name: c for c in Component.objects.filter(name__in=component_names)}
        new_components = [Component(name=name) for name in component_names if name not in existing_components]
        if new_components:
            Component.objects.bulk_create(new_components, ignore_conflicts=True)
            # Refresh cache only if new components were created
            existing_components.update({c.name: c for c in Component.objects.filter(
                name__in=[nc.name for nc in new_components]
            )})

        # Bulk create Vulnerabilities with optimized query
        existing_vulns = {v.vulnerability_id: v for v in Vulnerability.objects.filter(vulnerability_id__in=vuln_ids)}
        new_vulns = [Vulnerability(vulnerability_id=vid) for vid in vuln_ids if vid not in existing_vulns]
        if new_vulns:
            Vulnerability.objects.bulk_create(new_vulns, ignore_conflicts=True)
            # Refresh cache only if new vulnerabilities were created
            existing_vulns.update({v.vulnerability_id: v for v in Vulnerability.objects.filter(
                vulnerability_id__in=[nv.vulnerability_id for nv in new_vulns]
            )})

        # Bulk create ComponentVersions with optimized query
        existing_versions = {(cv.component.name, cv.version): cv for cv in ComponentVersion.objects.filter(
            component__name__in=component_names,
            version__in=[v for _, v in component_versions_set]
        ).select_related('component')}
        new_versions = [
            ComponentVersion(component=existing_components[name], version=version)
            for (name, version) in component_versions_set if (name, version) not in existing_versions
        ]
        if new_versions:
            ComponentVersion.objects.bulk_create(new_versions, ignore_conflicts=True)
            # Refresh cache only if new versions were created
            existing_versions.update({(cv.component.name, cv.version): cv for cv in ComponentVersion.objects.filter(
                component__name__in=[nv.component.name for nv in new_versions],
                version__in=[nv.version for nv in new_versions]
            ).select_related('component')})

        # Pre-load component versions already linked to this image to avoid per-match EXISTS queries
        _linked_cv_pks = set(image.component_versions.values_list('pk', flat=True))

        # Process each match
        for match in matches:
            vulnerability_data = match.get('vulnerability', {})
            vuln_id = vulnerability_data.get('id', '')
            severity = vulnerability_data.get('severity', 'UNKNOWN').upper()
            description = vulnerability_data.get('description', '')
            vuln_type = 'CVE'
            if vuln_id.startswith('GHSA-'):
                vuln_type = 'GHSA'
            elif vuln_id.startswith('RUSTSEC-'):
                vuln_type = 'RUSTSEC'
            elif vuln_id.startswith('PYSEC-'):
                vuln_type = 'PYSEC'
            elif vuln_id.startswith('NPM-'):
                vuln_type = 'NPM'
            epss_score = 0.0
            epss_data = vulnerability_data.get('epss', [])
            if isinstance(epss_data, list) and epss_data:
                epss_score = epss_data[0].get('epss', 0.0)
            elif isinstance(epss_data, (int, float)):
                epss_score = float(epss_data)

            # Get or create vulnerability (safe for parallel)
            vulnerability, _ = Vulnerability.objects.get_or_create(
                vulnerability_id=vuln_id,
                defaults={
                    'vulnerability_type': vuln_type,
                    'severity': severity,
                    'description': description,
                    'epss': epss_score
                }
            )
            # Update fields if needed
            updated = False
            if vulnerability.severity != severity:
                vulnerability.severity = severity
                updated = True
            if vulnerability.description != description:
                vulnerability.description = description
                updated = True
            if vulnerability.epss != epss_score:
                vulnerability.epss = epss_score
                updated = True
            if updated:
                vulnerability.save()

            artifact = match.get('artifact', {})
            component_name = artifact.get('name')
            component_type = artifact.get('type', 'unknown')
            component_version = artifact.get('version')
            purl = artifact.get('purl')
            cpes = artifact.get('cpes', [])
            locations = artifact.get('locations', [])

            if component_name and component_version:
                # Get or create component (safe for parallel)
                identity = component_identity(purl, component_type, component_name)
                component = Component.objects.filter(identity=identity).order_by('created_at').first()
                if component is None:
                    component = Component.objects.create(
                        identity=identity, name=component_name, type=component_type,
                    )
                # Update type if needed
                if component.type == 'unknown' and component_type != 'unknown':
                    component.type = component_type
                    component.save()
                # Get or create component version (safe for parallel)
                component_version_obj, _ = ComponentVersion.objects.get_or_create(
                    version=component_version,
                    component=component,
                    defaults={'purl': purl, 'cpes': cpes}
                )
                # Update purl/cpes if needed
                updated = False
                if purl and not component_version_obj.purl:
                    component_version_obj.purl = purl
                    updated = True
                if cpes and not component_version_obj.cpes:
                    component_version_obj.cpes = cpes
                    updated = True
                if updated:
                    component_version_obj.save()

                fix_metadata = _determine_fix_metadata(component_version_obj, vulnerability_data)

                # Link image to component version (use in-memory set to skip DB check)
                if component_version_obj.pk not in _linked_cv_pks:
                    component_version_obj.images.add(image)
                    _linked_cv_pks.add(component_version_obj.pk)
                    logger.info(f"Linked component version {component_version} to image {image.name}")
                
                # Process component locations
                for location in locations:
                    path = location.get('path', '')
                    layer_id = location.get('layerID', '')
                    access_path = location.get('accessPath', '')
                    annotations = location.get('annotations', {})
                    
                    # Determine evidence type from annotations
                    evidence_type = 'unknown'
                    if annotations:
                        evidence = annotations.get('evidence', '')
                        if evidence == 'primary':
                            evidence_type = 'primary'
                        elif evidence == 'supporting':
                            evidence_type = 'supporting'
                    
                    # Create or update component location
                    ComponentLocation.objects.get_or_create(
                        component_version=component_version_obj,
                        image=image,
                        path=path,
                        defaults={
                            'layer_id': layer_id,
                            'access_path': access_path,
                            'evidence_type': evidence_type,
                            'annotations': annotations
                        }
                    )
                
                # Get or create CVV (safe for parallel)
                cvv, _ = ComponentVersionVulnerability.objects.get_or_create(
                    component_version=component_version_obj,
                    vulnerability=vulnerability,
                    defaults=fix_metadata,
                )
                # Update fix info if needed
                if not _:
                    updated = False
                    for field_name, field_value in fix_metadata.items():
                        if getattr(cvv, field_name) != field_value:
                            setattr(cvv, field_name, field_value)
                            updated = True
                    if updated:
                        cvv.save(update_fields=['fixable', 'fix', 'fix_state', 'fix_status', 'fix_versions', 'updated_at'])

        # Set status to success only after all matches are processed
        image.scan_status = 'success'
        image.grype_data = scan_results
        image.save(update_fields=['scan_status', 'grype_data', *eol_update_fields, 'updated_at'])
        if scan_run_uuid:
            from .services.scans import finish_scan, store_raw_artifact
            from .models import ScanRun
            store_raw_artifact(image, 'grype', scan_results, scan_run=ScanRun.objects.get(pk=scan_run_uuid))
            finish_scan(scan_run_uuid)
        related_tag_ids = _propagate_image_completion_to_equivalent_images(image)
        _sync_repository_tag_processing_statuses(related_tag_ids)
        logger.info(f"Successfully processed Grype scan results for image {image_uuid}")
        logger.info(f"Total matches processed: {len(matches)}")
        # Calculate summary statistics
        total_matches = len(matches)
        unique_vulnerabilities = len(set(match.get('vulnerability', {}).get('id', '') for match in matches))
        unique_components = len(set(match.get('artifact', {}).get('name', '') for match in matches))
        
        return {
            "status": "success",
            "task_name": "Process Grype Scan Results",
            "image_uuid": str(image_uuid),
            "image_name": image.name,
            "summary": {
                "total_matches_processed": total_matches,
                "unique_vulnerabilities_found": unique_vulnerabilities,
                "unique_components_affected": unique_components,
                "scan_status_updated": True
            },
            "message": f"Grype scan results processed successfully for image {image.name}",
            "details": {
                "vulnerabilities_processed": total_matches,
                "image_scan_status": "success",
                "processing_timestamp": timezone.now().isoformat()
            },
            "timestamp": timezone.now().isoformat()
        }

    except Image.DoesNotExist:
        logger.error(f"Image with UUID {image_uuid} not found")
        return {
            "status": "error",
            "error": f"Image with UUID {image_uuid} not found"
        }
    except Exception as e:
        if scan_run_uuid:
            from .services.scans import finish_scan
            finish_scan(scan_run_uuid, error=str(e))
        error_msg = f"Error processing Grype scan results for image {image_uuid}: {str(e)}"
        logger.error(error_msg)
        
        # Try to update image status to error
        try:
            image = Image.objects.get(uuid=image_uuid)
            image.scan_status = 'error'
            image.save()
            _sync_repository_tag_processing_statuses(
                list(image.repository_tags.values_list('pk', flat=True))
            )
        except Exception as save_error:
            logger.error(f"Failed to update image status: {str(save_error)}")
        
        return {
            "status": "error",
            "error": error_msg,
            "error_type": type(e).__name__
        }

@celery_app.task(bind=True, max_retries=1, name="Scan Image with Grype")
def scan_image_with_grype(self, image_uuid: str, scan_run_uuid: str | None = None):
    """
    Scan an image's SBOM with Grype and save the results.
    This task should be called after SBOM generation is complete.
    
    Args:
        image_uuid (str): UUID of the Image to scan
    """
    from .models import Image
    import subprocess
    import json
    import tempfile
    import os

    logger.info(f"Starting Grype scan for image {image_uuid}")
    
    try:
        # Get image
        image = Image.objects.get(uuid=image_uuid)
        
        # Allow the normal Syft -> Parse SBOM -> Grype pipeline to continue while the image
        # is already marked in_process; only skip if another Grype run has already produced data.
        if image.scan_status == 'in_process' and image.grype_data:
            logger.warning(f"Image {image_uuid} is already being scanned")
            return {"status": "skipped", "reason": "already in process"}

        # Check if we have SBOM data
        if not image.sbom_data:
            logger.error(f"No SBOM data found for image {image_uuid}")
            image.scan_status = 'error'
            image.save()
            _sync_repository_tag_processing_statuses(
                list(image.repository_tags.values_list('pk', flat=True))
            )
            return {
                "status": "error",
                "error": "No SBOM data found"
            }

        # Update status to in_process
        image.scan_status = 'in_process'
        image.save()

        # Create temporary files for SBOM and Grype results
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as sbom_file, \
             tempfile.NamedTemporaryFile(suffix='.json', delete=False) as grype_file:
            sbom_file_path = sbom_file.name
            grype_file_path = grype_file.name

        try:
            # Save SBOM data to temporary file
            with open(sbom_file_path, 'w') as f:
                json.dump(image.sbom_data, f)

            # Run Grype scan on SBOM file
            logger.info(f"Running Grype scan on SBOM for image {image_uuid}")
            result = subprocess.run(
                ["grype", f"sbom:{sbom_file_path}", "--output", "json", "--file", grype_file_path],
                capture_output=True,
                check=True,
                text=True
            )

            # Read Grype results
            with open(grype_file_path, 'r') as f:
                grype_results = json.load(f)

            # Save Grype results to image (but don't set status to success yet)
            # Status will be set to 'success' in process_grype_scan_results after vulnerabilities are processed
            image.grype_data = grype_results
            image.scan_status = 'in_process'  # Keep as in_process until vulnerabilities are processed
            image.save()
            logger.info(f"Saved Grype results for image {image_uuid}")

            # Process Grype results (this will set status to 'success' when done)
            process_grype_scan_results.delay(str(image_uuid), grype_results, scan_run_uuid)
            
            logger.info(f"Successfully scanned image {image_uuid} with Grype")
            return {
                "status": "success",
                "task_name": "Scan Image with Grype",
                "image_uuid": str(image_uuid)
            }

        finally:
            # Clean up temporary files
            for file_path in [sbom_file_path, grype_file_path]:
                if os.path.exists(file_path):
                    os.unlink(file_path)
    
    except Image.DoesNotExist:
        logger.error(f"Image with UUID {image_uuid} not found")
        return {
            "status": "error",
            "error": f"Image with UUID {image_uuid} not found"
        }
    except Exception as e:
        if scan_run_uuid:
            from .services.scans import finish_scan
            finish_scan(scan_run_uuid, error=str(e))
        error_msg = f"Error scanning image {image_uuid} with Grype: {str(e)}"
        logger.error(error_msg)
        
        # Try to update image status to error
        try:
            image = Image.objects.get(uuid=image_uuid)
            image.scan_status = 'error'
            image.save()
            _sync_repository_tag_processing_statuses(
                list(image.repository_tags.values_list('pk', flat=True))
            )
        except Exception as save_error:
            logger.error(f"Failed to update image status: {str(save_error)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        else:
            logger.error(f"Max retries exceeded for image {image_uuid}")
            return {
                "status": "error",
                "error": error_msg,
                "max_retries_exceeded": True
            }

@celery_app.task(name="Rescan All Images with SBOM")
def rescan_all_images_with_sbom():
    """
    Re-analyze all images that have SBOM data using Grype.
    This task schedules individual scans without waiting for them to complete.
    """
    from .models import Image
    from django.db.models import Q
    import time

    logger.info("Starting mass rescan of all images with SBOM")
    start_time = time.time()

    try:
        # Get all images that have SBOM data and are not currently being processed
        images = Image.objects.filter(
            Q(sbom_data__isnull=False) & 
            ~Q(sbom_data={}) &
            ~Q(scan_status__in=['in_process', 'pending'])
        ).order_by('updated_at')

        total_images = images.count()
        logger.info(f"Found {total_images} images with SBOM data to rescan")

        if total_images == 0:
            logger.info("No images with SBOM data found")
            return {
                "status": "success",
                "task_name": "Rescan All Images with SBOM",
                "message": "No images with SBOM data found",
                "images_scheduled": 0,
                "processing_time": 0
            }

        scheduled_count = 0
        error_count = 0
        task_ids = []

        for idx, image in enumerate(images, 1):
            logger.info(f"[{idx}/{total_images}] Scheduling scan for image {image.uuid} ({image.name})")
            
            try:
                # Schedule Grype scan for this image (non-blocking)
                result = scan_image_with_grype.apply_async(args=[str(image.uuid)])
                task_ids.append(result.id)
                scheduled_count += 1
                logger.info(f"✅ Scheduled scan for image {image.name} (task_id: {result.id})")
                
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Error scheduling scan for image {image.uuid} ({image.name}): {str(e)}")
                logger.error(f"Exception type: {type(e).__name__}")
                continue

        total_time = time.time() - start_time
        logger.info(f"🎉 Mass rescan scheduling completed in {total_time:.2f} seconds")
        logger.info(f"📊 Summary:")
        logger.info(f"   - Total images found: {total_images}")
        logger.info(f"   - Successfully scheduled: {scheduled_count}")
        logger.info(f"   - Scheduling errors: {error_count}")
        logger.info(f"   - Processing time: {total_time:.2f} seconds")
        logger.info(f"   - Task IDs: {task_ids[:5]}{'...' if len(task_ids) > 5 else ''}")

        return {
            "status": "success",
            "task_name": "Rescan All Images with SBOM",
            "total_images": total_images,
            "images_scheduled": scheduled_count,
            "scheduling_errors": error_count,
            "processing_time": total_time,
            "task_ids": task_ids
        }

    except Exception as e:
        logger.error(f"❌ Error in mass rescan task: {str(e)}")
        return {
            "status": "error",
            "task_name": "Rescan All Images with SBOM",
            "error": str(e)
        }


@celery_app.task(name="Monitor Mass Rescan Progress") 
def monitor_mass_rescan_progress():
    """
    Monitor the progress of mass rescan by checking scan_status of images with SBOM.
    This can be called periodically to see how many images have been processed.
    """
    from .models import Image
    from django.db.models import Q, Count
    import time

    logger.info("Checking mass rescan progress...")
    
    try:
        # Get stats on images with SBOM
        images_with_sbom = Image.objects.filter(
            Q(sbom_data__isnull=False) & 
            ~Q(sbom_data={})
        )
        
        total_count = images_with_sbom.count()
        
        # Count by scan status
        status_counts = images_with_sbom.values('scan_status').annotate(count=Count('id'))
        status_breakdown = {item['scan_status']: item['count'] for item in status_counts}
        
        # Calculate progress
        completed = status_breakdown.get('success', 0)
        in_progress = status_breakdown.get('in_process', 0) + status_breakdown.get('pending', 0)
        errors = status_breakdown.get('error', 0)
        not_started = total_count - completed - in_progress - errors
        
        progress_percentage = (completed / total_count * 100) if total_count > 0 else 0
        
        logger.info(f"📊 Mass Rescan Progress Report:")
        logger.info(f"   - Total images with SBOM: {total_count}")
        logger.info(f"   - Completed: {completed} ({progress_percentage:.1f}%)")
        logger.info(f"   - In Progress: {in_progress}")
        logger.info(f"   - Errors: {errors}")
        logger.info(f"   - Not Started: {not_started}")
        logger.info(f"   - Status breakdown: {status_breakdown}")
        
        return {
            "status": "success",
            "task_name": "Monitor Mass Rescan Progress",
            "total_images": total_count,
            "completed": completed,
            "in_progress": in_progress,
            "errors": errors,
            "not_started": not_started,
            "progress_percentage": round(progress_percentage, 1),
            "status_breakdown": status_breakdown,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"❌ Error monitoring mass rescan progress: {str(e)}")
        return {
            "status": "error",
            "task_name": "Monitor Mass Rescan Progress",
            "error": str(e)
        }


def _repository_tag_image_ref(repository, repo_tag, registry=None):
    """Build docker image reference. For Artifactory, use repo_key (or legacy image_path) and pull base."""
    if registry and getattr(registry, 'provider', None) == 'jfrog':
        from urllib.parse import urlparse
        parsed = urlparse(registry.api_url or '')
        host = parsed.netloc or ''
        if not host and repository.url:
            host = (repository.url or '').split('/')[0].split('://')[-1]

        # New unified model: repo_key is set, name = repo_key/image_name
        if repository.repo_key:
            rk = repository.repo_key
            image_name = repository.name[len(rk) + 1:] if repository.name.startswith(rk + '/') else repository.name
            pull_base = f"{rk}.{host}" if host else (repository.url or repository.name)
            return f"{pull_base}/{image_name}:{repo_tag.tag}"

        # Legacy collection model: image_path on tag
        image_path = (getattr(repo_tag, 'image_path', None) or '').strip()
        if image_path:
            pull_base = f"{repository.name}.{host}" if host else (repository.url or repository.name)
            return f"{pull_base}/{image_path}:{repo_tag.tag}"

    return f"{repository.url}:{repo_tag.tag}"


# Scan task: allow 1 hour for large Artifactory repos (catalog + many images/tags)
SCAN_REPOSITORY_TAGS_TIME_LIMIT = 3600
SCAN_REPOSITORY_TAGS_SOFT_LIMIT = 3540

# When latest_only: max images to consider; pick one tag per image by highest version number
SCAN_LATEST_ONLY_MAX_IMAGES = 500

# Regex to extract a leading semantic version. Requires either a "v" prefix
# (v1, v1.2, v1.2.3) or a dotted numeric form (1.2, 1.2.3). A bare number
# with no dot and no "v" prefix (e.g. a build number, commit-distance or
# timestamp like "6820093") is deliberately NOT matched here, since such
# tags previously sorted as a huge "major version" and beat real semver
# tags like "6.0.4".
_VERSION_PREFIX_RE = re.compile(r'^v(\d+(?:\.\d+)*)', re.IGNORECASE)
_DOTTED_VERSION_PREFIX_RE = re.compile(r'^(\d+\.\d+(?:\.\d+)*)')


def _version_sort_key(tag: str):
    """
    Return a tuple suitable for sorting tags by version (higher = newer).
    Parse v1.2.3 / 1.2.3 style; unparseable tags get (0,); literal 'latest' gets high fallback.
    """
    tag = (tag or '').strip()
    if not tag:
        return (0,)
    if tag.lower() == 'latest':
        return (999999,)  # prefer when no version-like tags exist
    m = _VERSION_PREFIX_RE.match(tag) or _DOTTED_VERSION_PREFIX_RE.match(tag)
    if m:
        parts = [int(x) for x in m.group(1).split('.')]
        return tuple(parts)
    return (0,)


def _pick_latest_tag_by_version(tags):
    """
    Given a list of tag names, return the one considered 'latest'.

    Double sort, as tags can lie about themselves:
    1) Primary key: parsed semantic version (_version_sort_key), so a real
       version like "6.0.4" always outranks a non-version-looking tag.
    2) Secondary key (tie-break only): position in `tags`. Callers pass tags
       from the registry's chronological listing (e.g. ACR's
       orderby=timedesc), newest first, so the earliest position wins ties -
       i.e. the most recently pushed tag is preferred when versions are
       equal or equally unparseable.
    """
    if not tags:
        return None
    return max(enumerate(tags), key=lambda pair: (_version_sort_key(pair[1]), -pair[0]))[1]


@celery_app.task(
    name="Scan Repository Tags",
    time_limit=SCAN_REPOSITORY_TAGS_TIME_LIMIT,
    soft_time_limit=SCAN_REPOSITORY_TAGS_SOFT_LIMIT,
)
def scan_repository_tags(
    repository_uuid: str,
    latest_only: bool = False,
    process_existing: bool = False,
):
    """
    Task that scans a single repository for tags.
    For Artifactory repo keys: lists images via catalog, then tags per image.
    When latest_only=True, only one tag per image is collected (highest version by number).
    When process_existing=True, already-known tags discovered by this scan are re-queued
    for the standard processing pipeline as long as they are not already pending/in process.
    """
    from .models import Repository, RepositoryTag, ContainerRegistry
    from .utils.registry import (
        get_tags,
        get_catalog,
        get_manifest,
        get_helm_chart_versions,
        is_helm_chart,
    )
    logger.info(
        "Starting repository tags scan for repository %s (latest_only=%s, process_existing=%s)",
        repository_uuid,
        latest_only,
        process_existing,
    )
    
    try:
        repository = Repository.objects.select_related('container_registry').get(uuid=repository_uuid)
        
        # Update status to in_process
        repository.scan_status = 'in_process'
        repository.save()

        # Get registry
        registry = repository.container_registry
        if not registry:
            logger.warning(f"No registry found for repository {repository.name}")
            repository.scan_status = 'error'
            repository.save()
            return

        all_tag_tuples = []  # (tag_name, image_path or None)
        jfrog_new_style = registry.provider == 'jfrog' and repository.repo_key

        if registry.provider == 'jfrog' and jfrog_new_style:
            # ---- Unified per-component repo (repo_key set) ----
            # repo.name = 'repo_key/image_name'; extract image_name
            rk = repository.repo_key
            image_name = repository.name[len(rk) + 1:] if repository.name.startswith(rk + '/') else repository.name

            if repository.repository_type == 'helm':
                try:
                    helm_entries = get_helm_chart_versions(registry, rk)
                except Exception as e:
                    logger.error(f"Failed to get Helm index for {repository.name}: {e}")
                    repository.scan_status = 'error'
                    repository.save()
                    return
                # Filter for this specific chart only
                helm_entries = [(ver, chart) for ver, chart in helm_entries if chart == image_name]
                if latest_only and helm_entries:
                    best_ver = max(helm_entries, key=lambda x: _version_sort_key(x[0]))[0]
                    helm_entries = [(best_ver, image_name)]
                all_tag_tuples = [(ver, None) for ver, _chart in helm_entries]
                logger.info(f"Found {len(all_tag_tuples)} Helm chart versions for {repository.name}" + (" (latest_only)" if latest_only else ""))
            else:
                # Docker: single image within repo key
                try:
                    tags = list(get_tags(registry, rk, limit=100 if not latest_only else 50, image_name=image_name))
                except Exception as e:
                    logger.error(f"Failed to get tags for {repository.name}: {e}")
                    repository.scan_status = 'error'
                    repository.save()
                    return
                if latest_only and tags:
                    chosen = _pick_latest_tag_by_version(tags)
                    tags = [chosen]
                all_tag_tuples = [(t, None) for t in tags]
                logger.info(f"Found {len(all_tag_tuples)} tags for {repository.name}" + (" (latest_only)" if latest_only else ""))
                if all_tag_tuples and repository.repository_type in ('none', 'Unknown'):
                    repository.repository_type = 'docker'
                    repository.save()

        elif registry.provider == 'jfrog':
            # ---- Legacy collection-style repo (no repo_key) ----
            if repository.repository_type == 'helm':
                try:
                    helm_entries = get_helm_chart_versions(registry, repository.name)
                except Exception as e:
                    logger.error(f"Failed to get Helm index for {repository.name}: {e}")
                    repository.scan_status = 'error'
                    repository.save()
                    return
                if latest_only and helm_entries:
                    by_chart = {}
                    for ver, chart in helm_entries:
                        if chart not in by_chart or _version_sort_key(ver) > _version_sort_key(by_chart[chart]):
                            by_chart[chart] = ver
                    helm_entries = [(by_chart[c], c) for c in by_chart]
                all_tag_tuples = [(ver, chart) for ver, chart in helm_entries]
                logger.info(f"Found {len(all_tag_tuples)} Helm chart versions in {repository.name}" + (" (latest_only)" if latest_only else ""))
            else:
                try:
                    image_names, _ = get_catalog(registry, repository.name, page_size=500)
                except Exception as e:
                    logger.error(f"Failed to get catalog for {repository.name}: {e}")
                    repository.scan_status = 'error'
                    repository.save()
                    return
                if latest_only:
                    image_names = image_names[:SCAN_LATEST_ONLY_MAX_IMAGES]
                logger.info(f"Found {len(image_names)} images in Artifactory repo {repository.name}" + (" (latest_only)" if latest_only else ""))
                for img in image_names:
                    try:
                        tags = list(get_tags(registry, repository.name, limit=100 if not latest_only else 50, image_name=img))
                        if latest_only and tags:
                            chosen = _pick_latest_tag_by_version(tags)
                            all_tag_tuples.append((chosen, img))
                        else:
                            for tag_name in tags:
                                all_tag_tuples.append((tag_name, img))
                    except Exception as e:
                        logger.warning(f"Failed to get tags for image {img}: {e}")
                if all_tag_tuples and repository.repository_type in ('none', 'Unknown'):
                    repository.repository_type = 'docker'
                    repository.save()
        else:
            # ACR or single-image: tags for this repository name
            all_tags = list(get_tags(registry, repository.name, limit=500))
            if latest_only and all_tags:
                chosen = _pick_latest_tag_by_version(all_tags)
                all_tags = [chosen]
            all_tag_tuples = [(t, None) for t in all_tags]
            logger.info(f"Found {len(all_tags)} tags for repository {repository.name}" + (" (latest_only)" if latest_only else ""))
            if repository.repository_type in ('none', 'Unknown') and all_tags:
                first_tag = all_tags[0]
                manifest, _ = get_manifest(registry, repository.name, first_tag)
                if manifest:
                    if is_helm_chart(manifest):
                        repository.repository_type = 'helm'
                    else:
                        repository.repository_type = 'docker'
                    repository.save()

        # Process each (tag_name, image_path)
        new_count = 0
        new_tag_uuids = []
        existing_tag_uuids_to_process = []
        existing_tags_already_running = 0
        for tag_name, image_path in all_tag_tuples:
            try:
                image_path_val = (image_path or '').strip()
                existing_tag = RepositoryTag.objects.filter(
                    repository=repository,
                    tag=tag_name,
                    image_path=image_path_val,
                ).only('uuid', 'processing_status').first()
                if existing_tag is None:
                    digest = ''
                    # Native Helm repos (packageType=helm) have no Docker manifest; skip digest
                    if not (repository.repository_type == 'helm' and registry.provider == 'jfrog'):
                        if jfrog_new_style:
                            # Per-component repo: use repo_key + image_name for manifest
                            rk = repository.repo_key
                            img = repository.name[len(rk) + 1:] if repository.name.startswith(rk + '/') else repository.name
                            manifest, d = get_manifest(registry, rk, tag_name, image_name=img)
                            if d:
                                digest = _normalize_image_digest(d)
                        elif registry.provider != 'jfrog' or not image_path_val:
                            manifest, d = get_manifest(registry, repository.name, tag_name)
                            if d:
                                digest = _normalize_image_digest(d)
                        else:
                            manifest, d = get_manifest(registry, repository.name, tag_name, image_name=image_path_val)
                            if d:
                                digest = _normalize_image_digest(d)
                    rt = RepositoryTag.objects.create(
                        repository=repository,
                        tag=tag_name,
                        digest=digest or None,
                        image_path=image_path_val
                    )
                    new_count += 1
                    new_tag_uuids.append(str(rt.uuid))
                    logger.info(f"Created tag {tag_name}" + (f" for image {image_path_val}" if image_path_val else ""))
                elif process_existing:
                    if existing_tag.processing_status in ['pending', 'in_process']:
                        existing_tags_already_running += 1
                    else:
                        existing_tag_uuids_to_process.append(str(existing_tag.uuid))
            except Exception as e:
                logger.error(f"Error processing tag {tag_name}: {str(e)}")
                continue

        # Update repository status
        repository.scan_status = 'success'
        repository.last_scanned = timezone.now()
        repository.save()
        logger.info(f"Successfully completed repository tags scan for {repository.name} ({new_count} new tags)")

        # Schedule processing (create Images, SBOM) for each new tag
        tags_to_process = new_tag_uuids + existing_tag_uuids_to_process
        if tags_to_process:
            from .tasks import process_single_tag
            for tag_uuid in tags_to_process:
                process_single_tag.apply_async(args=[tag_uuid], task_name="Process Single Tag")
            logger.info(
                "Scheduled process_single_tag for %s tags (%s new, %s existing)",
                len(tags_to_process),
                len(new_tag_uuids),
                len(existing_tag_uuids_to_process),
            )
        
        existing_tags_before = RepositoryTag.objects.filter(repository=repository).count() - new_count
        new_tags_created = new_count
        tags_skipped = len(all_tag_tuples) - new_count
        
        return {
            "status": "success",
            "task_name": "Scan Repository Tags",
            "repository_uuid": str(repository_uuid),
            "repository_name": repository.name,
            "repository_url": repository.url,
            "repository_type": repository.repository_type,
            "summary": {
                "total_tags_found": len(all_tag_tuples),
                "new_tags_created": new_tags_created,
                "existing_tags_before": existing_tags_before,
                "tags_skipped": tags_skipped,
                "existing_tags_requeued": len(existing_tag_uuids_to_process),
                "existing_tags_already_running": existing_tags_already_running,
                "tags_scheduled_for_processing": len(tags_to_process),
                "scan_status_updated": True,
                "last_scanned_updated": True
            },
            "registry_info": {
                "provider": registry.provider,
                "api_url": registry.api_url,
                "registry_name": registry.name
            },
            "scan_details": {
                "scan_timestamp": timezone.now().isoformat(),
                "scan_duration": "completed",
                "repository_type_determined": repository.repository_type not in ('none', 'Unknown')
            },
            "message": f"Repository {repository.name} tags scan completed successfully",
            "next_steps": ["Tags are ready for image processing", "Repository scan status updated"],
            "timestamp": timezone.now().isoformat()
        }

    except Repository.DoesNotExist:
        logger.error(f"Repository with UUID {repository_uuid} not found")
        return {
            "status": "error",
            "task_name": "Scan Repository Tags",
            "repository_uuid": str(repository_uuid),
            "error": f"Repository with UUID {repository_uuid} not found",
            "error_type": "RepositoryNotFound",
            "message": "Specified repository does not exist in database",
            "suggestion": "Verify repository UUID and ensure repository exists before scanning",
            "timestamp": timezone.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error scanning repository {repository_uuid}: {str(e)}")
        try:
            repository = Repository.objects.get(uuid=repository_uuid)
            repository.scan_status = 'error'
            repository.save()
        except Exception:
            pass
        return {
            "status": "error",
            "task_name": "Scan Repository Tags",
            "repository_uuid": str(repository_uuid),
            "error": str(e),
            "error_type": type(e).__name__,
            "message": f"Unexpected error occurred during repository tags scan: {str(e)}",
            "suggestion": "Check registry connectivity, authentication credentials, and system resources",
            "details": {
                "scan_status_updated": "error",
                "error_occurred_at": timezone.now().isoformat()
            },
            "timestamp": timezone.now().isoformat()
        }

@celery_app.task(name="Process Single Tag")
def process_single_tag(tag_uuid: str):
    """
    Process a single repository tag and create an image if it doesn't exist.
    After processing, trigger SBOM scan for all images linked to this tag.
    """
    from .models import RepositoryTag
    from .utils.registry import (
        get_manifest,
        is_helm_chart,
        get_chart_digest,
        get_helm_images,
        get_helm_chart_url,
        get_helm_images_from_native_chart,
    )
    from .tasks import generate_sbom_and_create_components

    logger.info(f"Starting processing of tag {tag_uuid}")

    try:
        tag = RepositoryTag.objects.select_related(
            'repository', 'repository__container_registry'
        ).prefetch_related(
            'repository__image_fallback_repositories',
            'repository__image_fallback_repositories__container_registry',
        ).get(uuid=tag_uuid)
        # Set status to in_process
        tag.processing_status = 'in_process'
        tag.save()
        repository = tag.repository
        registry = repository.container_registry
        unresolved_image_refs = []
        logger.info(f"Processing tag {tag.tag} from repository {repository.name}")

        def _helm_processing_error_result(message: str):
            logger.error(
                "Helm image discovery failed for %s:%s: %s",
                repository.name,
                tag.tag,
                message,
            )
            tag.processing_status = 'error'
            tag.save(update_fields=['processing_status', 'updated_at'])
            return {
                "status": "error",
                "task_name": "Process Single Tag",
                "tag_uuid": str(tag_uuid),
                "repository": repository.name,
                "repository_uuid": str(repository.uuid),
                "tag": tag.tag,
                "tag_digest": tag.digest,
                "repository_type": repository.repository_type,
                "error": message,
                "error_type": "HelmImageDiscoveryError",
                "message": f"Failed to discover images for Helm tag {tag.tag}",
                "suggestion": "Provide scan-only Helm values or use the chart fallback extraction path",
                "timestamp": timezone.now().isoformat(),
            }

        # For Docker images, just create the record
        if repository.repository_type == 'docker':
            image_ref = _repository_tag_image_ref(repository, tag, registry)
            image_digest = _resolve_repository_tag_image_digest(
                tag,
                image_ref,
                registry,
            )
            image, created = _get_or_create_canonical_image(
                name=image_ref,
                digest=image_digest,
                artifact_reference=image_ref,
            )
            image.repository_tags.add(tag)
            logger.info(f"{'Created' if created else 'Linked'} Docker image {image_ref}")
        else:
            # For Helm charts: native Helm (Artifactory index.yaml) or OCI manifest (Docker/ACR)
            image_refs = []
            chart_digest = None
            unresolved_image_refs = []
            resolved_image_ids = []

            if repository.repository_type == 'helm' and registry.provider == 'jfrog':
                # Native Helm repo: do not call get_manifest (Helm repos don't expose Docker API).
                if repository.repo_key:
                    rk = repository.repo_key
                    chart_name = repository.name[len(rk) + 1:] if repository.name.startswith(rk + '/') else repository.name
                else:
                    chart_name = (getattr(tag, 'image_path', None) or '').strip()
                helm_repo_key = repository.repo_key or repository.name
                chart_url = get_helm_chart_url(registry, helm_repo_key, chart_name, tag.tag)
                if chart_url:
                    try:
                        image_refs = get_helm_images_from_native_chart(registry, chart_url)
                    except Exception as exc:
                        return _helm_processing_error_result(str(exc))
                else:
                    return _helm_processing_error_result(
                        f"Could not resolve chart URL for {repository.name} {chart_name}@{tag.tag}"
                    )
            else:
                if repository.repo_key:
                    rk = repository.repo_key
                    img_name = repository.name[len(rk) + 1:] if repository.name.startswith(rk + '/') else repository.name
                else:
                    img_name = getattr(tag, 'image_path', None) or None
                repo_for_manifest = repository.repo_key or repository.name
                manifest, digest = get_manifest(registry, repo_for_manifest, tag.tag, image_name=img_name)
                if manifest and is_helm_chart(manifest):
                    chart_digest = get_chart_digest(manifest)
                    if chart_digest:
                        try:
                            image_refs = list(get_helm_images(registry, repository.name, chart_digest))
                        except Exception as exc:
                            return _helm_processing_error_result(str(exc))
                    else:
                        return _helm_processing_error_result(
                            f"Could not extract chart digest for {repository.name}:{tag.tag}"
                        )
                elif not manifest:
                    logger.warning(f"Could not get manifest for {repository.name}:{tag.tag}")
                    tag.processing_status = 'error'
                    tag.save()
                    return
                else:
                    return _helm_processing_error_result(
                        f"Manifest for {repository.name}:{tag.tag} is not recognized as a Helm chart"
                    )

            for image_ref in image_refs:
                resolved_image_ref, image_digest, _resolved_artifact_ref, resolution_error = _resolve_helm_image_location(
                    repository,
                    tag,
                    registry,
                    image_ref,
                )
                if resolution_error:
                    unresolved_image_refs.append(f"{image_ref}: {resolution_error}")
                    logger.error(
                        "Failed Helm image resolution for %s:%s -> %s: %s",
                        repository.name,
                        tag.tag,
                        image_ref,
                        resolution_error,
                    )
                    continue
                artifact_ref = f"{repository.url}:{tag.tag}"
                image, created = _get_or_create_canonical_image(
                    name=resolved_image_ref,
                    digest=image_digest,
                    artifact_reference=artifact_ref,
                )
                resolved_image_ids.append(image.pk)
                logger.info(
                    "%s Helm image %s as %s with digest %s",
                    'Created' if created else 'Linked',
                    image_ref,
                    resolved_image_ref,
                    image_digest,
                )

            _reconcile_helm_tag_images(tag, resolved_image_ids)
            if not resolved_image_ids:
                return _helm_processing_error_result(
                    (
                        f"No resolvable child images found for Helm tag {tag.tag}. "
                        f"Unresolved refs: {', '.join(unresolved_image_refs) or 'none'}"
                    )
                )

            if unresolved_image_refs and not resolved_image_ids:
                return _helm_processing_error_result("; ".join(unresolved_image_refs[:3]))

        # Trigger SBOM scan for all images linked to this tag
        if repository.repository_type == 'helm':
            images = tag.images.filter(pk__in=resolved_image_ids) if resolved_image_ids else tag.images.none()
        else:
            images = tag.images.all()
        started = 0
        repaired_tag_ids = set()
        for image in images:
            if image.scan_status in ['in_process', 'pending'] and _has_completed_image_payload(image):
                image.scan_status = 'success'
                image.save(update_fields=['scan_status', 'updated_at'])
                repaired_tag_ids.update(_propagate_image_completion_to_equivalent_images(image))
                continue
            if image.scan_status == 'in_process':
                continue
            if _has_completed_image_scan(image):
                continue

            image.scan_status = 'pending'
            image.save(update_fields=['scan_status', 'updated_at'])
            repo_tag = image.repository_tags.first()
            art_type = repo_tag.repository.repository_type if repo_tag else 'docker'
            generate_sbom_and_create_components.delay(
                image_uuid=str(image.uuid),
                art_type=art_type
            )
            started += 1
        logger.info(f"Triggered SBOM scan for {started} images for tag {tag.tag}")

        # Calculate summary statistics
        total_images_linked = images.count()
        images_pending_before = images.filter(scan_status='pending').count()
        images_in_process_before = images.filter(scan_status='in_process').count()

        if unresolved_image_refs:
            tag.processing_status = 'error'
            tag.save(update_fields=['processing_status', 'updated_at'])
            return {
                "status": "error",
                "task_name": "Process Single Tag",
                "tag_uuid": str(tag_uuid),
                "repository": repository.name,
                "repository_uuid": str(repository.uuid),
                "tag": tag.tag,
                "tag_digest": tag.digest,
                "repository_type": repository.repository_type,
                "error": "; ".join(unresolved_image_refs[:3]),
                "error_type": "HelmImageResolutionError",
                "summary": {
                    "total_images_linked": total_images_linked,
                    "images_scanned": started,
                    "images_pending_before": images_pending_before,
                    "images_in_process_before": images_in_process_before,
                    "sbom_scans_triggered": started,
                    "tag_processing_status": tag.processing_status,
                },
                "message": f"Helm image resolution failed for one or more images in tag {tag.tag}",
                "timestamp": timezone.now().isoformat(),
            }

        if total_images_linked == 0:
            tag.processing_status = 'success'
            tag.save(update_fields=['processing_status', 'updated_at'])
            try:
                _capture_repository_tag_scan_snapshot(tag.pk)
            except Exception as exc:
                logger.error("Failed to capture empty tag snapshot for %s: %s", tag.pk, exc)
        else:
            synced_statuses = _sync_repository_tag_processing_statuses(
                list({tag.pk, *repaired_tag_ids})
            )
            tag.processing_status = synced_statuses.get(str(tag.pk), tag.processing_status)
        
        return {
            "status": "success",
            "task_name": "Process Single Tag",
            "tag_uuid": str(tag_uuid),
            "repository": tag.repository.name,
            "repository_uuid": str(tag.repository.uuid),
            "tag": tag.tag,
            "tag_digest": tag.digest,
            "repository_type": repository.repository_type,
            "summary": {
                "total_images_linked": total_images_linked,
                "images_scanned": started,
                "images_pending_before": images_pending_before,
                "images_in_process_before": images_in_process_before,
                "sbom_scans_triggered": started,
                "tag_processing_status": tag.processing_status
            },
            "processing_details": {
                "repository_type": repository.repository_type,
                "registry_provider": repository.container_registry.provider if repository.container_registry else None,
                "manifest_processed": repository.repository_type != 'docker',
                "chart_digest_extracted": repository.repository_type == 'helm' and chart_digest is not None
            },
            "sbom_scanning": {
                "scans_triggered": started,
                "art_type_used": repository.repository_type if repository.repository_type != 'none' else 'docker',
                "next_steps": ["SBOM generation in progress", "Component analysis will follow"]
            },
            "message": f"Tag {tag.tag} from repository {repository.name} processed successfully",
            "timestamp": timezone.now().isoformat()
        }

    except RepositoryTag.DoesNotExist:
        logger.error(f"Tag with UUID {tag_uuid} not found")
        return {
            "status": "error",
            "task_name": "Process Single Tag",
            "tag_uuid": str(tag_uuid),
            "error": f"Tag with UUID {tag_uuid} not found",
            "error_type": "TagNotFound",
            "message": "Specified repository tag does not exist in database",
            "suggestion": "Verify tag UUID and ensure tag exists before processing",
            "timestamp": timezone.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error processing tag {tag_uuid}: {str(e)}")
        try:
            tag = RepositoryTag.objects.get(uuid=tag_uuid)
            tag.processing_status = 'error'
            tag.save()
        except Exception:
            pass
        return {
            "status": "error",
            "task_name": "Process Single Tag",
            "tag_uuid": str(tag_uuid),
            "error": str(e),
            "error_type": type(e).__name__,
            "message": f"Unexpected error occurred during tag processing: {str(e)}",
            "suggestion": "Check registry connectivity, authentication credentials, and system resources",
            "details": {
                "processing_status_updated": "error",
                "error_occurred_at": timezone.now().isoformat()
            },
            "timestamp": timezone.now().isoformat()
        }


@celery_app.task(name="Deduplicate Images by Identity")
def deduplicate_images_by_identity():
    """
    Repair historical duplicate Image rows that represent the same logical image.
    Images are considered duplicates when they share the same name and normalized digest.
    """
    from .models import Image

    digest_filter = ~Q(digest__isnull=True) & ~Q(digest='')
    names_with_multiple_images = set(
        Image.objects.filter(digest_filter)
        .values('name')
        .annotate(image_count=Count('uuid'))
        .filter(image_count__gt=1)
        .values_list('name', flat=True)
    )
    names_with_unnormalized_digest = set(
        Image.objects.filter(digest_filter)
        .exclude(digest__startswith='sha256:')
        .values_list('name', flat=True)
    )
    candidate_names = sorted(names_with_multiple_images | names_with_unnormalized_digest)

    summary = {
        'candidate_names_seen': len(candidate_names),
        'duplicate_groups_merged': 0,
        'duplicate_images_deleted': 0,
        'repository_tag_links_merged': 0,
        'component_version_links_merged': 0,
        'component_locations_merged': 0,
        'component_contexts_merged': 0,
        'images_normalized': 0,
    }
    affected_primary_images = []

    for image_name in candidate_names:
        image_rows = list(
            Image.objects.filter(name=image_name)
            .filter(digest_filter)
            .prefetch_related(
                'repository_tags',
                'component_versions',
                'component_locations__component_version',
            )
        )
        grouped_by_digest = {}
        for image in image_rows:
            normalized_digest = _normalize_image_digest(image.digest)
            if not normalized_digest:
                continue
            grouped_by_digest.setdefault(normalized_digest, []).append(image)

        for normalized_digest, grouped_images in grouped_by_digest.items():
            if len(grouped_images) == 1 and grouped_images[0].digest == normalized_digest:
                continue

            with transaction.atomic():
                _acquire_image_identity_lock(image_name, normalized_digest)
                locked_images = list(
                    Image.objects.filter(pk__in=[image.pk for image in grouped_images])
                    .select_for_update()
                    .prefetch_related(
                        'repository_tags',
                        'component_versions',
                        'component_locations__component_version',
                    )
                )
                locked_images = [
                    image for image in locked_images
                    if _normalize_image_digest(image.digest) == normalized_digest
                ]

                if len(locked_images) == 1:
                    image = locked_images[0]
                    if image.digest != normalized_digest:
                        image.digest = normalized_digest
                        image.save(update_fields=['digest', 'updated_at'])
                        summary['images_normalized'] += 1
                    continue

                merge_result = _merge_duplicate_image_group(locked_images, normalized_digest)
                if not merge_result:
                    continue

                affected_primary_images.append(merge_result['primary_image_uuid'])
                for key in (
                    'duplicate_groups_merged',
                    'duplicate_images_deleted',
                    'repository_tag_links_merged',
                    'component_version_links_merged',
                    'component_locations_merged',
                    'component_contexts_merged',
                    'images_normalized',
                ):
                    summary[key] += merge_result[key]

    return {
        "status": "success",
        "task_name": "Deduplicate Images by Identity",
        "summary": summary,
        "details": {
            "affected_primary_images": affected_primary_images,
        },
        "message": (
            f"Image deduplication completed: {summary['duplicate_images_deleted']} duplicate "
            f"images removed across {summary['duplicate_groups_merged']} identity groups"
        ),
        "timestamp": timezone.now().isoformat(),
    }


@celery_app.task(name="Backfill Image Lineage Fields")
def backfill_image_lineage_fields(batch_size: int = 200):
    from django.db.models import Prefetch
    from .models import ComponentVersion, Image

    component_versions_prefetch = Prefetch(
        'component_versions',
        queryset=ComponentVersion.objects.filter(
            component__type__in=['deb', 'rpm', 'apk']
        ).select_related('component'),
    )

    summary = {
        'total_images_seen': 0,
        'images_updated': 0,
        'sbom_distro_images': 0,
        'package_distro_images': 0,
        'unknown_images': 0,
    }

    buffered_ids = []

    def process_batch(image_ids):
        if not image_ids:
            return

        nonlocal summary
        images = list(
            Image.objects.filter(pk__in=image_ids)
            .prefetch_related(component_versions_prefetch)
            .order_by('created_at', 'uuid')
        )
        images_to_update = []
        now = timezone.now()

        for image in images:
            summary['total_images_seen'] += 1
            purls = [component_version.purl for component_version in image.component_versions.all()]
            update_fields = _apply_image_lineage_fields(image, component_version_purls=purls)

            if image.lineage_source == 'sbom_distro':
                summary['sbom_distro_images'] += 1
            elif image.lineage_source == 'package_distro':
                summary['package_distro_images'] += 1
            else:
                summary['unknown_images'] += 1

            if update_fields:
                image.updated_at = now
                images_to_update.append(image)

        if images_to_update:
            Image.objects.bulk_update(
                images_to_update,
                [
                    'lineage_label',
                    'lineage_source',
                    'os_distro_name',
                    'os_distro_version',
                    'lineage_updated_at',
                    'updated_at',
                ],
                batch_size=batch_size,
            )
            summary['images_updated'] += len(images_to_update)

    image_id_iterator = (
        Image.objects.order_by('created_at', 'uuid')
        .values_list('pk', flat=True)
        .iterator(chunk_size=batch_size)
    )

    for image_id in image_id_iterator:
        buffered_ids.append(image_id)
        if len(buffered_ids) >= batch_size:
            process_batch(buffered_ids)
            buffered_ids = []

    if buffered_ids:
        process_batch(buffered_ids)

    return {
        "status": "success",
        "task_name": "Backfill Image Lineage Fields",
        "summary": summary,
        "message": (
            f"Image lineage backfill completed: {summary['images_updated']} images updated "
            f"out of {summary['total_images_seen']} processed"
        ),
        "timestamp": timezone.now().isoformat(),
    }


@celery_app.task(name="Backfill Image SBOM Security Metadata")
def backfill_image_sbom_security_metadata(batch_size: int = 100):
    from django.db.models import Prefetch
    from .models import ComponentVersion, Image

    component_versions_prefetch = Prefetch(
        'component_versions',
        queryset=ComponentVersion.objects.select_related('component'),
    )

    summary = {
        'total_images_seen': 0,
        'images_updated': 0,
        'contexts_created': 0,
        'contexts_updated': 0,
        'contexts_deleted': 0,
        'eol_images': 0,
        'supported_images': 0,
        'unknown_eol_images': 0,
    }

    buffered_ids = []

    def process_batch(image_ids):
        if not image_ids:
            return

        nonlocal summary
        images = list(
            Image.objects.filter(pk__in=image_ids)
            .prefetch_related(component_versions_prefetch)
            .order_by('created_at', 'uuid')
        )
        images_to_update = []
        now = timezone.now()

        for image in images:
            summary['total_images_seen'] += 1

            update_fields = []
            update_fields.extend(_apply_image_lineage_fields(
                image,
                component_version_purls=[component_version.purl for component_version in image.component_versions.all()],
            ))
            update_fields.extend(_apply_image_os_eol_fields(image))

            if image.os_eol_status == 'eol':
                summary['eol_images'] += 1
            elif image.os_eol_status == 'supported':
                summary['supported_images'] += 1
            else:
                summary['unknown_eol_images'] += 1

            if update_fields:
                image.updated_at = now
                images_to_update.append(image)

            context_summary = _upsert_image_component_version_contexts(image)
            summary['contexts_created'] += context_summary['contexts_created']
            summary['contexts_updated'] += context_summary['contexts_updated']
            summary['contexts_deleted'] += context_summary['contexts_deleted']

        if images_to_update:
            Image.objects.bulk_update(
                images_to_update,
                [
                    'lineage_label',
                    'lineage_source',
                    'os_distro_name',
                    'os_distro_version',
                    'lineage_updated_at',
                    'os_eol_status',
                    'os_eol_source',
                    'os_eol_message',
                    'os_eol_checked_at',
                    'updated_at',
                ],
                batch_size=batch_size,
            )
            summary['images_updated'] += len(images_to_update)

    image_id_iterator = (
        Image.objects.order_by('created_at', 'uuid')
        .values_list('pk', flat=True)
        .iterator(chunk_size=batch_size)
    )

    for image_id in image_id_iterator:
        buffered_ids.append(image_id)
        if len(buffered_ids) >= batch_size:
            process_batch(buffered_ids)
            buffered_ids = []

    if buffered_ids:
        process_batch(buffered_ids)

    return {
        "status": "success",
        "task_name": "Backfill Image SBOM Security Metadata",
        "summary": summary,
        "message": (
            "Image SBOM security metadata backfill completed: "
            f"{summary['images_updated']} images updated out of {summary['total_images_seen']} processed"
        ),
        "timestamp": timezone.now().isoformat(),
    }


@celery_app.task(name="Delete Old Repository Tags")
def delete_old_repository_tags(days: int = 1):
    """
    Delete all RepositoryTag objects older than `days` days, along with any
    Image records that become orphaned as a result (i.e. images linked only
    to tags being deleted, not shared with any tag that is kept).
    """
    from django.db.models import Exists, OuterRef
    from .models import RepositoryTag, Image

    cutoff = timezone.now() - timedelta(days=days)
    tag_ids = list(
        RepositoryTag.objects.filter(created_at__lt=cutoff).values_list('pk', flat=True)
    )

    deleted_image_count = 0
    if tag_ids:
        kept_tag_exists = RepositoryTag.objects.filter(images=OuterRef('pk')).exclude(pk__in=tag_ids)
        orphaned_image_ids = list(
            Image.objects.filter(repository_tags__pk__in=tag_ids)
            .annotate(has_kept_tag=Exists(kept_tag_exists))
            .filter(has_kept_tag=False)
            .values_list('pk', flat=True)
            .distinct()
        )
        if orphaned_image_ids:
            deleted_image_count, _ = Image.objects.filter(pk__in=orphaned_image_ids).delete()

    deleted_count = len(tag_ids)
    if tag_ids:
        RepositoryTag.objects.filter(pk__in=tag_ids).delete()

    # Calculate cleanup statistics
    cutoff_date_formatted = cutoff.strftime("%Y-%m-%d")
    space_saved_estimate = deleted_count * 0.1  # Rough estimate: 0.1 KB per tag record

    return {
        "status": "success",
        "task_name": "Delete Old Repository Tags",
        "summary": {
            "deleted_count": deleted_count,
            "deleted_image_count": deleted_image_count,
            "cutoff_days": days,
            "cutoff_date": cutoff_date_formatted,
            "space_saved_kb": round(space_saved_estimate, 2),
            "cleanup_type": "old_repository_tags"
        },
        "message": (
            f"Cleanup completed: {deleted_count} old repository tags removed, "
            f"{deleted_image_count} orphaned images removed"
        ),
        "details": {
            "cutoff_criteria": f"Tags older than {days} days",
            "cutoff_timestamp": cutoff.isoformat(),
            "cleanup_timestamp": timezone.now().isoformat()
        },
        "maintenance": {
            "frequency": "daily",
            "next_recommended_run": (timezone.now() + timedelta(days=1)).isoformat(),
            "note": "This task helps maintain database performance by removing outdated tag records"
        },
        "timestamp": timezone.now().isoformat()
    }

@celery_app.task(name="Update Vulnerability Details")
def update_vulnerability_details(vulnerability_uuid: str):
    """
    Update detailed information for a specific vulnerability.
    This task can be triggered manually or as part of a batch update.
    """
    from .models import Vulnerability, VulnerabilityDetails
    from .utils.vulnerability_sources import collect_vulnerability_data
    from django.utils import timezone
    from django.db import transaction
    import time

    logger.info(f"Starting vulnerability details update for {vulnerability_uuid}")
    start_time = time.time()

    try:
        vulnerability = Vulnerability.objects.get(uuid=vulnerability_uuid)
        if not _is_supported_vulnerability_enrichment_target(
            vulnerability.vulnerability_id,
            vulnerability.vulnerability_type,
        ):
            logger.info(
                f"Skipping vulnerability enrichment for unsupported identifier {vulnerability.vulnerability_id}"
            )
            return {
                "status": "skipped",
                "task_name": "Update Vulnerability Details",
                "vulnerability_id": vulnerability.vulnerability_id,
                "vulnerability_uuid": str(vulnerability_uuid),
                "reason": "unsupported vulnerability identifier",
                "message": f"Vulnerability {vulnerability.vulnerability_id} is not supported by the current enrichment sources",
                "timestamp": timezone.now().isoformat(),
            }
        
        # Skip if already updated recently (within 24 hours)
        try:
            existing_details = vulnerability.details
            if (
                existing_details.last_updated and
                (timezone.now() - existing_details.last_updated) < timedelta(hours=VULNERABILITY_DETAILS_FRESHNESS_HOURS)
            ):
                logger.info(f"Skipping {vulnerability.vulnerability_id} - updated recently")
                return {
                    "status": "skipped",
                    "task_name": "Update Vulnerability Details",
                    "vulnerability_id": vulnerability.vulnerability_id,
                    "vulnerability_uuid": str(vulnerability_uuid),
                    "reason": "updated recently",
                    "message": f"Vulnerability {vulnerability.vulnerability_id} was updated recently (within 24 hours)",
                    "details": {
                        "last_updated": existing_details.last_updated.isoformat() if existing_details.last_updated else None,
                        "hours_since_update": (timezone.now() - existing_details.last_updated).total_seconds() / 3600 if existing_details.last_updated else None
                    },
                    "suggestion": "Skip update as data is still fresh",
                    "timestamp": timezone.now().isoformat()
                }
        except VulnerabilityDetails.DoesNotExist:
            pass  # No existing details, will create new ones

        # Collect data from external sources
        cve_details, exploit_info = collect_vulnerability_data(vulnerability.vulnerability_id)
        now = timezone.now()
        data_sources = _build_vulnerability_data_sources(cve_details, exploit_info)
        
        # Use transaction to ensure atomicity
        with transaction.atomic():
            # Use get_or_create to avoid race conditions
            details, created = VulnerabilityDetails.objects.get_or_create(
                vulnerability=vulnerability,
                defaults={
                    'data_source': 'manual'  # Will be updated below
                }
            )

            # Update CVE details if available
            if cve_details:
                for field, value in cve_details.items():
                    if value is not None and hasattr(details, field):
                        setattr(details, field, value)

            # Update exploit information if available
            if exploit_info:
                for field, value in exploit_info.items():
                    if value is not None and hasattr(details, field):
                        setattr(details, field, value)

            details.data_source = ' + '.join(data_sources) if data_sources else 'manual'

            # Always update the last_updated timestamp
            details.last_updated = now
            details.save()

            if details.epss_score is not None and vulnerability.epss != details.epss_score:
                vulnerability.epss = details.epss_score
                vulnerability.updated_at = now
                vulnerability.save(update_fields=['epss', 'updated_at'])

        processing_time = time.time() - start_time
        logger.info(f"Updated vulnerability details for {vulnerability.vulnerability_id} in {processing_time:.2f}s")

        # Calculate summary statistics
        data_sources_count = len(data_sources) if data_sources else 0
        fields_updated = 0
        if cve_details:
            fields_updated += len([v for v in cve_details.values() if v is not None])
        if exploit_info:
            fields_updated += len([v for v in exploit_info.values() if v is not None])
        
        return {
            "status": "success",
            "task_name": "Update Vulnerability Details",
            "vulnerability_id": vulnerability.vulnerability_id,
            "vulnerability_uuid": str(vulnerability_uuid),
            "vulnerability_severity": vulnerability.severity,
            "summary": {
                "details_created": created,
                "data_sources_used": data_sources_count,
                "fields_updated": fields_updated,
                "cve_details_available": cve_details is not None,
                "exploit_info_available": exploit_info is not None
            },
            "data_sources": data_sources if data_sources else [],
            "processing_time": processing_time,
            "processing_time_formatted": f"{processing_time:.2f} seconds",
            "message": f"Vulnerability {vulnerability.vulnerability_id} details updated successfully",
            "details": {
                "cve_details_fields": list(cve_details.keys()) if cve_details else [],
                "exploit_info_fields": list(exploit_info.keys()) if exploit_info else [],
                "last_updated": details.last_updated.isoformat() if details.last_updated else None
            },
            "timestamp": timezone.now().isoformat()
        }

    except Vulnerability.DoesNotExist:
        logger.error(f"Vulnerability with UUID {vulnerability_uuid} not found")
        return {
            "status": "error",
            "error": f"Vulnerability with UUID {vulnerability_uuid} not found"
        }
    except Exception as e:
        logger.error(f"Error updating vulnerability details for {vulnerability_uuid}: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task(name="Update All Vulnerability Details")
def update_all_vulnerability_details():
    """
    Update detailed information for all vulnerabilities in the database.
    This is a periodic task that should be scheduled to run daily.
    
    Note: This task schedules individual vulnerability updates asynchronously
    to avoid blocking the worker. Use monitor_bulk_update_progress() to check progress.
    """
    from .models import Vulnerability
    from django.core.cache import cache

    logger.info("Starting bulk vulnerability details update")
    start_time = time.time()

    try:
        cutoff_time = timezone.now() - timedelta(hours=VULNERABILITY_DETAILS_FRESHNESS_HOURS)
        vulnerabilities = list(
            Vulnerability.objects.exclude(
                details__last_updated__gte=cutoff_time
            ).only('uuid', 'vulnerability_id', 'vulnerability_type')
        )
        eligible_vulnerabilities = [
            vulnerability for vulnerability in vulnerabilities
            if _is_supported_vulnerability_enrichment_target(
                vulnerability.vulnerability_id,
                vulnerability.vulnerability_type,
            )
        ]
        total_vulnerabilities = len(eligible_vulnerabilities)
        
        logger.info(f"Found {total_vulnerabilities} vulnerabilities to process")

        if not eligible_vulnerabilities:
            return {
                "status": "completed",
                "task_name": "Update All Vulnerability Details",
                "summary": {
                    "total_vulnerabilities": 0,
                    "scheduled_count": 0,
                    "total_batches": 0,
                    "batch_size": ENRICHMENT_BATCH_SIZE,
                },
                "message": "No vulnerabilities require enrichment at the moment",
                "timestamp": timezone.now().isoformat(),
            }

        processed_count = 0
        task_ids = []
        uuid_batches = [
            [str(vulnerability.uuid) for vulnerability in batch]
            for batch in _chunked(eligible_vulnerabilities, ENRICHMENT_BATCH_SIZE)
        ]

        for index, batch in enumerate(uuid_batches, start=1):
            logger.info(f"Scheduling enrichment batch {index}/{len(uuid_batches)} ({len(batch)} vulnerabilities)")
            task = update_vulnerability_details_bulk.apply_async(
                args=[batch],
                kwargs={'batch_size': min(50, len(batch))},
                task_name="Update Vulnerability Details (Bulk)",
            )
            task_ids.append(task.id)
            processed_count += len(batch)

        total_time = time.time() - start_time
        logger.info(f"Bulk vulnerability update scheduling completed in {total_time:.2f}s")
        logger.info(f"Scheduled {len(task_ids)} batch tasks for processing {processed_count} vulnerabilities")
        
        # Store task IDs in cache for monitoring (expires in 24 hours)
        cache_key = f"bulk_update_tasks_{int(start_time)}"
        cache.set(cache_key, {
            'task_ids': task_ids,
            'total_vulnerabilities': total_vulnerabilities,
            'start_time': start_time,
            'status': 'scheduled'
        }, timeout=86400)  # 24 hours

        # Calculate summary statistics
        total_batches = len(uuid_batches)
        estimated_completion_time = total_vulnerabilities * 0.5
        
        return {
            "status": "scheduled",
            "task_name": "Update All Vulnerability Details",
            "summary": {
                "total_vulnerabilities": total_vulnerabilities,
                "scheduled_count": processed_count,
                "total_batches": total_batches,
                "batch_size": ENRICHMENT_BATCH_SIZE,
                "estimated_completion_time_seconds": estimated_completion_time,
                "estimated_completion_time_formatted": f"{estimated_completion_time // 3600}h {(estimated_completion_time % 3600) // 60}m"
            },
            "processing_time": total_time,
            "processing_time_formatted": f"{total_time:.2f} seconds",
            "message": f"Bulk update scheduled: {len(task_ids)} enrichment batches queued for processing",
            "monitor_key": cache_key,
            "monitoring": {
                "cache_expires_in": "24 hours",
                "progress_function": "monitor_bulk_update_progress()",
                "note": "Use monitor_bulk_update_progress() to check progress"
            },
            "next_steps": ["Monitor progress using monitor_bulk_update_progress()", "Batch tasks will update vulnerability details"],
            "timestamp": timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in bulk vulnerability update: {str(e)}")
        return {
            "status": "error",
            "task_name": "Update All Vulnerability Details",
            "error": str(e)
        }


@celery_app.task(name="Update Critical Vulnerability Details")
def update_critical_vulnerability_details():
    """
    Update detailed information for critical and high severity vulnerabilities.
    This task should be scheduled to run more frequently than the full update.
    """
    from .models import Vulnerability
    from django.core.cache import cache
    from django.utils import timezone
    from datetime import timedelta

    logger.info("Starting critical vulnerability details update")
    start_time = time.time()

    try:
        # Get critical and high severity vulnerabilities
        critical_vulns = Vulnerability.objects.filter(
            severity__in=['CRITICAL', 'HIGH']
        )
        
        # Also include vulnerabilities updated more than 7 days ago
        week_ago = timezone.now() - timedelta(days=7)
        old_vulns = Vulnerability.objects.filter(
            details__last_updated__lt=week_ago
        )
        
        # Combine and deduplicate
        vulnerabilities = [
            vulnerability
            for vulnerability in (critical_vulns | old_vulns).distinct().only('uuid', 'vulnerability_id', 'vulnerability_type')
            if _is_supported_vulnerability_enrichment_target(
                vulnerability.vulnerability_id,
                vulnerability.vulnerability_type,
            )
        ]
        total_vulnerabilities = len(vulnerabilities)
        
        logger.info(f"Found {total_vulnerabilities} critical/old vulnerabilities to process")

        if not vulnerabilities:
            return {
                "status": "completed",
                "task_name": "Update Critical Vulnerability Details",
                "message": "No critical or stale supported vulnerabilities need updating",
                "summary": {
                    "total_vulnerabilities": 0,
                    "critical_severity_count": critical_vulns.count(),
                    "old_vulnerabilities_count": old_vulns.count(),
                    "scheduled_count": 0,
                    "total_batches": 0,
                    "batch_size": CRITICAL_ENRICHMENT_BATCH_SIZE,
                },
                "timestamp": timezone.now().isoformat(),
            }

        processed_count = 0
        task_ids = []
        uuid_batches = [
            [str(vulnerability.uuid) for vulnerability in batch]
            for batch in _chunked(vulnerabilities, CRITICAL_ENRICHMENT_BATCH_SIZE)
        ]

        for index, batch in enumerate(uuid_batches, start=1):
            logger.info(f"Scheduling critical enrichment batch {index}/{len(uuid_batches)} ({len(batch)} vulnerabilities)")
            task = update_vulnerability_details_bulk.apply_async(
                args=[batch],
                kwargs={'batch_size': min(25, len(batch))},
                task_name="Update Vulnerability Details (Bulk)",
            )
            task_ids.append(task.id)
            processed_count += len(batch)

        total_time = time.time() - start_time
        logger.info(f"Critical vulnerability update scheduling completed in {total_time:.2f}s")
        
        # Calculate summary statistics
        critical_count = critical_vulns.count()
        old_count = old_vulns.count()
        total_batches = len(uuid_batches)
        estimated_completion_time = total_vulnerabilities * 0.4
        
        # Store task IDs in cache for monitoring (expires in 24 hours)
        cache_key = f"critical_update_tasks_{int(start_time)}"
        cache.set(cache_key, {
            'task_ids': task_ids,
            'total_vulnerabilities': total_vulnerabilities,
            'start_time': start_time,
            'status': 'scheduled'
        }, timeout=86400)  # 24 hours

        return {
            "status": "scheduled",
            "task_name": "Update Critical Vulnerability Details",
            "summary": {
                "total_vulnerabilities": total_vulnerabilities,
                "critical_severity_count": critical_count,
                "old_vulnerabilities_count": old_count,
                "scheduled_count": processed_count,
                "total_batches": total_batches,
                "batch_size": CRITICAL_ENRICHMENT_BATCH_SIZE,
                "estimated_completion_time_seconds": estimated_completion_time,
                "estimated_completion_time_formatted": f"{estimated_completion_time // 3600}h {(estimated_completion_time % 3600) // 60}m"
            },
            "processing_time": total_time,
            "processing_time_formatted": f"{total_time:.2f} seconds",
            "message": f"Critical vulnerability update scheduled: {len(task_ids)} enrichment batches queued for processing",
            "monitor_key": cache_key,
            "monitoring": {
                "cache_expires_in": "24 hours",
                "progress_function": "monitor_bulk_update_progress()",
                "note": "Use monitor_bulk_update_progress() to check progress"
            },
            "priority": "high",
            "next_steps": ["Monitor progress using monitor_bulk_update_progress()", "Critical vulnerabilities will be updated first"],
            "timestamp": timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in critical vulnerability update: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task(name="Cleanup Old Vulnerability Data")
def cleanup_old_vulnerability_data():
    """
    Clean up old vulnerability data and archive outdated information.
    This task should be scheduled to run weekly.
    """
    from .models import VulnerabilityDetails
    from django.utils import timezone
    from datetime import timedelta
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Starting vulnerability data cleanup")

    try:
        # Only delete cached detail records for stale orphaned vulnerabilities.
        cutoff_date = timezone.now() - timedelta(days=90)
        old_details = VulnerabilityDetails.objects.filter(
            last_updated__lt=cutoff_date
        ).annotate(
            linked_components=Count('vulnerability__component_versions', distinct=True)
        ).filter(linked_components=0)
        
        deleted_count = old_details.count()
        old_details.delete()
        
        logger.info(f"Deleted {deleted_count} old vulnerability detail records")
        
        # Calculate cleanup statistics
        cutoff_date_formatted = cutoff_date.strftime("%Y-%m-%d")
        days_threshold = 90
        space_saved_estimate = deleted_count * 0.5  # Rough estimate: 0.5 KB per record
        
        return {
            "status": "completed",
            "task_name": "Cleanup Old Vulnerability Data",
            "summary": {
                "deleted_records": deleted_count,
                "cutoff_date": cutoff_date_formatted,
                "days_threshold": days_threshold,
                "space_saved_kb": round(space_saved_estimate, 2),
                "cleanup_type": "old_orphaned_vulnerability_details"
            },
            "message": f"Cleanup completed: {deleted_count} stale orphaned vulnerability detail records removed",
            "details": {
                "cutoff_criteria": f"Orphaned records older than {days_threshold} days",
                "cutoff_timestamp": cutoff_date.isoformat(),
                "cleanup_timestamp": timezone.now().isoformat()
            },
            "maintenance": {
                "frequency": "weekly",
                "next_recommended_run": (timezone.now() + timedelta(days=7)).isoformat(),
                "note": "This task helps maintain database performance without deleting useful cached enrichment data"
            },
            "timestamp": timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in vulnerability data cleanup: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task(name="Update Vulnerability Details (Bulk)")
def update_vulnerability_details_bulk(vulnerability_uuids: List[str], batch_size: int = 50):
    """
    Bulk update vulnerability details for multiple vulnerabilities.
    
    Args:
        vulnerability_uuids: List of vulnerability UUIDs to update
        batch_size: Number of vulnerabilities to process in each batch
    """
    start_time = time.time()
    
    try:
        from .models import Vulnerability, VulnerabilityDetails
        from .utils.vulnerability_sources import collect_vulnerability_data_bulk

        ordered_uuid_strings = list(dict.fromkeys(str(vulnerability_uuid) for vulnerability_uuid in vulnerability_uuids))
        vulnerabilities_by_uuid = {
            str(vulnerability.uuid): vulnerability
            for vulnerability in Vulnerability.objects.filter(uuid__in=ordered_uuid_strings).only(
                'uuid',
                'vulnerability_id',
                'vulnerability_type',
                'epss',
                'updated_at',
            )
        }
        vulnerabilities = [
            vulnerabilities_by_uuid[uuid_string]
            for uuid_string in ordered_uuid_strings
            if uuid_string in vulnerabilities_by_uuid
        ]
        supported_vulnerabilities = [
            vulnerability for vulnerability in vulnerabilities
            if _is_supported_vulnerability_enrichment_target(
                vulnerability.vulnerability_id,
                vulnerability.vulnerability_type,
            )
        ]
        skipped_count = len(vulnerabilities) - len(supported_vulnerabilities)
        total_count = len(supported_vulnerabilities)
        
        logger.info(f"Starting bulk update for {total_count} vulnerabilities")
        if not supported_vulnerabilities:
            return {
                'status': 'completed',
                'task_name': 'Update Vulnerability Details (Bulk)',
                'summary': {
                    'total_vulnerabilities': 0,
                    'processed_count': 0,
                    'success_count': 0,
                    'error_count': 0,
                    'skipped_count': skipped_count,
                    'success_rate': "0.0%",
                    'error_rate': "0.0%",
                    'total_batches': 0,
                    'batch_size': batch_size
                },
                'processing_time': time.time() - start_time,
                'processing_time_formatted': f"{time.time() - start_time:.2f} seconds",
                'message': 'No supported vulnerability identifiers were supplied for enrichment',
                'timestamp': timezone.now().isoformat()
            }
        
        processed_count = 0
        success_count = 0
        error_count = 0
        
        # Process in batches
        for i in range(0, total_count, batch_size):
            batch_vulnerabilities = supported_vulnerabilities[i:i + batch_size]
            batch_cve_ids = [v.vulnerability_id for v in batch_vulnerabilities]
            
            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch_cve_ids)} vulnerabilities")
            
            try:
                bulk_data = collect_vulnerability_data_bulk(batch_cve_ids)
                batch_vulnerability_ids = [v.pk for v in batch_vulnerabilities]
                details_by_vulnerability_id = {
                    detail.vulnerability_id: detail
                    for detail in VulnerabilityDetails.objects.filter(
                        vulnerability_id__in=batch_vulnerability_ids
                    ).select_related('vulnerability')
                }

                missing_details = [
                    VulnerabilityDetails(vulnerability=vulnerability, data_source='manual')
                    for vulnerability in batch_vulnerabilities
                    if vulnerability.pk not in details_by_vulnerability_id
                ]
                if missing_details:
                    VulnerabilityDetails.objects.bulk_create(
                        missing_details,
                        ignore_conflicts=True,
                    )
                    details_by_vulnerability_id = {
                        detail.vulnerability_id: detail
                        for detail in VulnerabilityDetails.objects.filter(
                            vulnerability_id__in=batch_vulnerability_ids
                        ).select_related('vulnerability')
                    }
                
                # Update database with transaction for atomicity
                with transaction.atomic():
                    details_to_update = []
                    update_fields_set = {'data_source', 'last_updated'}
                    vulnerabilities_to_update = []
                    vulnerability_update_fields = {'epss', 'updated_at'}
                    now = timezone.now()

                    for vulnerability in batch_vulnerabilities:
                        try:
                            cve_details, exploit_info = bulk_data.get(vulnerability.vulnerability_id, (None, None))
                            details = details_by_vulnerability_id.get(vulnerability.pk)
                            if details is None:
                                raise ValueError(
                                    f"Missing VulnerabilityDetails row for {vulnerability.vulnerability_id}"
                                )

                            if cve_details:
                                for field, value in cve_details.items():
                                    if value is not None and hasattr(details, field):
                                        setattr(details, field, value)
                                        update_fields_set.add(field)
                            
                            if exploit_info:
                                for field, value in exploit_info.items():
                                    if value is not None and hasattr(details, field):
                                        setattr(details, field, value)
                                        update_fields_set.add(field)

                            data_sources = _build_vulnerability_data_sources(cve_details, exploit_info)
                            details.data_source = ' + '.join(data_sources) if data_sources else 'manual'
                            details.last_updated = now
                            details_to_update.append(details)

                            if details.epss_score is not None and vulnerability.epss != details.epss_score:
                                vulnerability.epss = details.epss_score
                                vulnerability.updated_at = now
                                vulnerabilities_to_update.append(vulnerability)
                            success_count += 1
                            
                        except Exception as e:
                            logger.error(f"Error updating vulnerability {vulnerability.vulnerability_id}: {str(e)}")
                            error_count += 1

                    if details_to_update:
                        VulnerabilityDetails.objects.bulk_update(
                            details_to_update,
                            list(update_fields_set),
                            batch_size=200
                        )
                    if vulnerabilities_to_update:
                        Vulnerability.objects.bulk_update(
                            vulnerabilities_to_update,
                            list(vulnerability_update_fields),
                            batch_size=200,
                        )
                
                processed_count += len(batch_vulnerabilities)
                
            except Exception as e:
                logger.error(f"Error processing batch {i//batch_size + 1}: {str(e)}")
                error_count += len(batch_vulnerabilities)
                processed_count += len(batch_vulnerabilities)
        
        processing_time = time.time() - start_time
        
        # Calculate summary statistics
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        error_rate = (error_count / total_count * 100) if total_count > 0 else 0
        total_batches = (total_count + batch_size - 1) // batch_size
        
        result = {
            'status': 'completed',
            'task_name': 'Update Vulnerability Details (Bulk)',
            'summary': {
                'total_vulnerabilities': total_count,
                'processed_count': processed_count,
                'success_count': success_count,
                'error_count': error_count,
                'skipped_count': skipped_count,
                'success_rate': f"{success_rate:.1f}%",
                'error_rate': f"{error_rate:.1f}%",
                'total_batches': total_batches,
                'batch_size': batch_size
            },
            'processing_time': processing_time,
            'processing_time_formatted': f"{processing_time:.2f} seconds",
            'message': f"Bulk update completed: {success_count}/{total_count} vulnerabilities updated successfully",
            'performance': {
                'vulnerabilities_per_second': round(total_count / processing_time, 2) if processing_time > 0 else 0,
                'batch_processing_time': round(processing_time / total_batches, 2) if total_batches > 0 else 0
            },
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(f"Bulk update completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error in bulk update: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


@celery_app.task(name="Update Critical Vulnerabilities (Bulk)")
def update_critical_vulnerabilities_bulk():
    """
    Update details for all critical vulnerabilities using bulk processing.
    """
    try:
        # Get critical vulnerabilities that haven't been updated recently
        cutoff_time = timezone.now() - timedelta(hours=24)
        
        critical_vulnerabilities = Vulnerability.objects.filter(
            severity='CRITICAL'
        ).exclude(
            details__last_updated__gte=cutoff_time
        )
        
        vulnerability_uuids = list(critical_vulnerabilities.values_list('uuid', flat=True))
        
        if not vulnerability_uuids:
            logger.info("No critical vulnerabilities need updating")
            return {
                'status': 'completed',
                'task_name': 'Update Critical Vulnerabilities (Bulk)',
                'message': 'No critical vulnerabilities need updating',
                'summary': {
                    'total_vulnerabilities': 0,
                    'critical_vulnerabilities_found': 0,
                    'recently_updated': 'all'
                },
                'details': {
                    'cutoff_time': cutoff_time.isoformat(),
                    'severity_filter': 'CRITICAL',
                    'update_threshold': '24 hours'
                },
                'timestamp': timezone.now().isoformat()
            }
        
        logger.info(f"Found {len(vulnerability_uuids)} critical vulnerabilities to update")
        
        # Use bulk update task
        return update_vulnerability_details_bulk.delay(vulnerability_uuids, batch_size=25)
        
    except Exception as e:
        logger.error(f"Error updating critical vulnerabilities: {str(e)}")
        return {
            'status': 'error',
            'task_name': 'Update Critical Vulnerabilities (Bulk)',
            'error': str(e),
            'error_type': type(e).__name__,
            'message': f'Error occurred while updating critical vulnerabilities: {str(e)}',
            'suggestion': 'Check system resources, database connectivity, and external API availability',
            'priority': 'high',
            'timestamp': timezone.now().isoformat()
        }


@celery_app.task(name="Monitor Task Status")
def monitor_task_status():
    """
    Monitor the status of running vulnerability update tasks.
    This task can be used to check progress and identify stuck tasks.
    """
    from celery.result import GroupResult
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        # Get active tasks from the last hour
        cutoff_time = timezone.now() - timedelta(hours=1)
        
        # This is a placeholder for actual task monitoring
        # In a real implementation, you might want to store task IDs in the database
        # and check their status periodically
        
        logger.info("Task monitoring completed - no active tasks to monitor")
        
        return {
            'status': 'completed',
            'task_name': 'Monitor Task Status',
            'summary': {
                'active_tasks': 0,
                'monitoring_period': '1 hour',
                'cutoff_time': cutoff_time.isoformat()
            },
            'message': 'Task monitoring completed - no active tasks found',
            'details': {
                'monitoring_scope': 'vulnerability update tasks',
                'monitoring_frequency': 'manual',
                'next_recommended_check': (timezone.now() + timedelta(minutes=30)).isoformat()
            },
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in task monitoring: {str(e)}")
        return {
            'status': 'error',
            'task_name': 'Monitor Task Status',
            'error': str(e),
            'error_type': type(e).__name__,
            'message': f'Error occurred during task monitoring: {str(e)}',
            'suggestion': 'Check system resources, database connectivity, and Celery worker status',
            'timestamp': timezone.now().isoformat()
        }


@celery_app.task(name="Monitor Bulk Update Progress")
def monitor_bulk_update_progress(monitor_key: str):
    """
    Monitor the progress of a bulk vulnerability update operation.
    
    Args:
        monitor_key: Cache key returned by update_all_vulnerability_details
    """
    from django.core.cache import cache
    from celery.result import AsyncResult
    import time
    
    try:
        # Get bulk update info from cache
        bulk_info = cache.get(monitor_key)
        if not bulk_info:
            return {
                'status': 'error',
                'error': 'Monitor key not found or expired',
                'monitor_key': monitor_key
            }
        
        task_ids = bulk_info.get('task_ids', [])
        total_vulnerabilities = bulk_info.get('total_vulnerabilities', 0)
        start_time = bulk_info.get('start_time', 0)
        
        if not task_ids:
            return {
                'status': 'completed',
                'message': 'No tasks to monitor',
                'total_vulnerabilities': total_vulnerabilities
            }
        
        # Check status of all tasks
        completed_count = 0
        failed_count = 0
        pending_count = 0
        running_count = 0
        
        for task_id in task_ids:
            result = AsyncResult(task_id)
            if result.ready():
                if result.successful():
                    completed_count += 1
                else:
                    failed_count += 1
            elif result.state == 'PENDING':
                pending_count += 1
            else:
                running_count += 1
        
        # Calculate progress
        total_tasks = len(task_ids)
        progress_percentage = (completed_count / total_tasks * 100) if total_tasks > 0 else 0
        
        # Update cache with current status
        bulk_info['current_status'] = {
            'completed': completed_count,
            'failed': failed_count,
            'pending': pending_count,
            'running': running_count,
            'progress_percentage': progress_percentage
        }
        cache.set(monitor_key, bulk_info, timeout=86400)
        
        elapsed_time = time.time() - start_time
        
        return {
            'status': 'monitoring',
            'task_name': 'Monitor Bulk Update Progress',
            'monitor_key': monitor_key,
            'total_vulnerabilities': total_vulnerabilities,
            'total_tasks': total_tasks,
            'completed_tasks': completed_count,
            'failed_tasks': failed_count,
            'pending_tasks': pending_count,
            'running_tasks': running_count,
            'progress_percentage': round(progress_percentage, 2),
            'elapsed_time_seconds': round(elapsed_time, 2),
            'estimated_completion': 'Use progress_percentage to estimate'
        }
        
    except Exception as e:
        logger.error(f"Error monitoring bulk update progress: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'monitor_key': monitor_key
        }


@celery_app.task(name="Update CISA KEV Vulnerabilities")
def update_cisa_kev_vulnerabilities():
    """
    Update details for vulnerabilities found in CISA KEV catalog.
    """
    try:
        from .utils.vulnerability_sources import VulnerabilityDataCollector
        
        collector = VulnerabilityDataCollector()
        
        all_vulnerabilities = Vulnerability.objects.only('uuid', 'vulnerability_id', 'vulnerability_type')
        cve_vulnerabilities = [
            vulnerability for vulnerability in all_vulnerabilities
            if _is_supported_vulnerability_enrichment_target(
                vulnerability.vulnerability_id,
                vulnerability.vulnerability_type,
            )
        ]
        all_cve_ids = [vulnerability.vulnerability_id for vulnerability in cve_vulnerabilities]

        logger.info(f"Checking {len(all_cve_ids)} vulnerabilities against CISA KEV")
        
        # Check which CVEs are in CISA KEV
        kev_results = collector._check_cisa_kev_bulk(set(all_cve_ids))
        kev_cve_ids = list(kev_results.keys())
        
        if not kev_cve_ids:
            logger.info("No vulnerabilities found in CISA KEV")
            return {
                'status': 'completed',
                'task_name': 'Update CISA KEV Vulnerabilities',
                'message': 'No vulnerabilities found in CISA KEV catalog',
                'summary': {
                    'total_vulnerabilities_checked': len(all_cve_ids),
                    'kev_vulnerabilities_found': 0,
                    'kev_coverage': '0%'
                },
                'details': {
                    'cisa_kev_catalog_checked': True,
                    'cve_ids_processed': len(all_cve_ids),
                    'kev_results': 'empty'
                },
                'timestamp': timezone.now().isoformat()
            }
        
        # Get UUIDs for KEV vulnerabilities
        kev_vulnerabilities = [
            vulnerability for vulnerability in cve_vulnerabilities
            if vulnerability.vulnerability_id in kev_cve_ids
        ]
        vulnerability_uuids = [str(vulnerability.uuid) for vulnerability in kev_vulnerabilities]
        
        logger.info(f"Found {len(vulnerability_uuids)} vulnerabilities in CISA KEV")
        
        # Calculate KEV coverage statistics
        kev_coverage = (len(kev_cve_ids) / len(all_cve_ids) * 100) if all_cve_ids else 0
        
        # Use bulk update task
        return update_vulnerability_details_bulk.delay(vulnerability_uuids, batch_size=25)
        
    except Exception as e:
        logger.error(f"Error updating CISA KEV vulnerabilities: {str(e)}")
        return {
            'status': 'error',
            'task_name': 'Update CISA KEV Vulnerabilities',
            'error': str(e),
            'error_type': type(e).__name__,
            'message': f'Error occurred while checking CISA KEV catalog: {str(e)}',
            'suggestion': 'Check CISA API connectivity, network access, and system resources',
            'priority': 'high',
            'timestamp': timezone.now().isoformat()
        }


def get_vulnerability_statistics() -> Dict:
    """Get statistics about vulnerability details."""
    try:
        total_vulnerabilities = Vulnerability.objects.count()
        vulnerabilities_with_details = VulnerabilityDetails.objects.count()
        
        # Count vulnerabilities with exploits
        vulnerabilities_with_exploits = VulnerabilityDetails.objects.filter(
            exploit_available=True
        ).count()
        
        # Count CISA KEV vulnerabilities
        cisa_kev_vulnerabilities = VulnerabilityDetails.objects.filter(
            cisa_kev_known_exploited=True
        ).count()
        
        # Count ransomware vulnerabilities
        ransomware_vulnerabilities = VulnerabilityDetails.objects.filter(
            cisa_kev_ransomware_use='Known'
        ).count()
        
        return {
            'total_vulnerabilities': total_vulnerabilities,
            'vulnerabilities_with_details': vulnerabilities_with_details,
            'vulnerabilities_with_exploits': vulnerabilities_with_exploits,
            'cisa_kev_vulnerabilities': cisa_kev_vulnerabilities,
            'ransomware_vulnerabilities': ransomware_vulnerabilities,
            'details_percentage': (vulnerabilities_with_details / total_vulnerabilities * 100) if total_vulnerabilities > 0 else 0,
            'exploits_percentage': (vulnerabilities_with_exploits / total_vulnerabilities * 100) if total_vulnerabilities > 0 else 0,
            'kev_percentage': (cisa_kev_vulnerabilities / total_vulnerabilities * 100) if total_vulnerabilities > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting vulnerability statistics: {str(e)}")
        return {}

@celery_app.task(name="Test Task")
def test_task():
    """
    Simple test task for debugging
    """
    import time
    
    time.sleep(2)  # Simulate some work
    
    return {
        'status': 'success',
        'message': 'Test task completed successfully',
        'task_name': 'Test Task'
    }

@celery_app.task(name="Test Failing Task")
def test_failing_task():
    """
    Simple test task that fails
    """
    raise Exception("This is a test failure")

@celery_app.task(name="Performance Monitor")
def performance_monitor():
    """
    Monitor system performance and database query efficiency.
    This task can be scheduled to run periodically.
    """
    from django.db import connection
    from django.db.models import Count
    from .models import Image, Component, Vulnerability, Repository
    import time
    
    start_time = time.time()
    
    try:
        # Get database statistics
        stats = {
            'total_images': Image.objects.count(),
            'total_components': Component.objects.count(),
            'total_vulnerabilities': Vulnerability.objects.count(),
            'total_repositories': Repository.objects.count(),
            'images_with_sbom': Image.objects.filter(sbom_data__isnull=False).exclude(sbom_data={}).count(),
            'images_scanned': Image.objects.filter(scan_status='success').count(),
            'images_in_process': Image.objects.filter(scan_status='in_process').count(),
            'images_with_errors': Image.objects.filter(scan_status='error').count(),
        }
        
        # Check for potential performance issues
        performance_issues = []
        
        # Check for images without SBOM data
        if stats['total_images'] > 0:
            sbom_coverage = (stats['images_with_sbom'] / stats['total_images']) * 100
            if sbom_coverage < 80:
                performance_issues.append(f"Low SBOM coverage: {sbom_coverage:.1f}%")
        
        # Check for stuck processes
        if stats['images_in_process'] > 10:
            performance_issues.append(f"High number of images in process: {stats['images_in_process']}")
        
        # Check for error rate
        if stats['total_images'] > 0:
            error_rate = (stats['images_with_errors'] / stats['total_images']) * 100
            if error_rate > 20:
                performance_issues.append(f"High error rate: {error_rate:.1f}%")
        
        # Database query analysis
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT query, calls, total_time, mean_time
                FROM pg_stat_statements 
                WHERE query LIKE '%core_%'
                ORDER BY total_time DESC 
                LIMIT 5
            """)
            slow_queries = cursor.fetchall()
        
        processing_time = time.time() - start_time
        
        return {
            "status": "success",
            "task_name": "Performance Monitor",
            "statistics": stats,
            "performance_issues": performance_issues,
            "slow_queries": slow_queries,
            "processing_time": processing_time,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error in performance monitoring: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

@celery_app.task(name="Update All Components Latest Versions")
def update_all_components_latest_versions():
    """
    Update latest versions for all component versions in the system.
    This task should be scheduled to run periodically (e.g., monthly).
    
    Restrictions:
    - Skips components updated within the last 30 days
    - Processes in batches of 50 components
    """
    from .models import ComponentVersion
    return _run_bulk_component_latest_version_update(
        ComponentVersion.objects.all(),
        task_name="Update All Components Latest Versions",
        skip_recent_days=30,
        batch_size=50,
    )


@celery_app.task(name="Update Deb Components Latest Versions")
def update_deb_components_latest_versions():
    """
    Update latest versions only for deb packages already stored in the database.
    This is useful when backfilling distro-aware latest-version data.
    """
    from .models import ComponentVersion

    return _run_bulk_component_latest_version_update(
        ComponentVersion.objects.filter(component__type='deb'),
        task_name="Update Deb Components Latest Versions",
        skip_recent_days=30,
        batch_size=50,
    )


@celery_app.task(name="Recalculate Vulnerability Fix Availability")
def recalculate_vulnerability_fix_availability():
    """
    Recalculate fix availability metadata for existing vulnerabilities using stored Grype data.
    This updates current DB rows without rescanning images.
    """
    from .models import Image, ComponentVersionVulnerability

    logger.info("Starting vulnerability fix availability recalculation")
    start_time = time.time()

    images_processed = 0
    images_with_matches = 0
    images_without_grype_matches = 0
    findings_seen = 0
    duplicate_matches_skipped = 0
    unmatched_findings = 0
    cvvs_updated = 0

    try:
        images_qs = Image.objects.filter(grype_data__isnull=False).only('pk', 'uuid', 'grype_data')
        total_images = images_qs.count()

        for image in images_qs.iterator(chunk_size=50):
            images_processed += 1
            grype_data = image.grype_data if isinstance(image.grype_data, dict) else {}
            matches = grype_data.get('matches', [])
            if not isinstance(matches, list) or not matches:
                images_without_grype_matches += 1
                continue

            images_with_matches += 1

            component_names = set()
            component_versions = set()
            vulnerability_ids = set()

            for match in matches:
                artifact = match.get('artifact', {}) if isinstance(match, dict) else {}
                vulnerability_data = match.get('vulnerability', {}) if isinstance(match, dict) else {}
                component_name = artifact.get('name')
                component_version = artifact.get('version')
                vulnerability_id = vulnerability_data.get('id')

                if component_name:
                    component_names.add(component_name)
                if component_name and component_version:
                    component_versions.add(component_version)
                if vulnerability_id:
                    vulnerability_ids.add(vulnerability_id)

            cvv_rows = ComponentVersionVulnerability.objects.filter(
                component_version__images=image,
                component_version__component__name__in=component_names,
                component_version__version__in=component_versions,
                vulnerability__vulnerability_id__in=vulnerability_ids,
            ).select_related('component_version', 'component_version__component', 'vulnerability')

            cvv_map = {
                (
                    cvv.component_version.component.name,
                    cvv.component_version.version,
                    cvv.vulnerability.vulnerability_id,
                ): cvv
                for cvv in cvv_rows
            }

            processed_keys = set()
            cvvs_to_update = []
            update_timestamp = timezone.now()

            for match in matches:
                artifact = match.get('artifact', {}) if isinstance(match, dict) else {}
                vulnerability_data = match.get('vulnerability', {}) if isinstance(match, dict) else {}
                component_name = artifact.get('name')
                component_version = artifact.get('version')
                vulnerability_id = vulnerability_data.get('id')

                if not component_name or not component_version or not vulnerability_id:
                    continue

                findings_seen += 1
                key = (component_name, component_version, vulnerability_id)
                if key in processed_keys:
                    duplicate_matches_skipped += 1
                    continue
                processed_keys.add(key)

                cvv = cvv_map.get(key)
                if not cvv:
                    unmatched_findings += 1
                    continue

                fix_metadata = _determine_fix_metadata(cvv.component_version, vulnerability_data)

                updated = False
                for field_name, field_value in fix_metadata.items():
                    if getattr(cvv, field_name) != field_value:
                        setattr(cvv, field_name, field_value)
                        updated = True

                if updated:
                    cvv.updated_at = update_timestamp
                    cvvs_to_update.append(cvv)

            if cvvs_to_update:
                ComponentVersionVulnerability.objects.bulk_update(
                    cvvs_to_update,
                    ['fixable', 'fix', 'fix_state', 'fix_status', 'fix_versions', 'updated_at'],
                    batch_size=200,
                )
                cvvs_updated += len(cvvs_to_update)

        total_time = time.time() - start_time
        logger.info("Completed vulnerability fix availability recalculation")

        return {
            "status": "success",
            "task_name": "Recalculate Vulnerability Fix Availability",
            "summary": {
                "total_images_seen": total_images,
                "images_processed": images_processed,
                "images_with_grype_matches": images_with_matches,
                "images_without_grype_matches": images_without_grype_matches,
                "findings_seen": findings_seen,
                "duplicate_matches_skipped": duplicate_matches_skipped,
                "unmatched_findings": unmatched_findings,
                "cvvs_updated": cvvs_updated,
            },
            "processing_time": total_time,
        }
    except Exception as e:
        logger.error(f"Error recalculating vulnerability fix availability: {str(e)}")
        return {
            "status": "error",
            "task_name": "Recalculate Vulnerability Fix Availability",
            "error": str(e),
            "error_type": type(e).__name__,
        }


@celery_app.task(name="Cleanup Threat Intel Snapshots")
def cleanup_threat_intel_snapshots(retention_days: int = 90):
    """Delete old persisted threat-intel snapshots."""
    from .utils.threat_intel import cleanup_old_threat_intel_snapshots

    deleted_count = cleanup_old_threat_intel_snapshots(retention_days=retention_days)
    return {
        "status": "success",
        "task_name": "Cleanup Threat Intel Snapshots",
        "summary": {
            "retention_days": retention_days,
            "deleted_snapshots": deleted_count,
        },
        "timestamp": timezone.now().isoformat(),
    }


@celery_app.task(name="Collect Weekly Threat Intel Snapshot")
def collect_weekly_threat_intel_snapshot(retention_days: int = 90, limit: int | None = None):
    """Persist the current weekly threat-intel summary and rotate older snapshots."""
    from .utils.threat_intel import save_weekly_threat_intel_snapshot

    start_time = time.time()
    snapshot = save_weekly_threat_intel_snapshot(limit=limit)
    cleanup_result = cleanup_threat_intel_snapshots(retention_days=retention_days)
    processing_time = time.time() - start_time

    return {
        "status": "success",
        "task_name": "Collect Weekly Threat Intel Snapshot",
        "summary": {
            "snapshot_date": snapshot.snapshot_date.isoformat(),
            "period_start": snapshot.period_start.isoformat(),
            "period_end": snapshot.period_end.isoformat(),
            "retention_days": retention_days,
            "observed_this_week_count": (snapshot.observed_this_week or {}).get("count", 0),
            "kev_added_this_week_count": (snapshot.kev_added_this_week or {}).get("count", 0),
            "supply_chain_this_week_count": (snapshot.supply_chain_this_week or {}).get("count", 0),
            "deleted_snapshots": cleanup_result.get("summary", {}).get("deleted_snapshots", 0),
        },
        "processing_time": processing_time,
        "timestamp": timezone.now().isoformat(),
    }


@celery_app.task(name="Cleanup Root Cause Analytics Snapshots")
def cleanup_root_cause_analytics_snapshots(retention_days: int = 30):
    from .utils.analytics import cleanup_old_root_cause_analytics_snapshots

    cleanup_result = cleanup_old_root_cause_analytics_snapshots(retention_days=retention_days)
    return {
        "status": "success",
        "task_name": "Cleanup Root Cause Analytics Snapshots",
        "summary": {
            "retention_days": retention_days,
            **cleanup_result,
        },
        "timestamp": timezone.now().isoformat(),
    }


@celery_app.task(
    name="Collect Shared Root Cause Analytics Snapshot",
    soft_time_limit=3600,
    time_limit=4200,
)
def collect_shared_root_cause_analytics_snapshot(retention_days: int = 30, batch_size: int = 500):
    from .utils.analytics import save_shared_root_cause_analytics_snapshot

    start_time = time.time()
    snapshot = save_shared_root_cause_analytics_snapshot(batch_size=batch_size)
    processing_time = time.time() - start_time

    return {
        "status": "success",
        "task_name": "Collect Shared Root Cause Analytics Snapshot",
        "summary": {
            "snapshot_date": snapshot.snapshot_date.isoformat(),
            "retention_days": retention_days,
            "shared_root_causes_count": snapshot.total_items,
            "batch_size": batch_size,
        },
        "processing_time": processing_time,
        "timestamp": timezone.now().isoformat(),
    }


@celery_app.task(
    name="Collect Base Lineage Root Cause Analytics Snapshot",
    soft_time_limit=3600,
    time_limit=4200,
)
def collect_base_lineage_root_cause_analytics_snapshot(retention_days: int = 30, batch_size: int = 500):
    from .utils.analytics import save_base_lineage_root_cause_analytics_snapshot

    start_time = time.time()
    snapshot = save_base_lineage_root_cause_analytics_snapshot(batch_size=batch_size)
    processing_time = time.time() - start_time

    return {
        "status": "success",
        "task_name": "Collect Base Lineage Root Cause Analytics Snapshot",
        "summary": {
            "snapshot_date": snapshot.snapshot_date.isoformat(),
            "retention_days": retention_days,
            "base_lineage_root_causes_count": snapshot.total_items,
            "batch_size": batch_size,
        },
        "processing_time": processing_time,
        "timestamp": timezone.now().isoformat(),
    }


@celery_app.task(name="Collect Root Cause Analytics Snapshot")
def collect_root_cause_analytics_snapshot(retention_days: int = 30, batch_size: int = 500):
    shared_result = collect_shared_root_cause_analytics_snapshot.delay(
        retention_days=retention_days,
        batch_size=batch_size,
    )
    base_lineage_result = collect_base_lineage_root_cause_analytics_snapshot.delay(
        retention_days=retention_days,
        batch_size=batch_size,
    )
    cleanup_result = cleanup_root_cause_analytics_snapshots.delay(retention_days=retention_days)

    return {
        "status": "queued",
        "task_name": "Collect Root Cause Analytics Snapshot",
        "summary": {
            "retention_days": retention_days,
            "batch_size": batch_size,
            "shared_task_id": shared_result.id,
            "base_lineage_task_id": base_lineage_result.id,
            "cleanup_task_id": cleanup_result.id,
        },
        "timestamp": timezone.now().isoformat(),
    }
