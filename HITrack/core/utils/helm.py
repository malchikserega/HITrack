import logging
import os
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

RENDERED_IMAGE_RE = re.compile(
    r'image:\s*["\']?([A-Za-z0-9][A-Za-z0-9./:_-]*(?::[A-Za-z0-9._-]+|@sha256:[a-f0-9]{64}))'
)
VALUES_PATH_RE = re.compile(r"\.Values(?:\.[A-Za-z0-9_-]+)+")
REQUIRED_VALUES_RE = re.compile(
    r'required\s+(?:"[^"]*"|`[^`]*`)\s+(\.Values(?:\.[A-Za-z0-9_-]+)+)'
    r'|(\.Values(?:\.[A-Za-z0-9_-]+)+)\s*\|\s*required'
)


def _helm_template_error_detail(error: BaseException) -> str:
    if isinstance(error, subprocess.CalledProcessError):
        detail = (error.stderr or error.stdout or str(error)).strip()
    else:
        detail = str(error).strip()
    return detail[:4000] if detail else "unknown Helm template error"


def _extract_image_refs_from_text(text: str) -> set[str]:
    return {match.strip().strip("'\"") for match in RENDERED_IMAGE_RE.findall(text or "") if match}


def _extract_values_paths_from_error(detail: str) -> list[list[str]]:
    paths: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for raw_path in VALUES_PATH_RE.findall(detail or ""):
        segments = [segment for segment in raw_path.split(".") if segment and segment != "Values"]
        key = tuple(segments)
        if segments and key not in seen:
            seen.add(key)
            paths.append(segments)
    return paths


def _guess_placeholder_value(path: list[str]) -> Any:
    tail = path[-1].lower() if path else "value"
    full = ".".join(segment.lower() for segment in path)
    if tail in {"enabled", "create", "install"} or full.endswith(".enabled"):
        return False
    if "existingsecret" in full:
        return "hitrack-placeholder-secret"
    if any(token in tail for token in ("secret", "token", "password", "apikey", "api_key", "key")):
        return "hitrack-placeholder"
    if "domain" in tail or "host" in tail:
        return "example.invalid"
    if "url" in tail or "uri" in tail:
        return "https://example.invalid"
    if "port" in tail:
        return 443
    if tail in {"replicas", "replicacount", "count"}:
        return 1
    return "hitrack-placeholder"


def _set_nested_value(target: dict[str, Any], path: list[str], value: Any):
    node = target
    for segment in path[:-1]:
        child = node.get(segment)
        if not isinstance(child, dict):
            child = {}
            node[segment] = child
        node = child
    node[path[-1]] = value


def _run_helm_template(chart_path: str, values_override: dict[str, Any] | None = None) -> str:
    values_file = None
    try:
        cmd = ["helm", "template", "scan", chart_path, "--skip-tests"]
        if values_override:
            values_file = tempfile.NamedTemporaryFile(
                suffix=".yaml",
                delete=False,
                mode="w",
                encoding="utf-8",
            )
            yaml.safe_dump(values_override, values_file, sort_keys=True)
            values_file.flush()
            values_file.close()
            cmd.extend(["-f", values_file.name])
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            text=True,
            timeout=120,
        )
        return result.stdout
    finally:
        if values_file and os.path.exists(values_file.name):
            try:
                os.unlink(values_file.name)
            except OSError:
                pass


def _discover_images_via_helm_template(chart_path: str, chart_ref: str) -> list[str]:
    overrides: dict[str, Any] = {}
    seen_paths: set[tuple[str, ...]] = set()
    last_error = ""
    scanned_templates = False

    for attempt in range(4):
        try:
            rendered = _run_helm_template(chart_path, overrides if overrides else None)
            return sorted(_extract_image_refs_from_text(rendered))
        except (subprocess.SubprocessError, OSError) as error:
            last_error = _helm_template_error_detail(error)
            new_paths = []
            for path in _extract_values_paths_from_error(last_error):
                key = tuple(path)
                if key not in seen_paths:
                    seen_paths.add(key)
                    new_paths.append(path)
            if not new_paths and not scanned_templates:
                scanned_templates = True
                logger.info(
                    "No .Values paths in error output for %s; scanning template sources",
                    chart_ref,
                )
                for path in _extract_values_paths_from_templates(chart_path):
                    key = tuple(path)
                    if key not in seen_paths:
                        seen_paths.add(key)
                        new_paths.append(path)
            if not new_paths:
                raise RuntimeError(f"Helm template failed for {chart_ref}: {last_error}") from error
            for path in new_paths:
                _set_nested_value(overrides, path, _guess_placeholder_value(path))
            logger.warning(
                "Retrying Helm template for %s with %s synthetic value(s) after render failure",
                chart_ref,
                len(new_paths),
            )

    raise RuntimeError(f"Helm template failed for {chart_ref}: {last_error}")


def _looks_like_image_ref(value: str) -> bool:
    if not isinstance(value, str):
        return False
    candidate = value.strip().strip("'\"")
    if not candidate:
        return False
    if candidate.startswith(("http://", "https://")):
        return False
    if "@sha256:" in candidate:
        return True
    if ":" in candidate:
        return True
    if "/" in candidate and "." in candidate.split("/")[0]:
        return True
    return False


