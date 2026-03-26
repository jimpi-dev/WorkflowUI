import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Depends

from authz import require_user, require_admin
from config import get_media_storage_config, get_workflowui_embed_config, update_media_storage_config
from db.maintenance import vacuum_db
from db.migrate import QUICK_RUNS_PROJECT_ID
from services.comfyui_info import (
    get_workflowui_plugin_status,
    get_cached_status,
    set_cached_status,
    fetch_comfyui_status_system_stats,
    COMFYUI_STATUS_TTL_SEC,
    WORKFLOWUI_PLUGIN_MIN_VERSION,
)
from services.comfyui_workflow_fetch import fetch_workflow_from_comfyui
from version import ENGINE_VERSION

from dependencies import COMFY_URL, get_db, get_run_queue_state
import time

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_user)])


def _get_frontend_version() -> str | None:
    """Read frontend (WorkflowUI) version from frontend/package.json for status bar display."""
    try:
        # backend/routers/config.py -> repo root -> frontend/package.json
        root = Path(__file__).resolve().parent.parent.parent
        pkg_path = root / "frontend" / "package.json"
        if not pkg_path.is_file():
            return None
        raw = pkg_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        version = data.get("version")
        return str(version).strip() if isinstance(version, str) and version else None
    except Exception:
        return None


def _get_db_size_bytes(db_path: str) -> int:
    path = Path(db_path)
    total = 0
    try:
        if path.exists():
            try:
                total += path.stat().st_size
            except FileNotFoundError:
                # DB file disappeared between exists() and stat(); treat as 0 bytes
                pass
        for ext in ("-wal", "-shm"):
            p = Path(str(db_path) + ext)
            if p.exists():
                try:
                    total += p.stat().st_size
                except FileNotFoundError:
                    # SQLite sidecar file was removed between exists() and stat(); ignore
                    continue
    except OSError:
        # Any other OS-level error reading size should not break /config; size remains best-effort.
        return total
    return total


def _get_local_storage_size_bytes(root_path: str) -> int:
    """
    Best-effort total size in bytes for the local media storage root directory.

    This walks the directory tree rooted at ``root_path`` and sums file sizes.
    Any filesystem errors are swallowed so that /config remains robust.
    """
    try:
        path = Path(root_path).expanduser()
        if not path.exists() or not path.is_dir():
            return 0
        total = 0
        for p in path.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except FileNotFoundError:
                # File vanished between discovery and stat; ignore.
                continue
            except OSError:
                # Any other per-file error should not abort the entire walk.
                continue
        return total
    except OSError:
        # Any top-level OS error should not break /config; treat as 0 bytes.
        return 0


def _get_db_breakdown(db_path: str) -> dict[str, int]:
    breakdown: dict[str, int] = {}
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        try:
            page_size = conn.execute("PRAGMA page_size").fetchone()[0]
            cur = conn.execute(
                "SELECT name, COUNT(*) FROM dbstat WHERE name NOT LIKE 'sqlite_%' GROUP BY name"
            )
            table_sizes = {row[0]: row[1] * page_size for row in cur.fetchall()}
            breakdown["workflows"] = (
                table_sizes.get("workflow_definition", 0) + table_sizes.get("workflow_version", 0)
            )
            breakdown["apps"] = table_sizes.get("workflow_app", 0)
            breakdown["runs"] = table_sizes.get("run", 0) + table_sizes.get("generation", 0)
            breakdown["projects"] = table_sizes.get("project", 0)
            breakdown["presets"] = table_sizes.get("app_preset", 0)
            breakdown["comfyui"] = table_sizes.get("comfyui_version", 0)
        except sqlite3.OperationalError:
            breakdown = {}
            queries = [
                ("workflows", "SELECT COALESCE(SUM(LENGTH(id)+LENGTH(name)+LENGTH(CAST(created_at AS TEXT))), 0) FROM workflow_definition"),
                ("workflows", "SELECT COALESCE(SUM(LENGTH(original_graph_json)+LENGTH(detected_inputs_json)+LENGTH(detected_outputs_json)), 0) FROM workflow_version"),
                ("apps", "SELECT COALESCE(SUM(LENGTH(ui_config_json)+LENGTH(COALESCE(default_inputs_json,''))+LENGTH(COALESCE(default_outputs_json,''))), 0) FROM workflow_app"),
                ("runs", "SELECT COALESCE(SUM(LENGTH(COALESCE(images_json,''))+LENGTH(COALESCE(media_json,''))+LENGTH(COALESCE(error,''))+LENGTH(COALESCE(deleted_outputs_json,''))), 0) FROM generation"),
                ("runs", "SELECT COALESCE(SUM(LENGTH(COALESCE(input_snapshot_json,''))+LENGTH(COALESCE(metadata_snapshot_json,''))), 0) FROM run"),
                ("projects", "SELECT COALESCE(SUM(LENGTH(COALESCE(metadata_json,''))+LENGTH(COALESCE(tags_json,''))), 0) FROM project"),
                ("presets", "SELECT COALESCE(SUM(LENGTH(keys_json)+LENGTH(values_json)), 0) FROM app_preset"),
                ("comfyui", "SELECT COALESCE(SUM(LENGTH(metadata_json)), 0) FROM comfyui_version"),
            ]
            for entity, q in queries:
                try:
                    row = conn.execute(q).fetchone()
                    v = row[0] if row else 0
                    breakdown[entity] = breakdown.get(entity, 0) + (v or 0)
                except sqlite3.OperationalError:
                    breakdown[entity] = breakdown.get(entity, 0)
        finally:
            conn.close()
    except Exception:
        pass
    return breakdown


