import json
import mimetypes
import time
import uuid
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse, FileResponse

from authz import require_user, ensure_project_access, ensure_run_access, user_can_access_app
from db.migrate import QUICK_RUNS_PROJECT_ID
from services.comfyui_info import normalize_comfy_url as _normalize_comfy_url, get_run_remote_storage_bytes
from services.run_queue import (
    queue_run as run_queue_queue_run,
    start_worker as run_queue_start_worker,
    reorder_run as run_queue_reorder_run,
    move_run_to_position as run_queue_move_run_to_position,
    build_job_from_run,
)
from services.media_storage_service import MediaStorageService
from version import ENGINE_VERSION, MANIFEST_SCHEMA_VERSION

from dependencies import (
    COMFY_URL,
    INPUT_DATA_DIR,
    get_db,
    get_media_storage_service,
    get_executor,
    get_run_queue_state,
)
from routers.execution import load_run_output_content_bytes
from services.comfyui_embedded_detect import file_has_embedded_comfyui_metadata
from services.workflowui_embedded_detect import file_has_embedded_workflowui_metadata
from services.run_serialization import (
    build_updated_runs_response,
    queue_item_details_from_run,
    queue_item_summary_from_run,
    safe_json_loads,
)

router = APIRouter(dependencies=[Depends(require_user)])

def _queue_run(job: dict, state, get_db_fn, get_media_fn, auto_start: bool = True):
    executor = get_executor()
    return run_queue_queue_run(
        state.run_queue,
        state.runs,
        state.queue_lock,
        state.worker_busy,
        job,
        COMFY_URL,
        executor,
        get_db_fn,
        get_media_fn,
        processing_halted=state.processing_halted,
        auto_start=auto_start,
    )