def _compose_image_from_mapping(node: dict[str, Any]) -> str | None:
    image_value = node.get("image")
    if isinstance(image_value, str) and _looks_like_image_ref(image_value):
        return image_value.strip().strip("'\"")

    repository = node.get("repository") or node.get("repo")
    registry = node.get("registry") or node.get("imageRegistry")
    tag = node.get("tag")
    digest = node.get("digest")

    if not isinstance(repository, str) or not repository.strip():
        return None

    base = repository.strip().strip("'\"")
    if isinstance(registry, str) and registry.strip():
        registry_value = registry.strip().strip("/").strip("\"'")
        base = f"{registry_value}/{base.lstrip('/')}"

    if isinstance(digest, str) and digest.strip():
        digest_value = digest.strip().strip("'\"")
        if not digest_value.startswith("sha256:"):
            digest_value = f"sha256:{digest_value}"
        return f"{base}@{digest_value}"

    if tag is None:
        if "/" in base or "." in base:
            return base
        return None

    tag_value = str(tag).strip().strip("'\"")
    if not tag_value:
        if "/" in base or "." in base:
            return base
        return None
    return f"{base}:{tag_value}"


def _extract_images_from_values_node(node: Any) -> set[str]:
    images: set[str] = set()
    if isinstance(node, dict):
        candidate = _compose_image_from_mapping(node)
        if candidate and _looks_like_image_ref(candidate):
            images.add(candidate)
        for value in node.values():
            images.update(_extract_images_from_values_node(value))
    elif isinstance(node, list):
        for item in node:
            images.update(_extract_images_from_values_node(item))
    elif isinstance(node, str) and _looks_like_image_ref(node):
        images.add(node.strip().strip("'\""))
    return images


def _safe_extract_chart_archive(chart_path: str, output_dir: str):
    with tarfile.open(chart_path, "r:gz") as archive:
        members = archive.getmembers()
        root = Path(output_dir).resolve()
        for member in members:
            member_path = (root / member.name).resolve()
            if not str(member_path).startswith(str(root)):
                raise RuntimeError(f"Unsafe chart member path: {member.name}")
        archive.extractall(output_dir)


def _extract_values_paths_from_templates(chart_path: str) -> list[list[str]]:
    """Scan template files for .Values paths used in ``required`` calls.

    Only targets paths inside ``required "msg" .Values.xxx`` or
    ``.Values.xxx | required "msg"`` expressions so that we provide
    placeholders solely for values that cause ``required``/``fail``
    errors without overriding real defaults (like image repositories).
    """
    paths: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    with tempfile.TemporaryDirectory() as temp_dir:
        _safe_extract_chart_archive(chart_path, temp_dir)
        for fp in Path(temp_dir).rglob("*"):
            if not fp.is_file():
                continue
            if "/templates/" not in str(fp).replace("\\", "/"):
                continue
            if fp.suffix.lower() not in {".yaml", ".yml", ".tpl"}:
                continue
            try:
                content = fp.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for match in REQUIRED_VALUES_RE.finditer(content):
                raw = match.group(1) or match.group(2)
                if not raw:
                    continue
                segments = [s for s in raw.split(".") if s and s != "Values"]
                key = tuple(segments)
                if segments and key not in seen:
                    seen.add(key)
                    paths.append(segments)
    logger.debug(
        "Template source scan of %s found %d required .Values path(s)",
        chart_path,
        len(paths),
    )
    return paths


def _extract_images_from_chart_archive(chart_path: str) -> list[str]:
    images: set[str] = set()
    files_scanned = 0
    values_files_found = 0
    with tempfile.TemporaryDirectory() as temp_dir:
        _safe_extract_chart_archive(chart_path, temp_dir)
        for file_path in Path(temp_dir).rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in {".yaml", ".yml", ".tpl", ".txt"}:
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            files_scanned += 1
            images.update(_extract_image_refs_from_text(content))
            if file_path.name in {"values.yaml", "values.yml"}:
                values_files_found += 1
                try:
                    parsed = yaml.safe_load(content)
                except yaml.YAMLError:
                    parsed = None
                values_images = _extract_images_from_values_node(parsed)
                logger.debug(
                    "Parsed %s: found %d image ref(s) from values structure",
                    file_path.name,
                    len(values_images),
                )
                images.update(values_images)
    logger.debug(
        "Static chart archive scan: %d files scanned, %d values.yaml found, %d total image ref(s)",
        files_scanned,
        values_files_found,
        len(images),
    )
    return sorted(images)


def extract_images_from_chart_blob(blob: bytes, chart_ref: str) -> list[str]:
    chart_file = None
    render_error = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".tgz", delete=False) as handle:
            handle.write(blob)
            handle.flush()
            chart_file = handle.name

        try:
            rendered_images = _discover_images_via_helm_template(chart_file, chart_ref)
            if rendered_images:
                return rendered_images
            logger.warning(
                "Helm template for %s produced no image references; falling back to static chart extraction",
                chart_ref,
            )
        except RuntimeError as error:
            render_error = str(error)
            logger.warning(
                "Helm template failed for %s; falling back to static chart extraction: %s",
                chart_ref,
                render_error,
            )

        fallback_images = _extract_images_from_chart_archive(chart_file)
        if fallback_images:
            logger.warning(
                "Recovered %s image reference(s) for %s using static chart fallback",
                len(fallback_images),
                chart_ref,
            )
            return fallback_images

        if render_error:
            raise RuntimeError(render_error)
        return []
    finally:
        if chart_file and os.path.exists(chart_file):
            try:
                os.unlink(chart_file)
            except OSError:
                pass
