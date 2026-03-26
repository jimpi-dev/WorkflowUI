import json
import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File

from services.workflow_import_service import IdempotentImport
from services.workflow_convert import convert_workflow_via_comfy, is_api_format_prompt
from services.comfyui_workflow_fetch import fetch_workflow_from_comfyui

logger = logging.getLogger(__name__)
from services.png_metadata import read_workflowui_chunk
from services.mp3_metadata import read_workflowui_metadata as read_workflowui_metadata_mp3
from services.mp4_metadata import read_workflowui_metadata as read_workflowui_metadata_mp4
from version import ENGINE_VERSION

from dependencies import get_db, COMFY_URL

router = APIRouter()

def _find_available_workflow_name(base_name: str, workflow_repo) -> str:
    candidate = (base_name or "Workflow").strip()
    if not workflow_repo.get_workflow_by_name(candidate):
        return candidate
    n = 1
    while workflow_repo.get_workflow_by_name(f"{candidate}_{n}"):
        n += 1
    return f"{candidate}_{n}"


def _find_available_slug(base_slug: str, app_repo) -> str:
    candidate = (base_slug or "app").strip().lower().replace(" ", "-")
    if not candidate:
        candidate = "app"
    if not app_repo.get_app_by_slug(candidate):
        return candidate
    n = 1
    while app_repo.get_app_by_slug(f"{candidate}_{n}"):
        n += 1
    return f"{candidate}_{n}"