@router.post("/run")
def run_workflow_versioned(
    payload: dict,
    db=Depends(get_db),
    state=Depends(get_run_queue_state),
    ctx=Depends(require_user),
):
    _values = payload.get("values") or {}
    _bindings = payload.get("bindings") or []
    _dim_fields = ("width", "height", "width_override", "height_override")
    _dim_bindings = [b for b in _bindings if b.get("field") in _dim_fields]
    _dim_in_values = {k: _values.get(k) for k in _values if any(k.endswith("." + f) for f in _dim_fields)}
    print("[WorkflowUI /run] Incoming payload:", "values_keys=", list(_values.keys()), "bindings_count=", len(_bindings))
    print("[WorkflowUI /run] Dimension bindings:", _dim_bindings)
    print("[WorkflowUI /run] Dimension values in payload:", _dim_in_values)
    _lora_keys = [k for k in _values if ".lora_" in k or k.endswith(".lora") or ".lora." in k]
    _lora_bindings = [b for b in _bindings if b.get("field") and ("lora" in b["field"] or "strength" in b["field"] or b["field"].endswith(".on"))]
    _lora_in_values = {k: _values.get(k) for k in _lora_keys}
    print("[WorkflowUI /run] LoRA bindings:", _lora_bindings)
    print("[WorkflowUI /run] LoRA values in payload:", _lora_in_values)

    project_id = payload.get("project_id")
    app_id = payload.get("app_id")
    workflow_version_id = payload.get("workflow_version_id")
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    if not app_id and not workflow_version_id:
        raise HTTPException(status_code=400, detail="Provide app_id or workflow_version_id")
    _, workflow_repo, app_repo, run_repo, project_repo, _, _ = db
    ensure_project_access(project_id, ctx, project_repo)
    version_id = workflow_version_id
    default_inputs = None
    app = None
    if app_id:
        app = app_repo.get_app_by_id(app_id)
        if not app:
            raise HTTPException(status_code=404, detail="App not found")
        if not user_can_access_app(app.id, ctx):
            raise HTTPException(status_code=404, detail="App not found")
        version_id = app.workflow_version_id
        if app.default_inputs_json:
            default_inputs = json.loads(app.default_inputs_json)
    version = workflow_repo.get_workflow_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Workflow version not found")
    graph = json.loads(version.original_graph_json)
    run_id = payload.get("run_id") or str(uuid.uuid4())
    run_group_id = payload.get("run_group_id") or None
    parent_run_id = payload.get("parent_run_id") or None
    parent_media_id = payload.get("parent_media_id") or None
    root_run_id = run_id
    if parent_run_id:
        if parent_run_id == run_id:
            raise HTTPException(status_code=400, detail="parent_run_id cannot equal run_id")
        parent_run = run_repo.get_run(parent_run_id)
        if not parent_run:
            raise HTTPException(status_code=404, detail="parent_run_id: run not found")
        root_run_id = parent_run.root_run_id or parent_run.id
        if parent_media_id:
            prefix = parent_run_id + ":"
            if not parent_media_id.startswith(prefix) or len(parent_media_id) <= len(prefix):
                raise HTTPException(status_code=400, detail="parent_media_id must be {parent_run_id}:{outputIndex}")
    input_from_run = payload.get("input_from_run")
    if input_from_run and parent_run_id:
        parent_run = run_repo.get_run(parent_run_id)
        if parent_run:
            run_id_src = input_from_run.get("run_id")
            output_index = input_from_run.get("output_index")
            input_key = input_from_run.get("input_key")
            if run_id_src == parent_run_id and output_index is not None and isinstance(input_key, str) and input_key:
                media_list = None
                if parent_run.media_json:
                    try:
                        media_list = json.loads(parent_run.media_json)
                    except json.JSONDecodeError:
                        pass
                if not media_list and parent_run.images_json:
                    try:
                        media_list = json.loads(parent_run.images_json)
                    except json.JSONDecodeError:
                        pass
                if isinstance(media_list, list) and 0 <= output_index < len(media_list):
                    ent = media_list[output_index]
                    if isinstance(ent, dict) and ent.get("file_deleted"):
                        raise HTTPException(status_code=400, detail="Source media file was deleted")
                    filename = ent.get("filename") if isinstance(ent, dict) else None
                    if filename:
                        values = payload.setdefault("values", {})
                        if not isinstance(values, dict):
                            values = {}
                            payload["values"] = values
                        values[input_key] = filename
    created_at = int(time.time() * 1000)
    payload_values = payload.get("values") or {}
    payload_bindings = payload.get("bindings") or []
    default_inputs_applied = default_inputs if isinstance(default_inputs, dict) else {}
    input_snapshot = json.dumps({
        "values": payload_values,
        "bindings": payload_bindings,
        "default_inputs_applied": default_inputs_applied,
    })
    workflow_hash = version.graph_hash if version else None
    app_version_snap = getattr(app, "app_version", "1.0.0") if app else None
    metadata_snapshot = json.dumps({
        "workflow_version_id": version_id,
        "app_id": app_id,
        "created_at": created_at,
        "engine_version": ENGINE_VERSION,
        "manifest_version": MANIFEST_SCHEMA_VERSION,
        "app_version": app_version_snap,
        "workflow_hash": workflow_hash,
    })
    run_comfy_url = _normalize_comfy_url(app.comfyui_url or COMFY_URL) if app else COMFY_URL
    run_repo.create_run(
        run_id,
        project_id,
        version_id,
        app_id,
        "queued",
        created_at,
        queue_position=len(state.run_queue) + 1,
        input_snapshot_json=input_snapshot,
        metadata_snapshot_json=metadata_snapshot,
        run_group_id=run_group_id,
        comfyui_url=run_comfy_url,
        parent_run_id=parent_run_id,
        parent_media_id=parent_media_id,
        root_run_id=root_run_id,
        owner_user_id=ctx.user.id if ctx.user else None,
    )
    project_repo.update_project(project_id, updated_at=created_at)
    job = {
        "run_id": run_id,
        "payload": payload,
        "prompt": graph,
        "default_inputs": default_inputs,
        "comfyui_url": run_comfy_url,
    }
    if input_from_run and parent_run_id:
        job["input_from_run"] = input_from_run
    result = _queue_run(job, state, get_db, get_media_storage_service)
    _persist_queue(state, db[3])
    return result


@router.post("/run/{workflow_id}")
def run_workflow(
    workflow_id: str,
    payload: dict,
    db=Depends(get_db),
    state=Depends(get_run_queue_state),
    ctx=Depends(require_user),
):
    run_id = payload.get("run_id") or str(uuid.uuid4())
    path = Path("workflows") / f"{workflow_id}.json"
    if path.is_file():
        job = {
            "run_id": run_id,
            "workflow_id": workflow_id,
            "payload": payload,
            "comfyui_url": COMFY_URL,
        }
        result = _queue_run(job, state, get_db, get_media_storage_service)
        _persist_queue(state, db[3])
        return result
    _, workflow_repo, app_repo, run_repo, project_repo, _, _ = db
    app = app_repo.get_app_by_slug(workflow_id)
    if app:
        if not user_can_access_app(app.id, ctx):
            raise HTTPException(status_code=404, detail="Workflow not found")
        version = workflow_repo.get_workflow_version(app.workflow_version_id)
        if version:
            graph = json.loads(version.original_graph_json)
            default_inputs = json.loads(app.default_inputs_json) if app.default_inputs_json else None
            created_at = int(time.time() * 1000)
            run_comfy_url = _normalize_comfy_url(app.comfyui_url or COMFY_URL)
            run_repo.create_run(
                run_id,
                QUICK_RUNS_PROJECT_ID,
                version.id,
                app.id,
                "queued",
                created_at,
                queue_position=len(state.run_queue) + 1,
                comfyui_url=run_comfy_url,
                owner_user_id=ctx.user.id if ctx.user else None,
            )
            job = {
                "run_id": run_id,
                "payload": payload,
                "prompt": graph,
                "default_inputs": default_inputs,
                "comfyui_url": run_comfy_url,
            }
            result = _queue_run(job, state, get_db, get_media_storage_service)
            _persist_queue(state, db[3])
            return result
    raise HTTPException(status_code=404, detail="Workflow not found")


