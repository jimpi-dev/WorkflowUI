import logging
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Depends

from config import get_media_storage_config, get_workflowui_embed_config, update_media_storage_config
from db.maintenance import vacuum_db
from db.migrate import QUICK_RUNS_PROJECT_ID
from services.comfyui_info import (
    get_workflowui_plugin_status,
    get_cached_status,
    set_cached_status,
    fetch_comfyui_status_system_stats,
    COMFYUI_STATUS_TTL_SEC,
)
from version import ENGINE_VERSION

from dependencies import COMFY_URL, get_db, get_run_queue_state
import time

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_db_size_bytes(db_path: str) -> int:
    path = Path(db_path)
    total = path.stat().st_size if path.exists() else 0
    for ext in ("-wal", "-shm"):
        p = Path(str(db_path) + ext)
        if p.exists():
            total += p.stat().st_size
    return total


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
            breakdown["runs"] = table_sizes.get("run", 0)
            breakdown["projects"] = table_sizes.get("project", 0)
            breakdown["presets"] = table_sizes.get("app_preset", 0)
            breakdown["comfyui"] = table_sizes.get("comfyui_version", 0)
        except sqlite3.OperationalError:
            breakdown = {}
            queries = [
                ("workflows", "SELECT COALESCE(SUM(LENGTH(id)+LENGTH(name)+LENGTH(CAST(created_at AS TEXT))), 0) FROM workflow_definition"),
                ("workflows", "SELECT COALESCE(SUM(LENGTH(original_graph_json)+LENGTH(detected_inputs_json)+LENGTH(detected_outputs_json)), 0) FROM workflow_version"),
                ("apps", "SELECT COALESCE(SUM(LENGTH(ui_config_json)+LENGTH(COALESCE(default_inputs_json,''))+LENGTH(COALESCE(default_outputs_json,''))), 0) FROM workflow_app"),
                ("runs", "SELECT COALESCE(SUM(LENGTH(COALESCE(images_json,''))+LENGTH(COALESCE(input_snapshot_json,''))+LENGTH(COALESCE(metadata_snapshot_json,''))), 0) FROM run"),
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
    return {
        "comfyui_url": COMFY_URL,
        "quick_runs_project_id": QUICK_RUNS_PROJECT_ID,
        "engine_version": ENGINE_VERSION,
        "comfyuiDeleteSupported": comfyui_delete_supported,
        "workflowuiPluginAvailable": workflowui_plugin_available,
        "workflowuiPluginIncompatible": workflowui_plugin_incompatible,
        "mediaStorage": {
            "enabled": media_cfg.enabled,
            "rootPath": media_cfg.root_path,
            "deleteRemoteAfterSave": media_cfg.delete_remote_after_save,
        },
        "embedWorkflowuiMetadataOnDownload": embed_cfg.embed_on_download,
        "embedWorkflowuiMetadataOnSave": embed_cfg.embed_on_save,
        "dbSizeBytes": _get_db_size_bytes(db_path),
        "dbBreakdown": _get_db_breakdown(db_path),
    }


@router.get("/version")
def get_version():
    return {"engine_version": ENGINE_VERSION}


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


@router.patch("/admin/media-storage")
def patch_media_storage(body: dict):
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