def _import_from_workflowui_payload(payload: dict, db):
    _, workflow_repo, app_repo, run_repo, project_repo, _, import_service = db
    wv_id = payload.get("workflow_version_id")
    app_id = payload.get("app_id")
    if wv_id and app_id:
        app = app_repo.get_app_by_id(app_id)
        version = workflow_repo.get_workflow_version(wv_id)
        if app and version:
            definition = workflow_repo.get_workflow_definition(version.workflow_id) if version else None
            out = {
                "action": "open",
                "app_slug": app.slug,
                "app_title": app.title if app else None,
                "workflow_name": definition.name if definition else None,
            }
            if payload.get("input_snapshot") is not None:
                out["input_snapshot"] = payload["input_snapshot"]
            return out
    workflow = payload.get("workflow")
    app_snapshot = payload.get("app")
    if not isinstance(workflow, dict) or not isinstance(app_snapshot, dict):
        return {"action": "ignored", "reason": "invalid_snapshot"}
    graph = workflow.get("graph")
    if not isinstance(graph, dict):
        return {"action": "ignored", "reason": "invalid_snapshot"}
    manifest = payload.get("manifest")
    parsed_manifest = None
    if isinstance(manifest, dict):
        from services.manifest_parser import parse_manifest, validate_manifest_for_install
        parsed_manifest = parse_manifest(manifest)
        if parsed_manifest.manifest_version and parsed_manifest.engine_compat:
            valid, err = validate_manifest_for_install(parsed_manifest, ENGINE_VERSION)
            if not valid:
                return {"action": "rejected", "reason": "incompatible_manifest", "detail": err}
        if parsed_manifest.workflow_hash:
            from services.graph_hash import graph_hash
            computed = graph_hash(graph)
            if computed != parsed_manifest.workflow_hash:
                return {"action": "rejected", "reason": "workflow_hash_mismatch", "detail": "Workflow content does not match manifest workflow_hash"}
    from services.graph_hash import graph_hash
    computed_hash = (parsed_manifest.workflow_hash if parsed_manifest and parsed_manifest.workflow_hash else graph_hash(graph))
    existing_app = app_repo.get_app_by_workflow_graph_hash(computed_hash)
    if existing_app:
        version = workflow_repo.get_workflow_version(existing_app.workflow_version_id) if existing_app.workflow_version_id else None
        definition = workflow_repo.get_workflow_definition(version.workflow_id) if version else None
        out = {
            "action": "open",
            "app_slug": existing_app.slug,
            "app_title": existing_app.title,
            "workflow_name": definition.name if definition else None,
        }
        if payload.get("input_snapshot") is not None:
            out["input_snapshot"] = payload["input_snapshot"]
        return out
    wf_name = (workflow.get("name") or "Workflow").strip()
    resolved_name = _find_available_workflow_name(wf_name, workflow_repo)
    result = import_service.import_workflow(resolved_name, graph, created_from_image_import=True)
    base_slug = (app_snapshot.get("slug") or "app").strip()
    resolved_slug = _find_available_slug(base_slug, app_repo)
    app_title = (app_snapshot.get("title") or resolved_slug).strip()
    app_description = app_snapshot.get("description")
    ui_config = app_snapshot.get("ui_config")
    if not isinstance(ui_config, dict):
        ui_config = {}
    ui_config_json = json.dumps(ui_config)
    default_inputs = app_snapshot.get("default_inputs")
    default_outputs = app_snapshot.get("default_outputs")
    default_inputs_json = json.dumps(default_inputs) if default_inputs is not None else None
    default_outputs_json = json.dumps(default_outputs) if default_outputs is not None else None
    is_public = bool(app_snapshot.get("is_public", False))
    comfyui_url = app_snapshot.get("comfyui_url") if app_snapshot.get("comfyui_url") else None
    supported = app_snapshot.get("supported_input_kinds")
    supported_input_kinds_json = json.dumps(supported) if supported is not None else None
    app_version = (app_snapshot.get("app_version") or "1.0.0").strip() if isinstance(app_snapshot.get("app_version"), str) else "1.0.0"
    if parsed_manifest and parsed_manifest.app_version:
        app_version = parsed_manifest.app_version
    created_at_ms = int(time.time() * 1000)
    new_app_id = str(uuid.uuid4())
    app_repo.create_app(
        new_app_id,
        result.workflow_version_id,
        resolved_slug,
        app_title,
        app_description,
        ui_config_json,
        default_inputs_json,
        default_outputs_json,
        is_public,
        created_at_ms,
        app_version=app_version,
        comfyui_url=comfyui_url,
        supported_input_kinds_json=supported_input_kinds_json,
        created_from_image_import=True,
    )
    out = {
        "action": "restored",
        "workflow_id": result.workflow_id,
        "workflow_version_id": result.workflow_version_id,
        "app_id": new_app_id,
        "app_slug": resolved_slug,
        "app_title": app_title,
        "workflow_name": wf_name,
        "resolved_workflow_name": resolved_name,
        "resolved_slug": resolved_slug,
    }
    if payload.get("input_snapshot") is not None:
        out["input_snapshot"] = payload["input_snapshot"]
    return out


@router.post("/import/preview")
def post_import_preview(body: dict, db=Depends(get_db)):
    name = body.get("name")
    graph = body.get("graph")
    use_workflow_ui_link = body.get("use_workflow_ui_link") is True
    if not name or not isinstance(name, str):
        raise HTTPException(status_code=400, detail="name is required")
    if not isinstance(graph, dict) or not graph:
        raise HTTPException(status_code=400, detail="graph must be a non-empty object")
    _, _, _, _, _, _, import_service = db
    try:
        return import_service.preview_import(name, graph, use_workflow_ui_link=use_workflow_ui_link)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import")