@router.get("/run/{run_id}/status")
def get_run_status(run_id: str, db=Depends(get_db), state=Depends(get_run_queue_state), ctx=Depends(require_user)):
    with state.queue_lock:
        r = state.runs.get(run_id)
    run_entity = None
    if r is None:
        run_repo = db[3]
        if run_repo:
            run_entity = ensure_run_access(run_id, ctx, run_repo)
            if run_entity:
                r = {
                    "status": run_entity.status,
                    "queue_position": run_entity.queue_position,
                    "prompt_id": run_entity.prompt_id,
                    "seed": run_entity.seed,
                    "images": json.loads(run_entity.images_json) if run_entity.images_json else [],
                    "execution_time": run_entity.execution_time,
                    "error": run_entity.error,
                }
    else:
        run_repo = db[3]
        run_entity = ensure_run_access(run_id, ctx, run_repo) if run_repo else None
    if r is None:
        return {"status": "not_found"}
    r = r.copy()
    storage = {}
    if run_entity:
        storage = {
            "local_storage_status": run_entity.local_storage_status,
            "remote_status": run_entity.remote_status,
            "local_path": run_entity.local_path,
        }
    if r["status"] == "done":
        return {"status": "done", "images": r.get("images", []), "prompt_id": r.get("prompt_id"), "seed": r.get("seed"), "execution_time": r.get("execution_time"), **storage}
    if r["status"] == "queued":
        return {"status": "queued", "queue_position": r.get("queue_position"), "comfyui_unreachable_warning": r.get("comfyui_unreachable_warning"), **storage}
    if r["status"] == "running":
        return {"status": "running", "prompt_id": r.get("prompt_id"), **storage}
    if r["status"] == "error":
        return {"status": "error", "error": r.get("error", "Unknown error"), **storage}
    if r["status"] == "cancelled":
        return {"status": "cancelled", "error": r.get("error", "Cancelled"), **storage}
    return {"status": r["status"], **storage}


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, db=Depends(get_db), state=Depends(get_run_queue_state), ctx=Depends(require_user)):
    run_repo = db[3]
    ensure_run_access(run_id, ctx, run_repo)
    with state.queue_lock:
        r = state.runs.get(run_id)
        if r is None and run_repo and run_repo.get_run(run_id):
            raise HTTPException(status_code=400, detail="Run is not in the queue")
        if r is None:
            raise HTTPException(status_code=404, detail="Run not found")
        status = r.get("status")
        if status not in ("queued", "running"):
            raise HTTPException(status_code=400, detail=f"Run cannot be cancelled (status: {status})")
        if status == "queued":
            for i, job in enumerate(state.run_queue):
                if job.get("run_id") == run_id:
                    state.run_queue.pop(i)
                    break
            for i, q in enumerate(state.run_queue):
                rid = q["run_id"]
                if rid in state.runs:
                    state.runs[rid]["queue_position"] = i + 1
        state.runs[run_id]["status"] = "cancelled"
        state.runs[run_id]["error"] = "Cancelled"
        comfy_url = (r.get("comfyui_url") or COMFY_URL).rstrip("/") if status == "running" else None
    if comfy_url:
        try:
            requests.post(f"{comfy_url}/interrupt", timeout=5)
        except Exception as e:
            print("ComfyUI interrupt request failed:", e)
    if run_repo and run_repo.get_run(run_id):
        run_repo.update_run(run_id, status="cancelled", error="Cancelled")
    _persist_queue(state, run_repo)
    return {"ok": True, "status": "cancelled"}


