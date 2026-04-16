import json
import re
from typing import Any
from urllib.parse import quote


def safe_json_loads(s: str | None, default: Any = None) -> Any:
    if not s or not s.strip():
        return default
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return default


def queue_item_summary_from_run(run_entity, input_snapshot_json: str | None) -> dict:
    """Build summary for a queue item: seed, latent_resolution, key_inputs."""
    summary = {}
    if not input_snapshot_json:
        return summary
    try:
        snap = json.loads(input_snapshot_json)
        if not isinstance(snap, dict):
            return summary
        values = snap.get("values") or {}
        bindings = snap.get("bindings") or []
        if not isinstance(values, dict):
            values = {}
        seed = run_entity.seed if getattr(run_entity, "seed", None) is not None else None
        for b in bindings:
            if isinstance(b, dict) and b.get("field") in ("seed", "noise_seed"):
                key = b.get("key")
                if key and key in values:
                    try:
                        seed = int(values[key])
                    except (TypeError, ValueError):
                        pass
                break
        if seed is not None:
            summary["seed"] = seed
        latent = latent_resolution_from_input_snapshot(input_snapshot_json)
        if latent:
            summary["latent_resolution"] = latent
        key_inputs = []
        known_labels = {"steps": "Steps", "cfg": "CFG", "denoising_strength": "Denoise"}
        for b in bindings[:10]:
            if not isinstance(b, dict):
                continue
            key = b.get("key")
            field = b.get("field") or key
            if not key or key not in values:
                continue
            val = values[key]
            if field and ("seed" in str(field).lower() or "noise" in str(field).lower()):
                continue
            label = known_labels.get(field) or (field[:20] + "…" if len(str(field)) > 20 else field)
            key_inputs.append({"label": label, "value": val})
        if key_inputs:
            summary["key_inputs"] = key_inputs[:5]
    except (json.JSONDecodeError, TypeError):
        pass
    return summary


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi"}
_AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}


def _guess_media_type(field: str, key: str, value: Any) -> str | None:
    hay = f"{field} {key}".lower()
    if any(tok in hay for tok in ("image", "img", "photo")):
        return "image"
    if any(tok in hay for tok in ("video", "movie", "clip")):
        return "video"
    if any(tok in hay for tok in ("audio", "sound", "music")):
        return "audio"
    if isinstance(value, str):
        lower = value.lower()
        for ext in _IMAGE_EXTS:
            if lower.endswith(ext):
                return "image"
        for ext in _VIDEO_EXTS:
            if lower.endswith(ext):
                return "video"
        for ext in _AUDIO_EXTS:
            if lower.endswith(ext):
                return "audio"
    return None


def _friendly_label(field: str | None, key: str) -> str:
    source = field or key
    source = source.split(".")[-1]
    source = source.replace("_", " ").strip()
    if not source:
        return key
    return source[:1].upper() + source[1:]


def _value_kind(value: Any) -> str:
    if value is None or value == "":
        return "empty"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return "scalar"


def _display_value(value: Any) -> str:
    if value is None or value == "":
        return "Not provided"
    if isinstance(value, bool):
        return "Enabled" if value else "Disabled"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        clean = re.sub(r"\s+", " ", value).strip()
        return clean if len(clean) <= 120 else clean[:117] + "..."
    if isinstance(value, list):
        if not value:
            return "[]"
        rendered = ", ".join(str(v) for v in value[:4])
        if len(value) > 4:
            rendered += f", +{len(value) - 4} more"
        return rendered
    if isinstance(value, dict):
        keys = list(value.keys())
        if not keys:
            return "{}"
        rendered = ", ".join(str(k) for k in keys[:4])
        if len(keys) > 4:
            rendered += f", +{len(keys) - 4} more"
        return f"{{{rendered}}}"
    return str(value)


def _group_for_value(field: str, key: str, value: Any, media_type: str | None) -> str:
    if media_type:
        return "media"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "numeric"
    if isinstance(value, str):
        return "core" if any(tok in (field + " " + key).lower() for tok in ("seed", "width", "height", "steps", "cfg", "sampler")) else "text"
    if isinstance(value, (list, dict)):
        return "other"
    return "other"