def post_import(body: dict, db=Depends(get_db)):
    name = body.get("name")
    graph = body.get("graph")
    force_new_version = body.get("force_new_version") is True
    use_workflow_ui_link = body.get("use_workflow_ui_link") is True
    if not name or not isinstance(name, str):
        raise HTTPException(status_code=400, detail="name is required")
    if not isinstance(graph, dict) or not graph:
        raise HTTPException(status_code=400, detail="graph must be a non-empty object")
    conversion_warning = None
    if graph.get("nodes") is not None and COMFY_URL:
        logger.info(
            "Import (POST /import): converting UI workflow to API format (COMFY_URL=%s)",
            COMFY_URL.rstrip("/"),
        )
        api_graph = convert_workflow_via_comfy(COMFY_URL, graph)
        if api_graph is not None:
            graph = api_graph
            logger.info("Import (POST /import): conversion SUCCESS — storing API format (%s nodes).", len(graph))
        else:
            logger.warning(
                "Import (POST /import): conversion FAILED or unavailable — storing UI format. "
                "Generation will retry conversion (may fail or OOM).",
            )
            conversion_warning = (
                "Workflow conversion to API format failed (ComfyUI converter error or unavailable). "
                "Stored in UI format. When you run a generation, conversion will be retried; if it fails again you may see errors or OOM."
            )
    elif graph.get("nodes") is not None and not COMFY_URL:
        logger.info("Import (POST /import): COMFY_URL not set, storing UI format as-is.")
        conversion_warning = (
            "ComfyUI URL not set. Workflow stored in UI format. "
            "Set COMFYUI_URL so conversion runs at import and generation uses API format."
        )
    _, _, _, _, _, _, import_service = db
    try:
        result = import_service.import_workflow(
            name, graph,
            force_new_version=force_new_version,
            use_workflow_ui_link=use_workflow_ui_link,
        )
        out = {
            "workflow_id": result.workflow_id,
            "version": result.version,
            "graph_hash": result.graph_hash,
            "detected_inputs": result.detected_inputs,
            "detected_outputs": result.detected_outputs,
            "internal_nodes": result.internal_nodes,
            "workflow_version_id": result.workflow_version_id,
        }
        if conversion_warning:
            out["warning"] = conversion_warning
        return out
    except IdempotentImport as e:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Import is duplicate of latest version",
                "workflow_id": e.workflow_id,
                "version": e.version,
                "graph_hash": e.graph_hash,
                "workflow_version_id": e.workflow_version_id,
                "detected_inputs": e.detected_inputs,
                "detected_outputs": e.detected_outputs,
                "internal_nodes": e.internal_nodes,
            },
        )


@router.post("/import/from-image")
def post_import_from_image(image: UploadFile = File(..., alias="image"), db=Depends(get_db)):
    if not image.filename or not image.content_type or not image.content_type.startswith("image/"):
        return {"action": "ignored", "reason": "no_workflowui_metadata"}
    try:
        content = image.file.read()
    except Exception:
        return {"action": "ignored", "reason": "no_workflowui_metadata"}
    finally:
        image.file.close()
    raw = read_workflowui_chunk(content)
    if not raw or not raw.strip():
        return {"action": "ignored", "reason": "no_workflowui_metadata"}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"action": "ignored", "reason": "invalid_snapshot"}
    if not isinstance(payload, dict):
        return {"action": "ignored", "reason": "invalid_snapshot"}
    return _import_from_workflowui_payload(payload, db)


@router.post("/import/from-file")
def post_import_from_file(file: UploadFile = File(..., alias="file"), db=Depends(get_db)):
    if not file.filename:
        return {"action": "ignored", "reason": "no_workflowui_metadata"}
    try:
        content = file.file.read()
    except Exception:
        return {"action": "ignored", "reason": "no_workflowui_metadata"}
    finally:
        file.file.close()
    content_type = (file.content_type or "").strip().lower()
    filename_lower = (file.filename or "").lower()
    raw = None
    if content_type.startswith("image/"):
        raw = read_workflowui_chunk(content)
    elif content_type in ("audio/mpeg", "audio/mp3") or filename_lower.endswith(".mp3"):
        raw = read_workflowui_metadata_mp3(content)
    elif content_type.startswith("video/") or filename_lower.endswith(".mp4"):
        raw = read_workflowui_metadata_mp4(content)
    if not raw or not raw.strip():
        return {"action": "ignored", "reason": "no_workflowui_metadata"}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"action": "ignored", "reason": "invalid_snapshot"}
    if not isinstance(payload, dict):
        return {"action": "ignored", "reason": "invalid_snapshot"}
    return _import_from_workflowui_payload(payload, db)


