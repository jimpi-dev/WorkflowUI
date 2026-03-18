import json
import time
import uuid
import logging
from pathlib import Path
import shutil

from fastapi import APIRouter, HTTPException, Depends, Response

from db.migrate import QUICK_RUNS_PROJECT_ID
from config import get_media_storage_config

from dependencies import get_db, get_media_storage_service, get_run_queue_state, COMFY_URL
from services.comfyui_info import (
    normalize_comfy_url as _normalize_comfy_url,
    get_runs_remote_storage_bytes_batch,
    get_runs_remote_storage_bytes_deduplicated,
)
from services.run_serialization import (
    safe_json_loads,
    latent_resolution_from_input_snapshot,
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/projects")
def post_projects(body: dict, db=Depends(get_db)):
    name = body.get("name")
    if not name or not isinstance(name, str) or not name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    _, _, _, _, project_repo, _, _ = db
    description = body.get("description")
    tags = body.get("tags")
    tags_json = json.dumps(tags) if isinstance(tags, (list, tuple)) else None
    metadata = body.get("metadata")
    metadata_json = json.dumps(metadata) if isinstance(metadata, dict) else None
    storage_mode = body.get("storage_mode") or body.get("storageMode") or "inherit"
    if storage_mode not in {"inherit", "local", "remote"}:
        raise HTTPException(status_code=400, detail="storage_mode must be inherit, local, or remote")
    header_color = body.get("header_color")
    if header_color is not None and not isinstance(header_color, str):
        header_color = None
    if header_color is not None and isinstance(header_color, str) and not header_color.strip():
        header_color = None
    created_at = int(time.time() * 1000)
    updated_at = created_at
    project_id = str(uuid.uuid4())
    created = project_repo.create_project(
        project_id,
        name.strip(),
        description,
        created_at,
        updated_at,
        metadata_json,
        tags_json,
        storage_mode,
        header_color=header_color.strip() if header_color else None,
    )
    return {
        "id": created.id,
        "name": created.name,
        "description": created.description,
        "created_at": created.created_at,
        "updated_at": created.updated_at,
        "tags": json.loads(created.tags_json) if created.tags_json else [],
        "metadata": json.loads(created.metadata_json) if created.metadata_json else None,
        "storage_mode": created.storage_mode,
        "header_color": created.header_color,
    }


@router.get("/projects")
def list_projects(
    tag: str | None = None,
    limit: int = 100,
    archived: bool = False,
    db=Depends(get_db),
):
    _, _, _, run_repo, project_repo, _, _ = db
    projects = project_repo.list_projects(tag=tag, limit=limit, archived=archived)
    result = []
    for p in projects:
        run_count = run_repo.count_runs_by_project(p.id)
        result.append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
            "tags": safe_json_loads(p.tags_json, []),
            "metadata": safe_json_loads(p.metadata_json),
            "storage_mode": p.storage_mode,
            "run_count": run_count,
            "header_color": p.header_color,
            "archived_at": p.archived_at,
        })
    return result


