from typing import Any

from fastapi import APIRouter, HTTPException, Depends

from config import get_media_storage_config, get_workflowui_embed_config, update_media_storage_config
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

router = APIRouter()


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
def get_config():
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
    }


@router.get("/version")
def get_version():
    return {"engine_version": ENGINE_VERSION}


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
