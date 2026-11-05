import json
import os
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException

from authz import ensure_run_access, require_user
from config import get_genvault_config
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


def _require_genvault_enabled() -> None:
    if not get_genvault_config().enabled:
        raise HTTPException(status_code=404, detail="GenVault is disabled")


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


def _upload_bytes_to_genvault(
    content: bytes,
    upload_name: str,
    content_type: str,
    form_data: dict[str, str],
) -> dict[str, Any]:
    files = {"file": (upload_name, content, content_type or "application/octet-stream")}
    try:
        res = requests.post(f"{_genvault_url()}/api/upload", files=files, data=form_data, timeout=120)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"GenVault unreachable: {e!s}") from e
    if not res.ok:
        detail = res.text[:500] if res.text else f"status {res.status_code}"
        raise HTTPException(status_code=502, detail=f"GenVault upload failed: {detail}")
    return res.json() if res.content else {}


def _list_run_media_entries(run_entity: Any) -> list[dict[str, Any]]:
    entries: list[Any] = []
    try:
        if run_entity.media_json:
            entries = json.loads(run_entity.media_json)
        elif run_entity.images_json:
            entries = json.loads(run_entity.images_json)
    except Exception:
        entries = []
    if not isinstance(entries, list):
        return []
    return [ent for ent in entries if isinstance(ent, dict)]


def _exists_many_run_outputs(items: list[tuple[str, int]]) -> dict[tuple[str, int], bool]:
    """One GenVault exists call for many (run_id, output_index) pairs — folder-independent via source_key."""
    if not items:
        return {}
    payload = {
        "items": [
            {
                "client_key": f"{run_id}:{idx}",
                "source_key": f"run:{run_id}:output:{idx}",
                "source_run_id": run_id,
                "source_output_index": idx,
            }
            for run_id, idx in items
        ]
    }
    try:
        res = requests.post(f"{_genvault_url()}/api/exists", json=payload, timeout=30)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"GenVault unreachable: {e!s}") from e
    if not res.ok:
        detail = res.text[:500] if res.text else f"status {res.status_code}"
        raise HTTPException(status_code=502, detail=f"GenVault exists check failed: {detail}")
    data = res.json() if res.content else {}
    verified: dict[tuple[str, int], bool] = {(run_id, idx): False for run_id, idx in items}
    for row in data.get("items") or []:
        if not isinstance(row, dict):
            continue
        client_key = str(row.get("client_key") or "")
        if ":" not in client_key:
            continue
        run_id, _, idx_s = client_key.partition(":")
        try:
            idx = int(idx_s)
        except ValueError:
            continue
        key = (run_id, idx)
        if key in verified:
            verified[key] = bool(row.get("in_vault"))
    return verified


def _exists_run_outputs_in_genvault(run_id: str, output_indices: list[int]) -> dict[int, bool]:
    if not output_indices:
        return {}
    bulk = _exists_many_run_outputs([(run_id, idx) for idx in output_indices])
    return {idx: bulk.get((run_id, idx), False) for idx in output_indices}