@router.get("/projects/{project_id}")
def get_project_detail(project_id: str, db=Depends(get_db)):
    _, _, app_repo, run_repo, project_repo, _, _ = db
    proj = project_repo.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    run_count = run_repo.count_runs_by_project(project_id)
    runs_list = run_repo.get_runs_by_project(project_id, limit=1000)
    app_ids = set()
    has_local_data = False
    has_remote_data = False
    meta = safe_json_loads(proj.metadata_json, {}) if proj else {}
    deleted_app_ids = []
    if isinstance(meta, dict):
        raw_deleted = meta.get("deleted_app_ids")
        if isinstance(raw_deleted, list):
            deleted_app_ids = [d for d in raw_deleted if isinstance(d, str) and d.strip()]
    for r in runs_list:
        if r.app_id:
            app_ids.add(r.app_id)
        if r.local_storage_status and r.local_storage_status in ("saved", "partial"):
            has_local_data = True
        if r.images_json and r.images_json.strip():
            try:
                imgs = json.loads(r.images_json)
                if isinstance(imgs, list) and len(imgs) > 0:
                    for ent in imgs:
                        if isinstance(ent, dict) and not ent.get("remote_deleted"):
                            has_remote_data = True
                            break
            except (json.JSONDecodeError, TypeError):
                pass
    for aid in deleted_app_ids:
        app_ids.add(aid)
    apps_used = []
    for aid in app_ids:
        app = app_repo.get_app_by_id(aid)
        if app:
            apps_used.append({"id": app.id, "slug": app.slug, "title": app.title, "removed": False, "header_color": app.header_color})
        else:
            apps_used.append({"id": aid, "slug": None, "title": None, "removed": True})
    return {
        "id": proj.id,
        "name": proj.name,
        "description": proj.description,
        "created_at": proj.created_at,
        "updated_at": proj.updated_at,
        "tags": safe_json_loads(proj.tags_json, []),
        "metadata": safe_json_loads(proj.metadata_json),
        "storage_mode": proj.storage_mode,
        "run_count": run_count,
        "apps_used": apps_used,
        "header_color": proj.header_color,
        "archived_at": proj.archived_at,
        "has_local_data": has_local_data,
        "has_remote_data": has_remote_data,
    }


@router.patch("/projects/{project_id}")
def patch_project(project_id: str, body: dict, db=Depends(get_db)):
    if project_id == QUICK_RUNS_PROJECT_ID and "archived_at" in body:
        raise HTTPException(status_code=400, detail="Quick runs project cannot be archived.")
    _, _, _, _, project_repo, _, _ = db
    proj = project_repo.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    kwargs: dict = {"updated_at": int(time.time() * 1000)}
    if "name" in body and body["name"] is not None:
        name = body["name"]
        if isinstance(name, str) and name.strip():
            kwargs["name"] = name.strip()
    if "description" in body:
        kwargs["description"] = body["description"] if isinstance(body["description"], str) else None
    if "tags" in body:
        tags = body["tags"]
        kwargs["tags_json"] = json.dumps(tags) if isinstance(tags, (list, tuple)) else None
    if "metadata" in body:
        meta = body["metadata"]
        kwargs["metadata_json"] = json.dumps(meta) if isinstance(meta, dict) else None
    if "header_color" in body:
        hc = body["header_color"]
        kwargs["header_color"] = hc.strip() if isinstance(hc, str) and hc.strip() else None
    if "archived_at" in body:
        aa = body["archived_at"]
        if aa is None:
            kwargs["archived_at"] = None
        elif isinstance(aa, (int, float)) and not isinstance(aa, bool):
            kwargs["archived_at"] = int(aa)
    updated = project_repo.update_project(project_id, **kwargs)
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "id": updated.id,
        "name": updated.name,
        "description": updated.description,
        "updated_at": updated.updated_at,
        "tags": json.loads(updated.tags_json) if updated.tags_json else [],
        "metadata": json.loads(updated.metadata_json) if updated.metadata_json else None,
        "header_color": updated.header_color,
        "archived_at": updated.archived_at,
    }


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, body: dict | None = None, db=Depends(get_db)):
    if project_id == QUICK_RUNS_PROJECT_ID:
        raise HTTPException(status_code=400, detail="Quick runs project cannot be deleted or archived.")
    _, workflow_repo, _, run_repo, project_repo, _, _ = db
    proj = project_repo.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    keep = (body or {}).get("keep", "none")
    if keep not in ("local", "remote", "none"):
        raise HTTPException(status_code=400, detail="keep must be local, remote, or none")
    run_ids = [r.id for r in run_repo.get_runs_by_project(project_id, limit=10000)]
    media_storage = get_media_storage_config()
    media_service = get_media_storage_service()
    root_path = (media_storage.root_path or "").strip()
    project_dir = Path(root_path) / project_id if root_path else None
    if keep == "remote":
        if project_dir and project_dir.exists():
            try:
                shutil.rmtree(project_dir, ignore_errors=True)
            except Exception as e:
                logger.warning("delete_project: failed to remove local dir %s: %s", project_dir, e)
    elif keep == "local":
        for rid in run_ids:
            try:
                media_service.delete_remote(rid, None)
            except Exception as e:
                logger.warning("delete_project: delete_remote run %s: %s", rid, e)
    else:
        if project_dir and project_dir.exists():
            try:
                shutil.rmtree(project_dir, ignore_errors=True)
            except Exception as e:
                logger.warning("delete_project: failed to remove local dir %s: %s", project_dir, e)
        for rid in run_ids:
            try:
                media_service.delete_remote(rid, None)
            except Exception as e:
                logger.warning("delete_project: delete_remote run %s: %s", rid, e)

    def _delete_db(conn):
        run_repo.delete_runs_by_project(project_id, conn=conn)
        project_repo.delete_project(project_id, conn=conn)

    workflow_repo.run_in_transaction(_delete_db)
    return Response(status_code=204)