@router.post("/runs/{run_id}/retry")
def retry_run(run_id: str, state=Depends(get_run_queue_state)):
    with state.queue_lock:
        r = state.runs.get(run_id)
        if r is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if r.get("status") != "queued":
            raise HTTPException(status_code=400, detail=f"Run is not queued (status: {r.get('status')}); only queued runs can be retried.")
        job_index = None
        for i, job in enumerate(state.run_queue):
            if job.get("run_id") == run_id:
                job_index = i
                break
        if job_index is None:
            raise HTTPException(status_code=400, detail="Run is not in the queue.")
        job = state.run_queue.pop(job_index)
        state.run_queue.insert(0, job)
        state.runs[run_id].pop("comfyui_unreachable_warning", None)
        for i, q in enumerate(state.run_queue):
            rid = q["run_id"]
            if rid in state.runs:
                state.runs[rid]["queue_position"] = i + 1
    executor = get_executor()
    run_queue_start_worker(
        state.run_queue, state.runs, state.queue_lock, state.worker_busy,
        state.processing_halted, executor, get_db, get_media_storage_service,
    )
    return {"ok": True, "status": "queued", "queue_position": 1}


@router.post("/runs/{run_id}/reorder")
def reorder_run(run_id: str, body: dict, db=Depends(get_db), state=Depends(get_run_queue_state)):
    direction = body.get("direction")
    if direction not in ("up", "down"):
        raise HTTPException(status_code=400, detail="direction must be 'up' or 'down'")
    with state.queue_lock:
        r = state.runs.get(run_id)
        if not r or r.get("status") != "queued":
            raise HTTPException(status_code=400, detail="Run is not queued")
    new_pos = run_queue_reorder_run(
        state.run_queue, state.runs, state.queue_lock, run_id, direction,
    )
    if new_pos is None:
        raise HTTPException(status_code=400, detail="Could not reorder")
    _persist_queue(state, db[3])
    return {"ok": True, "queue_position": new_pos}


@router.post("/runs/{run_id}/move")
def move_run(run_id: str, body: dict, db=Depends(get_db), state=Depends(get_run_queue_state)):
    position = body.get("position")
    if position is None or not isinstance(position, (int, float)):
        raise HTTPException(status_code=400, detail="position (1-based) required")
    pos = int(position)
    with state.queue_lock:
        r = state.runs.get(run_id)
        if not r or r.get("status") != "queued":
            raise HTTPException(status_code=400, detail="Run is not queued")
    new_pos = run_queue_move_run_to_position(
        state.run_queue, state.runs, state.queue_lock, run_id, pos,
    )
    if new_pos is None:
        raise HTTPException(status_code=400, detail="Could not move run")
    _persist_queue(state, db[3])
    return {"ok": True, "queue_position": new_pos}


def _queue_item(run_id: str, run_entity, app_repo, project_repo, mem_run: dict | None) -> dict:
    app_title = app_slug = app_header_color = None
    if run_entity and run_entity.app_id and app_repo:
        app = app_repo.get_app_by_id(run_entity.app_id)
        if app:
            app_title, app_slug = app.title, app.slug
            app_header_color = getattr(app, "header_color", None)
    project_title = None
    if run_entity and run_entity.project_id and project_repo:
        proj = project_repo.get_project(run_entity.project_id)
        if proj:
            project_title = getattr(proj, "name", None)
    status = (mem_run or {}).get("status") or (run_entity.status if run_entity else "queued")
    out = {
        "run_id": run_id,
        "run_group_id": getattr(run_entity, "run_group_id", None) if run_entity else None,
        "status": status,
        "queue_position": (mem_run or {}).get("queue_position"),
        "app_title": app_title,
        "app_slug": app_slug,
        "app_header_color": app_header_color,
        "project_id": run_entity.project_id if run_entity else None,
        "project_title": project_title,
        "created_at": run_entity.created_at if run_entity else None,
        "comfyui_unreachable_warning": (mem_run or {}).get("comfyui_unreachable_warning"),
    }
    if run_entity:
        out["summary"] = queue_item_summary_from_run(run_entity, run_entity.input_snapshot_json)
        out["details"] = queue_item_details_from_run(run_entity, run_entity.input_snapshot_json)
    else:
        out["summary"] = {}
        out["details"] = {
            "total_inputs": 0,
            "media_count": 0,
            "groups": {"core": [], "text": [], "numeric": [], "boolean": [], "media": [], "other": []},
        }
    return out


def _persist_queue(state, run_repo) -> None:
    """Write current queue (running + queued run_ids) to saved_queue so it restores on next load."""
    if not run_repo or not hasattr(run_repo, "set_saved_queue"):
        return
    with state.queue_lock:
        running_id = None
        for rid, r in state.runs.items():
            if r.get("status") == "running":
                running_id = rid
                break
        run_ids = ([running_id] if running_id else []) + [j.get("run_id") for j in state.run_queue if j.get("run_id")]
    try:
        run_repo.set_saved_queue(run_ids)
    except Exception:
        pass


