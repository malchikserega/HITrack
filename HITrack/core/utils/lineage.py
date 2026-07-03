from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import parse_qsl, unquote


LINEAGE_SOURCE_SBOM = "sbom_distro"
LINEAGE_SOURCE_PACKAGE = "package_distro"
LINEAGE_SOURCE_UNKNOWN = "unknown"


@dataclass(frozen=True)
class ImageLineage:
    lineage_label: str
    lineage_source: str
    os_distro_name: str | None = None
    os_distro_version: str | None = None


def _clean_string(value) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _normalize_name(value: str | None) -> str | None:
    cleaned = _clean_string(value)
    return cleaned.lower() if cleaned else None


def _normalize_version(value: str | None) -> str | None:
    cleaned = _clean_string(value)
    return cleaned if cleaned else None


def _build_lineage_label(name: str | None, version: str | None) -> str:
    normalized_name = _normalize_name(name)
    normalized_version = _normalize_version(version)
    if normalized_name and normalized_version:
        return f"{normalized_name}-{normalized_version}"
    if normalized_name:
        return normalized_name
    return "unknown"


def _extract_sbom_distro(sbom_data) -> ImageLineage | None:
    if not isinstance(sbom_data, dict):
        return None

    distro = sbom_data.get("distro")
    if not isinstance(distro, dict):
        return None

    distro_name = _normalize_name(distro.get("name"))
    distro_version = _normalize_version(distro.get("version"))
    if not distro_name:
        return None

    return ImageLineage(
        lineage_label=_build_lineage_label(distro_name, distro_version),
        lineage_source=LINEAGE_SOURCE_SBOM,
        os_distro_name=distro_name,
        os_distro_version=distro_version,
    )


def _parse_purl(purl: str) -> dict | None:
    if not purl or not str(purl).startswith("pkg:"):
        return None

    package_reference = str(purl)[4:]
    package_reference, _, _ = package_reference.partition("#")
    package_reference, _, qualifier_string = package_reference.partition("?")
    package_path, _, version = package_reference.partition("@")
    segments = [unquote(segment).strip() for segment in package_path.split("/") if segment.strip()]
    if len(segments) < 2:
        return None

    qualifiers = {
        key.lower(): unquote(value).strip().lower()
        for key, value in parse_qsl(qualifier_string, keep_blank_values=True)
        if key
    }

    return {
        "package_type": segments[0].lower(),
        "namespace": "/".join(segment.lower() for segment in segments[1:-1]) or None,
        "package_name": segments[-1].lower(),
        "version": version,
        "qualifiers": qualifiers,
    }


def _split_package_distro_hint(distro_hint: str | None) -> tuple[str | None, str | None]:
    cleaned = _normalize_name(distro_hint)
    if not cleaned:
        return None, None

    normalized = cleaned.replace(":", "-")
    if normalized.startswith("debian-"):
        return "debian", normalized[len("debian-") :] or None
    if normalized.startswith("ubuntu-"):
        return "ubuntu", normalized[len("ubuntu-") :] or None
    if normalized.startswith("alpine-"):
        return "alpine", normalized[len("alpine-") :] or None
    if normalized.startswith("redhat-"):
        return "redhat", normalized[len("redhat-") :] or None
    if normalized.startswith("rhel-"):
        return "rhel", normalized[len("rhel-") :] or None
    if normalized.startswith("rocky-"):
        return "rocky", normalized[len("rocky-") :] or None

    if "-" in normalized:
        name, version = normalized.rsplit("-", 1)
        if any(char.isdigit() for char in version):
            return name, version

    return normalized, None


def _extract_package_distro_hints(purls: Iterable[str | None]) -> list[str]:
    hints: list[str] = []
    seen: set[str] = set()

    for purl in purls:
        parsed = _parse_purl(purl or "")
        if not parsed:
            continue
        if parsed["package_type"] not in {"deb", "rpm", "apk"}:
            continue

        distro_hint = _normalize_name(parsed["qualifiers"].get("distro"))
        if not distro_hint or distro_hint in seen:
            continue

        seen.add(distro_hint)
        hints.append(distro_hint)

    return hints


def _extract_package_distro_lineage(purls: Iterable[str | None]) -> ImageLineage | None:
    distro_hints = _extract_package_distro_hints(purls)
    if not distro_hints:
        return None

    distro_hint = distro_hints[0]
    distro_name, distro_version = _split_package_distro_hint(distro_hint)

    return ImageLineage(
        lineage_label=_build_lineage_label(distro_name or distro_hint, distro_version),
        lineage_source=LINEAGE_SOURCE_PACKAGE,
        os_distro_name=distro_name or distro_hint,
        os_distro_version=distro_version,
    )


def derive_image_lineage(sbom_data=None, component_version_purls: Iterable[str | None] | None = None) -> ImageLineage:
    component_version_purls = component_version_purls or []

    sbom_lineage = _extract_sbom_distro(sbom_data)
    if sbom_lineage:
        return sbom_lineage

    package_lineage = _extract_package_distro_lineage(component_version_purls)
    if package_lineage:
        return package_lineage

    return ImageLineage(
        lineage_label="unknown",
        lineage_source=LINEAGE_SOURCE_UNKNOWN,
        os_distro_name=None,
        os_distro_version=None,
    )


def image_lineage_to_update_fields(image_lineage: ImageLineage) -> dict:
    return {
        "lineage_label": image_lineage.lineage_label,
        "lineage_source": image_lineage.lineage_source,
        "os_distro_name": image_lineage.os_distro_name,
        "os_distro_version": image_lineage.os_distro_version,
    }