@router.patch("/projects/{project_id}/storage")
def patch_project_storage(project_id: str, body: dict, db=Depends(get_db)):
    storage_mode = body.get("storage_mode") or body.get("storageMode")
    if storage_mode not in {"inherit", "local", "remote"}:
        raise HTTPException(status_code=400, detail="storage_mode must be inherit, local, or remote")
    _, _, _, _, project_repo, _, _ = db
    updated = project_repo.update_project(
        project_id,
        storage_mode=storage_mode,
        updated_at=int(time.time() * 1000),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "id": updated.id,
        "storage_mode": updated.storage_mode,
        "updated_at": updated.updated_at,
    }


@router.get("/projects/{project_id}/runs")
def list_project_runs(
    project_id: str,
    app_id: str | None = None,
    workflow_version_id: str | None = None,
    since: int | None = None,
    until: int | None = None,
    meta_q: str | None = None,
    deleted_app: bool | None = None,
    limit: int = 100,
    offset: int = 0,
    db=Depends(get_db),
    state=Depends(get_run_queue_state),
):
    _, _, app_repo, run_repo, project_repo, _, _ = db
    proj = project_repo.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    meta_q_trim = meta_q.strip() if meta_q and isinstance(meta_q, str) else None
    total = run_repo.count_runs_by_project_filtered(
        project_id,
        app_id=app_id,
        workflow_version_id=workflow_version_id,
        since_ts=since,
        until_ts=until,
        meta_q=meta_q_trim,
        deleted_app=deleted_app,
    )
    runs_list = run_repo.get_runs_by_project(
        project_id,
        app_id=app_id,
        workflow_version_id=workflow_version_id,
        since_ts=since,
        until_ts=until,
        meta_q=meta_q_trim,
        deleted_app=deleted_app,
        limit=limit,
        offset=offset,
    )
    out = []
    logger.debug(
        "list_project_runs: project_id=%s app_id=%s deleted_app=%s since=%s until=%s meta_q=%s limit=%s offset=%s base_count=%s",
        project_id,
        app_id,
        deleted_app,
        since,
        until,
        meta_q_trim,
        limit,
        offset,
        len(runs_list),
    )
    with state.queue_lock:
        mem = {rid: dict(r) if isinstance(r, dict) else {} for rid, r in state.runs.items()}
    for r in runs_list:
        app_slug = None
        app_title = None
        app_header_color = None
        app_id_out = r.app_id
        if r.app_id:
            app = app_repo.get_app_by_id(r.app_id)
            if app:
                app_slug = app.slug
                app_title = app.title
                app_header_color = app.header_color
            else:
                # Hide deleted app IDs from API consumers while keeping
                # deleted-app detection available server-side.
                app_id_out = None
        mem_run = mem.get(r.id) if mem else None
        status = mem_run.get("status", r.status) if mem_run else r.status
        error = mem_run.get("error", r.error) if mem_run else r.error
        queue_position = mem_run.get("queue_position") if mem_run else None
        comfyui_unreachable_warning = mem_run.get("comfyui_unreachable_warning") if mem_run else None
        # Sizes are loaded separately via GET .../runs/storage_sizes so the list returns fast
        out.append({
            "id": r.id,
            "project_id": r.project_id,
            "workflow_version_id": r.workflow_version_id,
            "app_id": app_id_out,
            "app_slug": app_slug,
            "app_title": app_title,
            "app_header_color": app_header_color,
            "status": status,
            "queue_position": queue_position,
            "created_at": r.created_at,
            "seed": r.seed,
            "images": safe_json_loads(r.images_json, []),
            "execution_time": r.execution_time,
            "error": error,
            "run_group_id": r.run_group_id,
            "latent_resolution": latent_resolution_from_input_snapshot(r.input_snapshot_json),
            "local_storage_status": r.local_storage_status,
            "remote_status": r.remote_status,
            "local_path": r.local_path,
            "local_storage_bytes": None,
            "remote_storage_bytes": None,
            "comfyui_unreachable_warning": comfyui_unreachable_warning,
            "parent_run_id": r.parent_run_id,
            "parent_media_id": r.parent_media_id,
            "root_run_id": r.root_run_id,
        })

    # Debug sample of app_id values to verify deleted-app matching
    logger.debug(
        "list_project_runs: sample app ids (first 10): %s",
        [
            {
                "id": item.get("id"),
                "project_id": item.get("project_id"),
                "app_id": repr(item.get("app_id")),
                "app_slug": repr(item.get("app_slug")),
                "app_title": repr(item.get("app_title")),
            }
            for item in out[:10]
        ],
    )
    return {"runs": out, "total": total}