def _restore_queue_from_saved(state, get_db_fn, run_repo) -> bool:
    """If in-memory queue is empty and saved_queue has items, restore them. Returns True if restored."""
    if not run_repo or not hasattr(run_repo, "get_saved_queue"):
        return False
    with state.queue_lock:
        if state.run_queue or any(r.get("status") == "running" for r in state.runs.values()):
            return False
        sq = run_repo.get_saved_queue()
        if not sq or not sq[0]:
            return False
        run_ids = sq[0]
    state.processing_halted[0] = True
    for run_id in run_ids:
        run_entity = run_repo.get_run(run_id) if run_repo else None
        if not run_entity or run_entity.status not in ("queued", "cancelled"):
            continue
        job = build_job_from_run(run_entity, get_db_fn)
        if not job:
            continue
        run_queue_queue_run(
            state.run_queue,
            state.runs,
            state.queue_lock,
            state.worker_busy,
            job,
            COMFY_URL,
            get_executor(),
            get_db_fn,
            get_media_storage_service,
            processing_halted=state.processing_halted,
            auto_start=False,
        )
    return True


@router.get("/queue")
def get_queue(db=Depends(get_db), state=Depends(get_run_queue_state), ctx=Depends(require_user)):
    _, _, app_repo, run_repo, project_repo, _, _ = db
    try:
        _restore_queue_from_saved(state, get_db, run_repo)
    except Exception:
        pass
    with state.queue_lock:
        running_id = None
        for rid, r in state.runs.items():
            if r.get("status") == "running":
                running_id = rid
                break
        queued_ids = [j.get("run_id") for j in state.run_queue if j.get("run_id")]
        mem = {rid: state.runs.get(rid, {}) for rid in ([running_id] if running_id else []) + queued_ids}
        processing_halted = state.processing_halted[0] if state.processing_halted else False
    running_item = None
    if running_id:
        run_entity = run_repo.get_run(running_id) if run_repo else None
        if run_entity and ((ctx.auth_enabled and ctx.user and run_entity.owner_user_id != ctx.user.id) or (not ctx.auth_enabled and run_entity.owner_user_id is not None)):
            run_entity = None
        running_item = _queue_item(running_id, run_entity, app_repo, project_repo, mem.get(running_id))
    queued = []
    for run_id in queued_ids:
        run_entity = run_repo.get_run(run_id) if run_repo else None
        if run_entity and ((ctx.auth_enabled and ctx.user and run_entity.owner_user_id != ctx.user.id) or (not ctx.auth_enabled and run_entity.owner_user_id is not None)):
            continue
        queued.append(_queue_item(run_id, run_entity, app_repo, project_repo, mem.get(run_id)))
    _persist_queue(state, run_repo)
    return {
        "running": running_item,
        "queued": queued,
        "processing_halted": processing_halted,
    }


@router.post("/queue/pause")
def pause_queue(state=Depends(get_run_queue_state)):
    state.processing_halted[0] = True
    # Interrupt the current run on ComfyUI so nothing keeps processing
    with state.queue_lock:
        running_id = None
        comfy_url = None
        for rid, r in state.runs.items():
            if r.get("status") == "running":
                running_id = rid
                comfy_url = (r.get("comfyui_url") or COMFY_URL).rstrip("/")
                break
    if comfy_url:
        try:
            requests.post(f"{comfy_url}/interrupt", timeout=5)
        except Exception as e:
            print("ComfyUI interrupt on pause failed:", e)
    return {"ok": True, "processing_halted": True}


@router.post("/queue/start")
def start_queue(state=Depends(get_run_queue_state)):
    state.processing_halted[0] = False
    run_queue_start_worker(
        state.run_queue, state.runs, state.queue_lock, state.worker_busy,
        state.processing_halted, get_executor(), get_db, get_media_storage_service,
    )
    return {"ok": True, "processing_halted": False}


