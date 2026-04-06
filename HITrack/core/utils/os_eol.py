from __future__ import annotations

from dataclasses import dataclass


OS_EOL_STATUS_SUPPORTED = 'supported'
OS_EOL_STATUS_EOL = 'eol'
OS_EOL_STATUS_UNKNOWN = 'unknown'

OS_EOL_SOURCE_GRYPE_ALERT = 'grype_alert'
OS_EOL_SOURCE_GRYPE_TRACKED = 'grype_tracked'
OS_EOL_SOURCE_UNKNOWN = 'unknown'

_TRACKED_DISTRO_FAMILIES = {
    'alpine',
    'amazon linux',
    'amazonlinux',
    'almalinux',
    'debian',
    'oracle linux',
    'oraclelinux',
    'red hat enterprise linux',
    'redhat',
    'rhel',
    'sles',
    'suse linux enterprise server',
    'ubuntu',
}


@dataclass(frozen=True)
class ImageOsEolStatus:
    status: str
    source: str
    message: str | None = None


def _clean_string(value) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _normalize_distro_family(os_distro_name: str | None, lineage_label: str | None) -> str | None:
    candidates = [_clean_string(os_distro_name), _clean_string(lineage_label)]
    for candidate in candidates:
        if not candidate:
            continue
        normalized = candidate.lower()
        if normalized.startswith('debian'):
            return 'debian'
        if normalized.startswith('ubuntu'):
            return 'ubuntu'
        if normalized.startswith('alpine'):
            return 'alpine'
        if normalized.startswith('amazon linux') or normalized.startswith('amazonlinux'):
            return 'amazon linux'
        if normalized.startswith('almalinux'):
            return 'almalinux'
        if normalized.startswith('oracle linux') or normalized.startswith('oraclelinux'):
            return 'oracle linux'
        if normalized.startswith('red hat enterprise linux'):
            return 'red hat enterprise linux'
        if normalized.startswith('redhat'):
            return 'redhat'
        if normalized.startswith('rhel'):
            return 'rhel'
        if normalized.startswith('rocky'):
            return 'rocky'
        if normalized.startswith('sles'):
            return 'sles'
        if normalized.startswith('suse linux enterprise server'):
            return 'suse linux enterprise server'
    return None


def _extract_eol_alert(grype_data) -> ImageOsEolStatus | None:
    if not isinstance(grype_data, dict):
        return None

    alerts_by_package = grype_data.get('alertsByPackage') or []
    if not isinstance(alerts_by_package, list):
        return None

    for package_alert in alerts_by_package:
        alerts = package_alert.get('alerts') or []
        if not isinstance(alerts, list):
            continue
        for alert in alerts:
            if (alert or {}).get('type') != 'distro-eol':
                continue
            metadata = (alert or {}).get('metadata') or {}
            distro_name = _clean_string(metadata.get('name'))
            distro_version = _clean_string(metadata.get('version'))
            message = _clean_string(alert.get('message'))
            if not message and distro_name and distro_version:
                message = f'Package is from end-of-life distro: {distro_name} {distro_version}'
            return ImageOsEolStatus(
                status=OS_EOL_STATUS_EOL,
                source=OS_EOL_SOURCE_GRYPE_ALERT,
                message=message,
            )

    return None


def derive_image_os_eol_status(grype_data=None, os_distro_name: str | None = None, lineage_label: str | None = None) -> ImageOsEolStatus:
    eol_alert = _extract_eol_alert(grype_data)
    if eol_alert:
        return eol_alert

    if isinstance(grype_data, dict):
        family = _normalize_distro_family(os_distro_name, lineage_label)
        if family in _TRACKED_DISTRO_FAMILIES:
            return ImageOsEolStatus(
                status=OS_EOL_STATUS_SUPPORTED,
                source=OS_EOL_SOURCE_GRYPE_TRACKED,
                message=None,
            )

    return ImageOsEolStatus(
        status=OS_EOL_STATUS_UNKNOWN,
        source=OS_EOL_SOURCE_UNKNOWN,
        message=None,
    )


def image_os_eol_to_update_fields(image_os_eol: ImageOsEolStatus) -> dict:
    return {
        'os_eol_status': image_os_eol.status,
        'os_eol_source': image_os_eol.source,
        'os_eol_message': image_os_eol.message,
    }