def _format_run_date_ms(ms: int) -> str:
    try:
        return time.strftime("%Y-%m-%d", time.gmtime(ms / 1000))
    except Exception:
        return time.strftime("%Y-%m-%d", time.gmtime())


@router.get("/projects/{project_id}/runs/storage_sizes")
def get_project_runs_storage_sizes(
    project_id: str,
    run_ids: str,
    db=Depends(get_db),
    service=Depends(get_media_storage_service),
):
    """Return local and remote storage bytes for the given run IDs (comma-separated). Runs must belong to the project."""
    _, _, app_repo, run_repo, project_repo, _, _ = db
    proj = project_repo.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    ids = [rid.strip() for rid in (run_ids or "").split(",") if rid.strip()]
    if not ids:
        return {}
    result: dict[str, dict[str, int | None]] = {}
    runs_with_images: list[tuple[str, str, list]] = []  # (run_id, comfy_url, images)
    for rid in ids:
        r = run_repo.get_run(rid)
        if not r or r.project_id != project_id:
            continue
        result[rid] = {"local_storage_bytes": None, "remote_storage_bytes": None}
        if r.local_storage_status in ("saved", "partial"):
            result[rid]["local_storage_bytes"] = service.get_run_local_storage_bytes(r)
        run_images = safe_json_loads(r.images_json, [])
        if run_images:
            app = app_repo.get_app_by_id(r.app_id) if r.app_id else None
            raw_url = (r.comfyui_url or (app.comfyui_url if app else None) or COMFY_URL or "").strip()
            # Always try to resolve a ComfyUI URL for remote size when run has images
            if not raw_url:
                raw_url = (COMFY_URL or "http://localhost:8188/").strip()
            comfy_url = _normalize_comfy_url(raw_url).rstrip("/") if raw_url else ""
            if comfy_url:
                runs_with_images.append((rid, comfy_url, run_images))
    by_url: dict[str, list[tuple[str, list]]] = {}
    for rid, url, imgs in runs_with_images:
        by_url.setdefault(url, []).append((rid, imgs))
    for url, entries in by_url.items():
        groups = [imgs for _, imgs in entries]
        sizes = get_runs_remote_storage_bytes_batch(url, groups)
        if sizes is None:
            sizes = get_runs_remote_storage_bytes_deduplicated(url, groups)
        for i, (rid, _) in enumerate(entries):
            if i < len(sizes):
                result[rid]["remote_storage_bytes"] = sizes[i]
    return result