@router.get("/runs/{run_id}")
def get_run_detail(run_id: str, db=Depends(get_db), service: MediaStorageService = Depends(get_media_storage_service), ctx=Depends(require_user)):
    _, _, app_repo, run_repo, _, _, _ = db
    run_entity = ensure_run_access(run_id, ctx, run_repo)
    parent_app_title = None
    if run_entity.parent_run_id and app_repo:
        parent_run = run_repo.get_run(run_entity.parent_run_id)
        if parent_run and parent_run.app_id:
            parent_app = app_repo.get_app_by_id(parent_run.app_id)
            if parent_app:
                parent_app_title = parent_app.title
    local_storage_bytes = None
    if run_entity.local_storage_status in ("saved", "partial"):
        local_storage_bytes = service.get_run_local_storage_bytes(run_entity)
    remote_storage_bytes = None
    run_images = json.loads(run_entity.images_json) if run_entity.images_json else []
    if run_images:
        comfy_url = run_entity.comfyui_url
        if not comfy_url and run_entity.app_id and app_repo:
            app = app_repo.get_app_by_id(run_entity.app_id)
            comfy_url = app.comfyui_url if app else None
        comfy_url = _normalize_comfy_url(comfy_url or COMFY_URL or "").rstrip("/") if comfy_url or COMFY_URL else ""
        if comfy_url:
            remote_storage_bytes = get_run_remote_storage_bytes(comfy_url, run_images)
    out = {
        "id": run_entity.id,
        "project_id": run_entity.project_id,
        "workflow_version_id": run_entity.workflow_version_id,
        "app_id": run_entity.app_id,
        "status": run_entity.status,
        "created_at": run_entity.created_at,
        "prompt_id": run_entity.prompt_id,
        "seed": run_entity.seed,
        "images": json.loads(run_entity.images_json) if run_entity.images_json else [],
        "execution_time": run_entity.execution_time,
        "error": run_entity.error,
        "input_snapshot": json.loads(run_entity.input_snapshot_json) if run_entity.input_snapshot_json else None,
        "metadata_snapshot": run_repo.get_resolved_metadata_snapshot(run_entity) if run_repo else (json.loads(run_entity.metadata_snapshot_json) if run_entity.metadata_snapshot_json else None),
        "local_storage_status": run_entity.local_storage_status,
        "remote_status": run_entity.remote_status,
        "local_path": run_entity.local_path,
        "local_storage_bytes": local_storage_bytes,
        "remote_storage_bytes": remote_storage_bytes,
        "deleted_outputs": json.loads(run_entity.deleted_outputs_json) if run_entity.deleted_outputs_json else [],
        "parent_run_id": run_entity.parent_run_id,
        "parent_media_id": run_entity.parent_media_id,
        "parent_app_title": parent_app_title,
        "root_run_id": run_entity.root_run_id,
        "deleted_at": run_entity.deleted_at,
        "media": json.loads(run_entity.media_json) if run_entity.media_json else (json.loads(run_entity.images_json) if run_entity.images_json else []),
        "child_run_ids": [r.id for r in run_repo.get_child_runs(run_id)] if run_repo else [],
    }
    return out


@router.get("/runs/{run_id}/output-workflowui-embedded")
def get_run_output_workflowui_embedded(
    run_id: str,
    output_index: int = 0,
    state=Depends(get_run_queue_state),
    service: MediaStorageService = Depends(get_media_storage_service),
    db=Depends(get_db),
    ctx=Depends(require_user),
):
    """Embedded metadata: WorkflowUI (restore JSON) vs ComfyUI (PNG chunks or MP4 moov JSON)."""
    _, _, _, run_repo, _, _, _ = db
    run_entity = ensure_run_access(run_id, ctx, run_repo)
    entries = []
    try:
        if run_entity.media_json:
            entries = json.loads(run_entity.media_json)
        elif run_entity.images_json:
            entries = json.loads(run_entity.images_json)
    except Exception:
        entries = []
    if not isinstance(entries, list) or output_index < 0 or output_index >= len(entries):
        raise HTTPException(status_code=400, detail="Invalid output index")
    ent = entries[output_index]
    if not isinstance(ent, dict):
        raise HTTPException(status_code=400, detail="Invalid output")
    if ent.get("remote_deleted"):
        return {
            "hasEmbeddedWorkflowuiMetadata": False,
            "hasWorkflowuiEmbeddedMetadata": False,
            "hasComfyuiEmbeddedMetadata": False,
            "comfyuiEmbeddedCheckApplicable": False,
            "unavailable": True,
            "reason": "remote_deleted",
        }
    filename = str(ent.get("filename") or "")
    subfolder = str(ent.get("subfolder") or "")
    typ = str(ent.get("type") or ent.get("kind") or "output")
    try:
        content, _ = load_run_output_content_bytes(
            filename,
            subfolder,
            typ,
            run_id,
            preview=None,
            state=state,
            service=service,
            db=db,
            ctx=ctx,
        )
    except HTTPException:
        raise
    except Exception:
        return {
            "hasEmbeddedWorkflowuiMetadata": None,
            "hasWorkflowuiEmbeddedMetadata": None,
            "hasComfyuiEmbeddedMetadata": None,
            "comfyuiEmbeddedCheckApplicable": False,
            "unavailable": True,
            "reason": "fetch_failed",
        }
    has_wf = file_has_embedded_workflowui_metadata(content, filename, typ)
    has_comfy, comfy_applicable = file_has_embedded_comfyui_metadata(content)
    return {
        "hasEmbeddedWorkflowuiMetadata": has_wf,
        "hasWorkflowuiEmbeddedMetadata": has_wf,
        "hasComfyuiEmbeddedMetadata": has_comfy,
        "comfyuiEmbeddedCheckApplicable": comfy_applicable,
    }


