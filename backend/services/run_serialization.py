import json
from typing import Any


def safe_json_loads(s: str | None, default: Any = None) -> Any:
    if not s or not s.strip():
        return default
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return default


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