@router.get("/comfyui/status")
def get_comfyui_status(state=Depends(get_run_queue_state)):
    with state.queue_lock:
        running = 1 if state.worker_busy[0] else 0
        pending = len(state.run_queue)
    payload: dict[str, Any] = {
        "queue": {"running": running, "pending": pending},
        "system_stats": None,
    }
    now = time.time()
    cached, expires = get_cached_status(COMFY_URL)
    if cached is not None and now < expires:
        payload["system_stats"] = cached
    else:
        stats = fetch_comfyui_status_system_stats(COMFY_URL)
        set_cached_status(stats, COMFYUI_STATUS_TTL_SEC)
        payload["system_stats"] = stats
    return payload


@router.get("/config")
def get_config(db=Depends(get_db)):
    db_path = db[0]
    media_cfg = get_media_storage_config()
    comfyui_delete_supported, workflowui_plugin_available, workflowui_plugin_incompatible = get_workflowui_plugin_status(COMFY_URL)
    embed_cfg = get_workflowui_embed_config()
    frontend_version = _get_frontend_version()
    # Always report the size of the media storage root folder if it exists,
    # regardless of whether media storage is currently enabled.
    local_storage_size = _get_local_storage_size_bytes(media_cfg.root_path)
    payload: dict[str, Any] = {
        "comfyui_url": COMFY_URL,
        "quick_runs_project_id": QUICK_RUNS_PROJECT_ID,
        "engine_version": ENGINE_VERSION,
        "comfyuiDeleteSupported": comfyui_delete_supported,
        "workflowuiPluginAvailable": workflowui_plugin_available,
        "workflowuiPluginIncompatible": workflowui_plugin_incompatible,
        "workflowuiPluginMinVersion": WORKFLOWUI_PLUGIN_MIN_VERSION,
        "mediaStorage": {
            "enabled": media_cfg.enabled,
            "rootPath": media_cfg.root_path,
            "deleteRemoteAfterSave": media_cfg.delete_remote_after_save,
        },
        "localStorageSizeBytes": local_storage_size,
        "localStorageRootPath": media_cfg.root_path,
        "embedWorkflowuiMetadataOnDownload": embed_cfg.embed_on_download,
        "embedWorkflowuiMetadataOnSave": embed_cfg.embed_on_save,
        "dbSizeBytes": _get_db_size_bytes(db_path),
        "dbBreakdown": _get_db_breakdown(db_path),
    }
    if frontend_version is not None:
        payload["version"] = frontend_version
    return payload


@router.get("/version")
def get_version():
    return {"engine_version": ENGINE_VERSION}