@router.get("/runs/{run_id}/input-media")
def get_run_input_media(run_id: str, filename: str, db=Depends(get_db), ctx=Depends(require_user)):
    """Serve input media used by a run, guarded by run access checks."""
    _, _, _, run_repo, _, _, _ = db
    run_entity = ensure_run_access(run_id, ctx, run_repo)
    if not filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    allowed = False
    if run_entity.input_snapshot_json:
        try:
            snap = json.loads(run_entity.input_snapshot_json)
            values = snap.get("values") if isinstance(snap, dict) else {}
            if isinstance(values, dict):
                allowed = filename in {str(v) for v in values.values() if isinstance(v, str)}
        except Exception:
            allowed = False
    if not allowed:
        raise HTTPException(status_code=404, detail="Input media not found")
    base = INPUT_DATA_DIR.resolve()
    file_path = (INPUT_DATA_DIR / filename).resolve()
    if not str(file_path).startswith(str(base)) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Input media file not found")
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    return FileResponse(path=str(file_path), media_type=media_type, filename=filename)


@router.post("/runs/{run_id}/save")
def save_run(run_id: str, service: MediaStorageService = Depends(get_media_storage_service)):
    result = service.save_run(run_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Save failed"))
    return result


@router.post("/runs/{run_id}/save-image/{image_id}")
def save_run_image(run_id: str, image_id: str, service: MediaStorageService = Depends(get_media_storage_service)):
    try:
        image_index = int(image_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="image_id must be an integer index")
    result = service.save_run_image(run_id, image_index)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Save failed"))
    return result


@router.post("/runs/{run_id}/delete-run")
def delete_run_full(run_id: str, db=Depends(get_db), service: MediaStorageService = Depends(get_media_storage_service)):
    _, _, _, run_repo, _, _, _ = db
    children = run_repo.get_child_runs(run_id, limit=1) if run_repo else []
    if children:
        run_repo.update_run(run_id, deleted_at=int(time.time() * 1000))
        return {"ok": True, "soft_deleted": True}
    result = service.delete_run_full(run_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Delete run failed"))
    return result


@router.post("/runs/{run_id}/delete-remote")
def delete_run_remote(run_id: str, db=Depends(get_db), service: MediaStorageService = Depends(get_media_storage_service)):
    result = service.delete_remote(run_id, None)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Remote delete failed"))
    _, _, app_repo, run_repo, _, _, _ = db
    return build_updated_runs_response(result, app_repo, run_repo)


@router.post("/runs/{run_id}/delete-remote-image/{image_id}")
def delete_run_remote_image(run_id: str, image_id: str, db=Depends(get_db), service: MediaStorageService = Depends(get_media_storage_service)):
    try:
        image_index = int(image_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="image_id must be an integer index")
    if image_index < 0:
        raise HTTPException(status_code=400, detail="image_id must be a non-negative index")
    result = service.delete_remote(run_id, image_index=image_index)
    if not result.get("ok"):
        err = result.get("error") or result.get("remote_status") or "Remote delete failed"
        raise HTTPException(status_code=400, detail=err)
    _, _, app_repo, run_repo, _, _, _ = db
    return build_updated_runs_response(result, app_repo, run_repo)


@router.post("/runs/{run_id}/delete-remote-images")
async def delete_run_remote_images(run_id: str, request: Request, db=Depends(get_db), service: MediaStorageService = Depends(get_media_storage_service)):
    try:
        raw = await request.body()
        body = json.loads(raw) if raw else {}
    except Exception:
        body = {}
    indices = body.get("indices")
    if not isinstance(indices, list):
        raise HTTPException(status_code=400, detail="Body must be JSON with an 'indices' array, e.g. {\"indices\": [0, 1]}")
    try:
        indices = [int(x) for x in indices]
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="indices must be integers")
    if any(i < 0 for i in indices):
        raise HTTPException(status_code=400, detail="indices must be non-negative")
    result = service.delete_remote(run_id, image_indices=indices)
    if not result.get("ok"):
        err = result.get("error") or result.get("remote_status") or "Remote delete failed"
        raise HTTPException(status_code=400, detail=err)
    _, _, app_repo, run_repo, _, _, _ = db
    return build_updated_runs_response(result, app_repo, run_repo)


@router.post("/runs/{run_id}/remove-outputs")
async def remove_run_outputs(run_id: str, request: Request, db=Depends(get_db), service: MediaStorageService = Depends(get_media_storage_service)):
    try:
        raw = await request.body()
        body = json.loads(raw) if raw else {}
    except Exception:
        body = {}
    indices = body.get("indices")
    if not isinstance(indices, list):
        raise HTTPException(
            status_code=400,
            detail="Body must be JSON with an 'indices' array, e.g. {\"indices\": [0]}",
        )
    try:
        indices = [int(x) for x in indices]
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="indices must be integers")
    if any(i < 0 for i in indices):
        raise HTTPException(status_code=400, detail="indices must be non-negative")
    result = service.remove_outputs_without_local_copy(run_id, indices)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Remove failed"))
    _, _, app_repo, run_repo, _, _, _ = db
    return build_updated_runs_response(result, app_repo, run_repo)