def _mark_upload_result_in_vault(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("ok"):
        result["in_vault"] = True
    return result


def _sync_run_outputs_to_genvault(
    run_id: str,
    entries: list[dict[str, Any]],
    indices_to_sync: list[int],
    preflight: dict[int, bool],
    *,
    state,
    service,
    db,
    ctx,
) -> dict[str, Any]:
    output_results: list[dict[str, Any]] = []
    skipped_count = 0
    uploaded_count = 0

    for output_index in indices_to_sync:
        if preflight.get(output_index):
            output_results.append(
                {
                    "output_index": output_index,
                    "ok": True,
                    "skipped": True,
                    "in_vault": True,
                }
            )
            skipped_count += 1
            continue
        try:
            result = _upload_run_output_to_genvault(
                run_id,
                output_index,
                entries[output_index],
                state=state,
                service=service,
                db=db,
                ctx=ctx,
            )
            output_results.append(_mark_upload_result_in_vault(result))
            uploaded_count += 1
        except HTTPException as e:
            output_results.append({"output_index": output_index, "ok": False, "error": str(e.detail)})
        except Exception as e:
            output_results.append({"output_index": output_index, "ok": False, "error": str(e)})

    all_uploaded = all(r.get("ok") for r in output_results) if output_results else True
    all_verified = all(r.get("in_vault") for r in output_results if r.get("ok")) if output_results else True

    return {
        "ok": all_uploaded and all_verified,
        "run_id": run_id,
        "outputs": output_results,
        "all_verified": all_verified,
        "output_count": len(indices_to_sync),
        "skipped_count": skipped_count,
        "uploaded_count": uploaded_count,
    }


def _upload_run_output_to_genvault(
    run_id: str,
    output_index: int,
    ent: dict[str, Any],
    *,
    state,
    service,
    db,
    ctx,
) -> dict[str, Any]:
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
    uploaded = _upload_bytes_to_genvault(
        content, upload_name, content_type or "application/octet-stream", form_data
    )
    return {
        "output_index": output_index,
        "ok": True,
        "skipped": False,
        "duplicate": bool(uploaded.get("duplicate")),
        "uploaded": uploaded,
    }


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


@router.get("/genvault/health")
def genvault_health():
    _require_genvault_enabled()
    try:
        res = requests.get(f"{_genvault_url()}/health", timeout=5)
        if res.ok:
            return {"online": True}
        return {"online": False, "detail": f"status {res.status_code}"}
    except requests.RequestException as e:
        return {"online": False, "detail": str(e)}


@router.get("/genvault/url")
def get_genvault_url() -> dict[str, str]:
    _require_genvault_enabled()
    return {"url": _genvault_url()}


@router.post("/genvault/push-from-run")
def push_from_run(
    payload: dict[str, Any],
    state=Depends(get_run_queue_state),
    service=Depends(get_media_storage_service),
    db=Depends(get_db),
    ctx=Depends(require_user),
):
    _require_genvault_enabled()
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

    preflight = _exists_run_outputs_in_genvault(run_id, [output_index])
    if preflight.get(output_index):
        return {
            "ok": True,
            "run_id": run_id,
            "output_index": output_index,
            "skipped": True,
            "in_vault": True,
            "uploaded": {"duplicate": True, "match_reason": "source_key"},
        }

    try:
        result = _upload_run_output_to_genvault(
            run_id,
            output_index,
            ent,
            state=state,
            service=service,
            db=db,
            ctx=ctx,
        )
    except HTTPException:
        raise
    result = _mark_upload_result_in_vault(result)
    return {
        "ok": True,
        "run_id": run_id,
        "output_index": output_index,
        "skipped": False,
        "in_vault": bool(result.get("in_vault")),
        "duplicate": bool(result.get("duplicate")),
        "uploaded": result.get("uploaded"),
    }


@router.post("/genvault/push-run")
def push_run(
    payload: dict[str, Any],
    state=Depends(get_run_queue_state),
    service=Depends(get_media_storage_service),
    db=Depends(get_db),
    ctx=Depends(require_user),
):
    _require_genvault_enabled()
    run_id = str(payload.get("run_id") or "").strip()
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")

    run_repo = db[3]
    run_entity = ensure_run_access(run_id, ctx, run_repo)
    entries = _list_run_media_entries(run_entity)
    indices_to_sync = [i for i, ent in enumerate(entries) if not ent.get("remote_deleted")]
    if not indices_to_sync:
        return {
            "ok": True,
            "run_id": run_id,
            "outputs": [],
            "all_verified": True,
            "output_count": 0,
            "skipped_count": 0,
            "uploaded_count": 0,
        }

    preflight = _exists_run_outputs_in_genvault(run_id, indices_to_sync)
    return _sync_run_outputs_to_genvault(
        run_id,
        entries,
        indices_to_sync,
        preflight,
        state=state,
        service=service,
        db=db,
        ctx=ctx,
    )


@router.post("/genvault/push-runs")
def push_runs(
    payload: dict[str, Any],
    state=Depends(get_run_queue_state),
    service=Depends(get_media_storage_service),
    db=Depends(get_db),
    ctx=Depends(require_user),
):
    _require_genvault_enabled()
    raw_run_ids = payload.get("run_ids")
    if not isinstance(raw_run_ids, list) or not raw_run_ids:
        raise HTTPException(status_code=400, detail="run_ids must be a non-empty list")

    run_repo = db[3]
    plans: list[dict[str, Any]] = []
    exists_items: list[tuple[str, int]] = []

    for raw_id in raw_run_ids:
        run_id = str(raw_id or "").strip()
        if not run_id:
            continue
        run_entity = ensure_run_access(run_id, ctx, run_repo)
        entries = _list_run_media_entries(run_entity)
        indices = [i for i, ent in enumerate(entries) if not ent.get("remote_deleted")]
        plans.append({"run_id": run_id, "entries": entries, "indices": indices})
        for idx in indices:
            exists_items.append((run_id, idx))

    if not plans:
        raise HTTPException(status_code=400, detail="No valid run_ids provided")

    preflight_bulk = _exists_many_run_outputs(exists_items) if exists_items else {}

    run_results: list[dict[str, Any]] = []
    total_skipped = 0
    total_uploaded = 0

    for plan in plans:
        run_id = plan["run_id"]
        indices: list[int] = plan["indices"]
        if not indices:
            run_results.append(
                {
                    "ok": True,
                    "run_id": run_id,
                    "outputs": [],
                    "all_verified": True,
                    "output_count": 0,
                    "skipped_count": 0,
                    "uploaded_count": 0,
                }
            )
            continue
        preflight = {idx: preflight_bulk.get((run_id, idx), False) for idx in indices}
        result = _sync_run_outputs_to_genvault(
            run_id,
            plan["entries"],
            indices,
            preflight,
            state=state,
            service=service,
            db=db,
            ctx=ctx,
        )
        run_results.append(result)
        total_skipped += int(result.get("skipped_count") or 0)
        total_uploaded += int(result.get("uploaded_count") or 0)

    return {
        "ok": all(r.get("ok") for r in run_results),
        "runs": run_results,
        "skipped_count": total_skipped,
        "uploaded_count": total_uploaded,
    }


@router.post("/genvault/push-input")
def push_input(
    payload: dict[str, Any],
    db=Depends(get_db),
    ctx=Depends(require_user),
):
    _require_genvault_enabled()
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
    try:
        data = _upload_bytes_to_genvault(content, filename, "application/octet-stream", form_data)
    except HTTPException:
        raise
    return {"ok": True, "filename": filename, "uploaded": data}


@router.post("/genvault/exists")
def genvault_exists(payload: dict[str, Any]):
    _require_genvault_enabled()
    try:
        res = requests.post(f"{_genvault_url()}/api/exists", json=payload, timeout=30)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"GenVault unreachable: {e!s}")
    if not res.ok:
        detail = res.text[:500] if res.text else f"status {res.status_code}"
        raise HTTPException(status_code=502, detail=f"GenVault exists check failed: {detail}")
    return res.json()