def queue_item_details_from_run(run_entity, input_snapshot_json: str | None) -> dict:
    """Build richer details for queue item inspection UI."""
    empty = {
        "total_inputs": 0,
        "media_count": 0,
        "groups": {"core": [], "text": [], "numeric": [], "boolean": [], "media": [], "other": []},
    }
    if not input_snapshot_json:
        return empty
    try:
        snap = json.loads(input_snapshot_json)
        if not isinstance(snap, dict):
            return empty
        values = snap.get("values") or {}
        bindings = snap.get("bindings") or []
        if not isinstance(values, dict):
            values = {}
        bind_by_key = {}
        for b in bindings:
            if isinstance(b, dict) and isinstance(b.get("key"), str):
                bind_by_key[b["key"]] = b
        groups = {"core": [], "text": [], "numeric": [], "boolean": [], "media": [], "other": []}
        media_count = 0
        for idx, (key, value) in enumerate(values.items()):
            if idx >= 48:
                break
            b = bind_by_key.get(key, {})
            field = str(b.get("field") or key)
            label = _friendly_label(b.get("field"), key)
            media_type = _guess_media_type(field, key, value)
            group = _group_for_value(field, key, value, media_type)
            item = {
                "key": key,
                "label": label,
                "value": value,
                "display_value": _display_value(value),
                "value_kind": _value_kind(value),
                "group": group,
            }
            if media_type:
                media_count += 1
                item["media_type"] = media_type
                if isinstance(value, str) and value.strip():
                    item["preview_url"] = f"/api/runs/{run_entity.id}/input-media?filename={quote(value.strip())}"
            groups[group].append(item)
        return {
            "total_inputs": sum(len(groups[g]) for g in groups),
            "media_count": media_count,
            "groups": groups,
        }
    except (json.JSONDecodeError, TypeError):
        return empty


def latent_resolution_from_input_snapshot(input_snapshot_json: str | None) -> str | None:
    if not input_snapshot_json:
        return None
    try:
        snap = json.loads(input_snapshot_json)
        values = snap.get("values") if isinstance(snap, dict) else None
        if not values or not isinstance(values, dict):
            return None
        w = None
        h = None
        for key, val in values.items():
            if not isinstance(key, str) or not isinstance(val, (int, float)):
                continue
            n = int(val) if isinstance(val, float) and val == int(val) else (val if isinstance(val, int) else None)
            if n is None or n <= 0:
                continue
            if key.endswith(".width") or key.endswith(".width_override"):
                w = n
            if key.endswith(".height") or key.endswith(".height_override"):
                h = n
        if w is not None and h is not None:
            return f"{w}×{h}"
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def run_entity_to_list_item(r, app_repo, status_override=None, error_override=None):
    app_slug = None
    app_title = None
    app_header_color = None
    if r.app_id:
        app = app_repo.get_app_by_id(r.app_id)
        if app:
            app_slug = app.slug
            app_title = app.title
            app_header_color = app.header_color
    return {
        "id": r.id,
        "project_id": r.project_id,
        "workflow_version_id": r.workflow_version_id,
        "app_id": r.app_id,
        "app_slug": app_slug,
        "app_title": app_title,
        "app_header_color": app_header_color,
        "status": status_override if status_override is not None else r.status,
        "created_at": r.created_at,
        "seed": r.seed,
        "images": safe_json_loads(r.images_json, []),
        "execution_time": r.execution_time,
        "error": error_override if error_override is not None else r.error,
        "run_group_id": r.run_group_id,
        "latent_resolution": latent_resolution_from_input_snapshot(r.input_snapshot_json),
        "local_storage_status": r.local_storage_status,
        "remote_status": r.remote_status,
        "local_path": r.local_path,
        "parent_run_id": r.parent_run_id,
        "parent_media_id": r.parent_media_id,
        "root_run_id": r.root_run_id,
    }


def build_updated_runs_response(result: dict, app_repo, run_repo):
    updated_ids = result.get("updated_run_ids")
    if not updated_ids:
        return result
    updated_runs = []
    seen = set()
    for rid in updated_ids:
        if rid in seen:
            continue
        seen.add(rid)
        r = run_repo.get_run(rid)
        if r:
            updated_runs.append(run_entity_to_list_item(r, app_repo))
    result = dict(result)
    result["updated_runs"] = updated_runs
    return result