@router.post("/runs/{run_id}/delete-local")
def delete_run_local(run_id: str, service: MediaStorageService = Depends(get_media_storage_service)):
    result = service.delete_local(run_id, None)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Local delete failed"))
    return result


@router.post("/runs/{run_id}/delete-local-image/{image_id}")
def delete_run_local_image(run_id: str, image_id: str, db=Depends(get_db), service: MediaStorageService = Depends(get_media_storage_service)):
    try:
        image_index = int(image_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="image_id must be an integer index")
    if image_index < 0:
        raise HTTPException(status_code=400, detail="image_id must be a non-negative index")
    result = service.delete_local(run_id, image_index=image_index)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Local delete failed"))
    _, _, app_repo, run_repo, _, _, _ = db
    return build_updated_runs_response(result, app_repo, run_repo)


@router.post("/runs/{run_id}/delete-local-images")
async def delete_run_local_images(run_id: str, request: Request, db=Depends(get_db), service: MediaStorageService = Depends(get_media_storage_service)):
    try:
        raw = await request.body()
        body = json.loads(raw) if raw else {}
    except Exception:
        body = {}
    indices = body.get("indices")
    if not isinstance(indices, list):
        raise HTTPException(status_code=400, detail="Body must be JSON with an 'indices' array")
    try:
        indices = [int(x) for x in indices]
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="indices must be integers")
    if any(i < 0 for i in indices):
        raise HTTPException(status_code=400, detail="indices must be non-negative")
    result = service.delete_local(run_id, image_indices=indices)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Local delete failed"))
    _, _, app_repo, run_repo, _, _, _ = db
    return build_updated_runs_response(result, app_repo, run_repo)


@router.post("/runs/{run_id}/delete-both")
def delete_run_both(run_id: str, db=Depends(get_db), service: MediaStorageService = Depends(get_media_storage_service)):
    result = service.delete_both(run_id, None)
    _, _, app_repo, run_repo, _, _, _ = db
    out = build_updated_runs_response(dict(result), app_repo, run_repo)
    if not result.get("ok"):
        err = result.get("error", "Delete failed")
        body = dict(out) if isinstance(out, dict) else {}
        body["detail"] = err
        return JSONResponse(status_code=400, content=body)
    return out


@router.post("/runs/{run_id}/delete-both-image/{image_id}")
def delete_run_both_image(run_id: str, image_id: str, db=Depends(get_db), service: MediaStorageService = Depends(get_media_storage_service)):
    try:
        image_index = int(image_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="image_id must be an integer index")
    if image_index < 0:
        raise HTTPException(status_code=400, detail="image_id must be a non-negative index")
    result = service.delete_both(run_id, image_index=image_index)
    _, _, app_repo, run_repo, _, _, _ = db
    out = build_updated_runs_response(dict(result), app_repo, run_repo)
    if not result.get("ok"):
        err = result.get("error", "Delete failed")
        body = dict(out) if isinstance(out, dict) else {}
        body["detail"] = err
        return JSONResponse(status_code=400, content=body)
    return out


@router.post("/runs/{run_id}/delete-both-images")
async def delete_run_both_images(run_id: str, request: Request, db=Depends(get_db), service: MediaStorageService = Depends(get_media_storage_service)):
    try:
        raw = await request.body()
        body = json.loads(raw) if raw else {}
    except Exception:
        body = {}
    indices = body.get("indices")
    if not isinstance(indices, list):
        raise HTTPException(status_code=400, detail="Body must be JSON with an 'indices' array")
    try:
        indices = [int(x) for x in indices]
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="indices must be integers")
    if any(i < 0 for i in indices):
        raise HTTPException(status_code=400, detail="indices must be non-negative")
    result = service.delete_both(run_id, image_indices=indices)
    _, _, app_repo, run_repo, _, _, _ = db
    out = build_updated_runs_response(dict(result), app_repo, run_repo)
    if not result.get("ok"):
        err = result.get("error", "Delete failed")
        body = dict(out) if isinstance(out, dict) else {}
        body["detail"] = err
        return JSONResponse(status_code=400, content=body)
    return out
