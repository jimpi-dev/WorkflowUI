import json
import os
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException

from authz import ensure_run_access, require_user
from dependencies import get_db, get_media_storage_service, get_run_queue_state, INPUT_DATA_DIR, get_vault_input_repo
from routers.execution import load_run_output_content_bytes
from services.vault_input_access import ensure_can_read_input_file
from services.workflowui_metadata import build_workflowui_metadata_payload, workflowui_metadata_to_json_string
from services.png_metadata import inject_workflowui_chunk
from services.mp3_metadata import inject_workflowui_metadata as inject_workflowui_metadata_mp3
from services.mp4_metadata import inject_workflowui_metadata as inject_workflowui_metadata_mp4

router = APIRouter(dependencies=[Depends(require_user)])


def _genvault_url() -> str:
    return (os.environ.get("GENVAULT_URL") or "http://localhost:8090").rstrip("/")


def _pick_run_media_entry(run_entity: Any, output_index: int) -> dict[str, Any]:
    entries: list[Any] = []
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
        raise HTTPException(status_code=400, detail="Invalid output entry")
    return ent


def _embed_workflowui_metadata_if_needed(content: bytes, filename: str, type_hint: str, run_id: str, db) -> bytes:
    _, workflow_repo, app_repo, run_repo, project_repo, _, _ = db
    payload = build_workflowui_metadata_payload(run_id, run_repo, workflow_repo, app_repo, project_repo)
    if not payload:
        return content
    json_str = workflowui_metadata_to_json_string(payload)
    lower_name = (filename or "").lower()
    t = (type_hint or "").strip().lower()
    if content.startswith(b"\x89PNG\r\n\x1a\n") or lower_name.endswith(".png"):
        return inject_workflowui_chunk(content, json_str)
    if t == "audio" or lower_name.endswith(".mp3"):
        return inject_workflowui_metadata_mp3(content, json_str)
    if t == "video" or lower_name.endswith((".mp4", ".mov", ".m4v")):
        return inject_workflowui_metadata_mp4(content, json_str)
    return content


@router.get("/genvault/url")
def get_genvault_url() -> dict[str, str]:
    return {"url": _genvault_url()}


@router.post("/genvault/push-from-run")
def push_from_run(
    payload: dict[str, Any],
    state=Depends(get_run_queue_state),
    service=Depends(get_media_storage_service),
    db=Depends(get_db),
    ctx=Depends(require_user),
):
    run_id = str(payload.get("run_id") or "").strip()
    output_index = payload.get("output_index")
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")
    if not isinstance(output_index, int):
        raise HTTPException(status_code=400, detail="output_index must be an integer")

    run_repo = db[3]
    run_entity = ensure_run_access(run_id, ctx, run_repo)
    ent = _pick_run_media_entry(run_entity, output_index)
    if ent.get("remote_deleted"):
        raise HTTPException(status_code=400, detail="Output is deleted")

    filename = str(ent.get("filename") or "")
    subfolder = str(ent.get("subfolder") or "")
    media_type = str(ent.get("type") or ent.get("kind") or "output")

    content, content_type = load_run_output_content_bytes(
        filename,
        subfolder,
        media_type,
        run_id,
        preview=None,
        state=state,
        service=service,
        db=db,
        ctx=ctx,
    )
    # For generated media, embed WorkflowUI metadata before sending to GenVault.
    if (media_type or "").strip().lower() != "input":
        content = _embed_workflowui_metadata_if_needed(content, filename, media_type, run_id, db)
    upload_name = filename or f"{run_id}-{output_index}.bin"

    source_key = f"run:{run_id}:output:{output_index}"
    form_data = {
        "source_type": "generation_output",
        "source_key": source_key,
        "source_run_id": run_id,
        "source_output_index": str(output_index),
    }
    files = {"file": (upload_name, content, content_type or "application/octet-stream")}
    try:
        res = requests.post(f"{_genvault_url()}/api/upload", files=files, data=form_data, timeout=120)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"GenVault unreachable: {e!s}")
    if not res.ok:
        detail = res.text[:500] if res.text else f"status {res.status_code}"
        raise HTTPException(status_code=502, detail=f"GenVault upload failed: {detail}")
    data = res.json() if res.content else {}
    return {"ok": True, "run_id": run_id, "output_index": output_index, "uploaded": data}


@router.post("/genvault/push-input")
def push_input(
    payload: dict[str, Any],
    db=Depends(get_db),
    ctx=Depends(require_user),
):
    filename = str(payload.get("filename") or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    run_repo = db[3]
    if ctx.auth_enabled:
        ensure_can_read_input_file(ctx, filename, get_vault_input_repo(), run_repo)

    file_path = (INPUT_DATA_DIR / filename).resolve()
    base = INPUT_DATA_DIR.resolve()
    if not str(file_path).startswith(str(base)) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Input file not found")

    content = file_path.read_bytes()
    form_data = {
        "source_type": "input_image",
        "source_key": f"input:{filename}",
        "source_input_filename": filename,
    }
    files = {"file": (filename, content, "application/octet-stream")}
    try:
        res = requests.post(f"{_genvault_url()}/api/upload", files=files, data=form_data, timeout=120)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"GenVault unreachable: {e!s}")
    if not res.ok:
        detail = res.text[:500] if res.text else f"status {res.status_code}"
        raise HTTPException(status_code=502, detail=f"GenVault upload failed: {detail}")
    data = res.json() if res.content else {}
    return {"ok": True, "filename": filename, "uploaded": data}


@router.post("/genvault/exists")
def genvault_exists(payload: dict[str, Any]):
    try:
        res = requests.post(f"{_genvault_url()}/api/exists", json=payload, timeout=30)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"GenVault unreachable: {e!s}")
    if not res.ok:
        detail = res.text[:500] if res.text else f"status {res.status_code}"
        raise HTTPException(status_code=502, detail=f"GenVault exists check failed: {detail}")
    return res.json()

