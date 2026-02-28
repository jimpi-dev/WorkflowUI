from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ParsedManifest:
    manifest_version: str | None
    engine_compat: str | None
    app_version: str | None = None
    workflow_hash: str | None = None
    raw: dict[str, Any] | None = None


def parse_manifest(data: Any) -> ParsedManifest:
    if not isinstance(data, dict):
        return ParsedManifest(manifest_version=None, engine_compat=None, raw=None)
    manifest_version = data.get("manifest_version")
    if isinstance(manifest_version, str):
        manifest_version = manifest_version.strip() or None
    else:
        manifest_version = None
    engine_compat = data.get("engine_compat")
    if isinstance(engine_compat, str):
        engine_compat = engine_compat.strip() or None
    else:
        engine_compat = None
    app_version = data.get("app_version")
    if isinstance(app_version, str):
        app_version = app_version.strip() or None
    else:
        app_version = None
    workflow_hash = data.get("workflow_hash")
    if isinstance(workflow_hash, str):
        workflow_hash = workflow_hash.strip() or None
    else:
        workflow_hash = None
    return ParsedManifest(
        manifest_version=manifest_version,
        engine_compat=engine_compat,
        app_version=app_version,
        workflow_hash=workflow_hash,
        raw=data,
    )


def _parse_semver(version_str: str) -> tuple[int, int, int] | None:
    if not version_str or not isinstance(version_str, str):
        return None
    version_str = version_str.strip()
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-|$)", version_str)
    if not m:
        return None
    try:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except (ValueError, IndexError):
        return None


def _satisfies_engine_compat(engine_compat: str, current_version: str) -> bool:
    current = _parse_semver(current_version)
    if not current:
        return False
    compat = (engine_compat or "").strip()
    if not compat:
        return False
    if compat.startswith("^") or compat.startswith("~"):
        compat = compat[1:].strip()
    required = _parse_semver(compat)
    if not required:
        return False
    if current[0] != required[0]:
        return False
    if current[1] > required[1]:
        return True
    if current[1] < required[1]:
        return False
    return current[2] >= required[2]


def check_engine_compat(parsed: ParsedManifest, current_engine_version: str) -> tuple[bool, str | None]:
    if not parsed.engine_compat:
        return True, None
    if _satisfies_engine_compat(parsed.engine_compat, current_engine_version):
        return True, None
    return False, (
        f"Engine version {current_engine_version} does not satisfy app requirement {parsed.engine_compat}"
    )


def validate_manifest_for_install(parsed: ParsedManifest, current_engine_version: str) -> tuple[bool, str | None]:
    if not parsed.manifest_version:
        return False, "manifest_version is required for app package install"
    if not parsed.engine_compat:
        return False, "engine_compat is required for app package install"
    ok, err = check_engine_compat(parsed, current_engine_version)
    if not ok:
        return False, err or "Engine incompatible"
    return True, None