def _minimal_app_payload(workflow_name: str, graph: dict, db) -> dict:
    """Build minimal workflow+app payload for _import_from_workflowui_payload."""
    _, workflow_repo, app_repo, _, _, _, _ = db
    resolved_name = _find_available_workflow_name(workflow_name.strip() or "Imported from ComfyUI", workflow_repo)
    base_slug = (workflow_name.strip() or "app").lower().replace(" ", "-") or "app"
    resolved_slug = _find_available_slug(base_slug, app_repo)
    return {
        "workflow": {"name": resolved_name, "graph": graph},
        "app": {
            "slug": resolved_slug,
            "title": (workflow_name.strip() or resolved_slug).strip(),
            "description": "",
            "ui_config": {},
            "default_inputs": None,
            "default_outputs": None,
            "is_public": False,
        },
    }


def _fetch_workflow_from_comfyui_plugin(workflow_id: str):
    """Fetch workflow in API format from ComfyUI WorkflowUI plugin. Returns (name, graph) or raises HTTPException."""
    return fetch_workflow_from_comfyui(COMFY_URL, workflow_id)


@router.post("/import/from-comfyui")
def post_import_from_comfyui(body: dict, db=Depends(get_db)):
    graph = body.get("graph")
    name = body.get("name")
    comfyui_workflow_id = body.get("comfyui_workflow_id")

    if comfyui_workflow_id and isinstance(comfyui_workflow_id, str) and comfyui_workflow_id.strip():
        name, graph = _fetch_workflow_from_comfyui_plugin(comfyui_workflow_id.strip())
        has_nodes = isinstance(graph, dict) and isinstance(graph.get("nodes"), list)
        logger.info(
            "Import from ComfyUI: fetched workflow '%s', graph has %s nodes (UI format=%s)",
            name,
            len(graph.get("nodes", [])) if has_nodes else "N/A",
            has_nodes,
        )
    elif isinstance(graph, dict) and graph:
        name = (name or "Imported from ComfyUI").strip() or "Imported from ComfyUI"
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'graph' (with optional 'name') or 'comfyui_workflow_id'",
        )

    conversion_warning = None
    if isinstance(graph, dict) and graph.get("nodes") is not None and COMFY_URL:
        logger.info(
            "Import from ComfyUI: converting UI workflow to API format (COMFY_URL=%s)",
            COMFY_URL.rstrip("/"),
        )
        api_graph = convert_workflow_via_comfy(COMFY_URL, graph)
        if api_graph is not None:
            graph = api_graph
            logger.info(
                "Import from ComfyUI: conversion SUCCESS — storing API format (%s nodes).",
                len(graph),
            )
        else:
            logger.warning(
                "Import from ComfyUI: conversion FAILED or unavailable — storing UI format. "
                "Run may use built-in conversion (possible OOM).",
            )
            conversion_warning = (
                "Workflow conversion to API format failed at import (ComfyUI converter error or unavailable). "
                "Stored in UI format. Generation will retry conversion; if it fails again you may see errors or OOM."
            )
    else:
        if isinstance(graph, dict) and is_api_format_prompt(graph):
            logger.info("Import from ComfyUI: graph already API format (%s nodes), no conversion.", len(graph))
        elif isinstance(graph, dict) and graph.get("nodes") is not None and not COMFY_URL:
            logger.info("Import from ComfyUI: COMFY_URL not set, skipping convert; storing as-is.")
            conversion_warning = (
                "ComfyUI URL not set at import. Workflow stored in UI format. "
                "Set COMFYUI_URL so conversion runs at import and generation uses API format."
            )

    payload = _minimal_app_payload(name, graph, db)
    out = _import_from_workflowui_payload(payload, db)
    if conversion_warning and isinstance(out, dict):
        out["warning"] = conversion_warning
    return out