@router.post("/projects/{project_id}/runs/move")
def move_runs_to_project(
    project_id: str,
    body: dict,
    db=Depends(get_db),
):
    run_ids = body.get("run_ids")
    target_project_id = body.get("target_project_id")
    if not isinstance(run_ids, list) or not run_ids:
        raise HTTPException(status_code=400, detail="run_ids must be a non-empty list")
    if not target_project_id or not isinstance(target_project_id, str) or not target_project_id.strip():
        raise HTTPException(status_code=400, detail="target_project_id is required")
    target_project_id = target_project_id.strip()
    if target_project_id == project_id:
        raise HTTPException(status_code=400, detail="Target project must be different from source project")

    _, _, _, run_repo, project_repo, _, _ = db
    source_proj = project_repo.get_project(project_id)
    if not source_proj:
        raise HTTPException(status_code=404, detail="Source project not found")
    if getattr(source_proj, "archived_at", None) is not None:
        raise HTTPException(status_code=400, detail="Cannot move runs from an archived project")

    target_proj = project_repo.get_project(target_project_id)
    if not target_proj:
        raise HTTPException(status_code=404, detail="Target project not found")
    if getattr(target_proj, "archived_at", None) is not None:
        raise HTTPException(status_code=400, detail="Cannot move runs into an archived project")

    run_ids = [str(rid).strip() for rid in run_ids if rid]
    if not run_ids:
        raise HTTPException(status_code=400, detail="run_ids must be a non-empty list")

    runs_to_move = []
    for rid in run_ids:
        r = run_repo.get_run(rid)
        if not r:
            raise HTTPException(status_code=404, detail=f"Run not found: {rid}")
        if r.project_id != project_id:
            raise HTTPException(status_code=400, detail=f"Run {rid} does not belong to this project")
        runs_to_move.append(r)

    root = (get_media_storage_config().root_path or "").strip()
    if root:
        for run in runs_to_move:
            run_date = _format_run_date_ms(run.created_at)
            group_or_run_id = run.run_group_id or run.id
            old_dir = Path(root) / project_id / run_date / group_or_run_id
            new_dir = Path(root) / target_project_id / run_date / group_or_run_id
            if old_dir.exists() and old_dir.is_dir():
                try:
                    new_dir.parent.mkdir(parents=True, exist_ok=True)
                    if new_dir.exists():
                        shutil.rmtree(new_dir)
                    shutil.move(str(old_dir), str(new_dir))
                except Exception as e:
                    logger.warning("move_runs_to_project: failed to move run dir %s -> %s: %s", old_dir, new_dir, e)

    def _do_move(conn):
        return run_repo.move_runs_to_project([r.id for r in runs_to_move], target_project_id, conn=conn)

    workflow_repo = db[1]
    n = workflow_repo.run_in_transaction(_do_move)

    if root and n > 0:
        for run in runs_to_move:
            run_date = _format_run_date_ms(run.created_at)
            group_or_run_id = run.run_group_id or run.id
            new_path = Path(root) / target_project_id / run_date / group_or_run_id
            if new_path.exists():
                run_repo.update_run(run.id, local_path=str(new_path))

    return {"moved": n}


@router.get("/projects/{project_id}/runs/stats")
def get_project_runs_stats(
    project_id: str,
    app_id: str | None = None,
    workflow_version_id: str | None = None,
    since: int | None = None,
    until: int | None = None,
    meta_q: str | None = None,
    deleted_app: bool | None = None,
    db=Depends(get_db),
):
    _, _, _, run_repo, project_repo, _, _ = db
    proj = project_repo.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    meta_q_trim = meta_q.strip() if meta_q and isinstance(meta_q, str) else None
    total_generations = run_repo.count_runs_by_project_filtered(
        project_id,
        app_id=app_id,
        workflow_version_id=workflow_version_id,
        since_ts=since,
        until_ts=until,
        meta_q=meta_q_trim,
        deleted_app=deleted_app,
    )
    total_runs = run_repo.count_run_rows_by_project_filtered(
        project_id,
        app_id=app_id,
        workflow_version_id=workflow_version_id,
        since_ts=since,
        until_ts=until,
        meta_q=meta_q_trim,
        deleted_app=deleted_app,
    )
    return {"total_runs": total_runs, "total_generations": total_generations}