@router.get("/config/diagnostics/run-table")
def get_run_table_diagnostics(db=Depends(get_db)):
    db_path = db[0]
    columns = [
        ("generation", "images_json", False),
        ("generation", "media_json", False),
        ("run", "input_snapshot_json", True),
        ("run", "metadata_snapshot_json", True),
        ("generation", "deleted_outputs_json", False),
        ("generation", "error", False),
    ]
    result: dict[str, Any] = {
        "row_count": 0,
        "columns": {},
        "total_bytes": 0,
    }
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        try:
            row = conn.execute("SELECT COUNT(*) FROM generation").fetchone()
            result["row_count"] = row[0] if row else 0
            total = 0
            for table, col_name, searchable in columns:
                try:
                    row = conn.execute(
                        f"SELECT COALESCE(SUM(LENGTH(COALESCE({col_name}, ''))), 0) FROM {table}"
                    ).fetchone()
                    bytes_val = row[0] if row else 0
                    result["columns"][col_name] = {
                        "bytes": bytes_val,
                        "searchable": searchable,
                    }
                    total += bytes_val
                except sqlite3.OperationalError:
                    result["columns"][col_name] = {"bytes": 0, "searchable": searchable}
            result["total_bytes"] = total
        finally:
            conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


@router.post("/config/vacuum")
def post_vacuum(db=Depends(get_db)):
    db_path = db[0]
    logger.info("DB vacuum triggered")
    size_before = _get_db_size_bytes(db_path)
    vacuum_db(db_path)
    size_after = _get_db_size_bytes(db_path)
    freed = size_before - size_after
    logger.info("DB vacuum ended, freed %d bytes (%.1f MB)", freed, freed / 1_048_576)
    return {"dbSizeBytes": size_after}

def _is_excluded_comfyui_workflow_id(workflow_id: str) -> bool:
    if not workflow_id or not isinstance(workflow_id, str):
        return True
    s = workflow_id.strip()
    if not s:
        return True
    basename = s.replace("\\", "/").split("/")[-1]
    return basename.startswith(".")


@router.get("/comfyui/workflows")
def get_comfyui_workflows():
    """Proxy to ComfyUI WorkflowUI plugin: list workflows available for import."""
    import requests
    base = (COMFY_URL or "").rstrip("/")
    if not base:
        return {"workflows": [], "error": "ComfyUI URL not configured. Set COMFYUI_URL in the backend .env."}
    url = f"{base}/workflowui/workflows"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
    except requests.ConnectionError:
        return {"workflows": [], "error": f"Cannot reach ComfyUI at {base}. Is it running?"}
    except requests.Timeout:
        return {"workflows": [], "error": f"ComfyUI at {base} did not respond in time."}
    except requests.RequestException as e:
        return {"workflows": [], "error": f"ComfyUI request failed: {e!s}"}
    except Exception as e:
        return {"workflows": [], "error": str(e)}
    if isinstance(data, list):
        raw = data
    elif isinstance(data, dict) and "workflows" in data:
        raw = data["workflows"] if isinstance(data["workflows"], list) else []
    else:
        raw = []

    def _get_id(item: Any) -> str:
        if isinstance(item, dict):
            return str(item.get("id") or item.get("label") or "")
        return str(item) if item is not None else ""

    workflows = [w for w in raw if not _is_excluded_comfyui_workflow_id(_get_id(w))]
    return {"workflows": workflows}


@router.get("/comfyui/workflows/{workflow_id}")
def get_comfyui_workflow(workflow_id: str):
    """Fetch a single workflow (name + graph) from ComfyUI plugin for preview/load. Does not create workflow or app."""
    name, graph = fetch_workflow_from_comfyui(COMFY_URL, workflow_id)
    return {"name": name, "graph": graph}

@router.patch("/admin/media-storage")
def patch_media_storage(body: dict, _=Depends(require_admin)):
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Invalid body")
    enabled = body.get("enabled")
    root_path = body.get("rootPath")
    delete_remote = body.get("deleteRemoteAfterSave")
    cfg = update_media_storage_config(
        enabled=bool(enabled) if enabled is not None else None,
        root_path=str(root_path) if root_path is not None else None,
        delete_remote_after_save=bool(delete_remote) if delete_remote is not None else None,
    )
    return {
        "enabled": cfg.enabled,
        "rootPath": cfg.root_path,
        "deleteRemoteAfterSave": cfg.delete_remote_after_save,
    }
