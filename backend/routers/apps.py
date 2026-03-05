import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Depends, Response

from config import get_workflowui_embed_config
from services.workflow_analyzer import analyze_workflow, apply_default_inputs_to_graph, extract_form_label_from_graph
from services.workflow_analyzer import _normalize_to_api_format as normalize_workflow_to_api_format

from dependencies import get_db
from routers.import_ import _find_available_slug

MEDIA_INPUT_TYPES = frozenset({"image", "video", "audio"})
logger = logging.getLogger(__name__)

router = APIRouter()


def _derived_supported_input_kinds(detected_inputs: list) -> list[str]:
    if not detected_inputs or not isinstance(detected_inputs, list):
        return []
    seen: set[str] = set()
    for inp in detected_inputs:
        if not isinstance(inp, dict):
            continue
        t = inp.get("type")
        if isinstance(t, str) and t.strip().lower() in MEDIA_INPUT_TYPES:
            seen.add(t.strip().lower())
    return sorted(seen)


def _app_supported_input_kinds(app, workflow_repo) -> list[str] | None:
    if app.supported_input_kinds_json:
        try:
            return json.loads(app.supported_input_kinds_json)
        except json.JSONDecodeError:
            pass
    version = workflow_repo.get_workflow_version(app.workflow_version_id) if workflow_repo else None
    if not version or not version.detected_inputs_json:
        return None
    try:
        inputs = json.loads(version.detected_inputs_json)
    except json.JSONDecodeError:
        return None
    derived = _derived_supported_input_kinds(inputs)
    return derived if derived else None


def _resolved_embed_on_download(app) -> bool:
    if getattr(app, "embed_workflowui_metadata_on_download", None) is not None:
        return bool(app.embed_workflowui_metadata_on_download)
    return get_workflowui_embed_config().embed_on_download


def _resolved_embed_on_save(app) -> bool:
    if getattr(app, "embed_workflowui_metadata_on_save", None) is not None:
        return bool(app.embed_workflowui_metadata_on_save)
    return get_workflowui_embed_config().embed_on_save


@router.get("/apps")
def list_apps(db=Depends(get_db)):
    _, workflow_repo, app_repo, run_repo, _, _, _ = db
    apps = app_repo.list_all_apps()
    app_ids = [a.id for a in apps]
    last_used_map = run_repo.get_last_run_timestamps_for_app_ids(app_ids) if app_ids else {}
    return [
        {
            "id": a.id,
            "slug": a.slug,
            "title": a.title,
            "description": a.description,
            "is_public": a.is_public,
            "created_at": a.created_at,
            "last_used": last_used_map.get(a.id),
            "workflow_version_id": a.workflow_version_id,
            "app_version": getattr(a, "app_version", "1.0.0"),
            "supported_input_kinds": _app_supported_input_kinds(a, workflow_repo),
            "header_color": a.header_color,
            "created_from_image_import": getattr(a, "created_from_image_import", False),
        }
        for a in apps
    ]


@router.post("/apps")
def post_apps(body: dict, db=Depends(get_db)):
    workflow_version_id = body.get("workflow_version_id")
    slug = body.get("slug")
    title = body.get("title")
    ui_config = body.get("ui_config")
    description = body.get("description")
    default_inputs = body.get("default_inputs")
    default_outputs = body.get("default_outputs")
    is_public = body.get("is_public", True)
    if not workflow_version_id or not slug or not title:
        raise HTTPException(status_code=400, detail="workflow_version_id, slug, and title are required")
    if not isinstance(ui_config, dict):
        ui_config = {}
    _, workflow_repo, app_repo, _, _, _, _ = db
    wv = workflow_repo.get_workflow_version(workflow_version_id)
    if not wv:
        raise HTTPException(status_code=404, detail="workflow_version_id not found")
    existing = app_repo.get_app_by_slug(slug)
    if existing:
        raise HTTPException(status_code=409, detail="slug already in use")
    app_id = str(uuid.uuid4())
    created_at = int(time.time() * 1000)
    ui_config_json = json.dumps(ui_config)
    default_inputs_json = json.dumps(default_inputs) if default_inputs is not None else None
    default_outputs_json = json.dumps(default_outputs) if default_outputs is not None else None
    comfyui_url = body.get("comfyui_url") if isinstance(body.get("comfyui_url"), str) else None
    supported_input_kinds = body.get("supported_input_kinds")
    supported_input_kinds_json = json.dumps(supported_input_kinds) if supported_input_kinds is not None else None
    header_color = body.get("header_color")
    if header_color is not None and not isinstance(header_color, str):
        header_color = None
    if header_color is not None and isinstance(header_color, str) and not header_color.strip():
        header_color = None
    embed_on_download = body.get("embed_workflowui_metadata_on_download")
    embed_on_save = body.get("embed_workflowui_metadata_on_save")
    if embed_on_download is not None and not isinstance(embed_on_download, bool):
        embed_on_download = None
    if embed_on_save is not None and not isinstance(embed_on_save, bool):
        embed_on_save = None
    app_version = (body.get("app_version") or "1.0.0").strip() if isinstance(body.get("app_version"), str) else "1.0.0"
    created = app_repo.create_app(
        app_id,
        workflow_version_id,
        slug.strip(),
        title,
        description,
        ui_config_json,
        default_inputs_json,
        default_outputs_json,
        bool(is_public),
        created_at,
        app_version=app_version,
        comfyui_url=comfyui_url or None,
        supported_input_kinds_json=supported_input_kinds_json,
        header_color=header_color.strip() if header_color else None,
        embed_workflowui_metadata_on_download=embed_on_download,
        embed_workflowui_metadata_on_save=embed_on_save,
    )
    embed_cfg = get_workflowui_embed_config()
    return {
        "id": created.id,
        "slug": created.slug,
        "workflow_version_id": created.workflow_version_id,
        "title": created.title,
        "description": created.description,
        "ui_config": json.loads(created.ui_config_json),
        "default_inputs": json.loads(created.default_inputs_json) if created.default_inputs_json else None,
        "default_outputs": json.loads(created.default_outputs_json) if created.default_outputs_json else None,
        "is_public": created.is_public,
        "created_at": created.created_at,
        "comfyui_url": created.comfyui_url,
        "supported_input_kinds": json.loads(created.supported_input_kinds_json) if created.supported_input_kinds_json else None,
        "header_color": created.header_color,
        "embedWorkflowuiMetadataOnDownload": created.embed_workflowui_metadata_on_download if created.embed_workflowui_metadata_on_download is not None else embed_cfg.embed_on_download,
        "embedWorkflowuiMetadataOnSave": created.embed_workflowui_metadata_on_save if created.embed_workflowui_metadata_on_save is not None else embed_cfg.embed_on_save,
    }


@router.get("/apps/public")
def list_public_apps(db=Depends(get_db)):
    _, workflow_repo, app_repo, _, _, _, _ = db
    apps = app_repo.list_public_apps()
    return [
        {
            "id": a.slug,
            "slug": a.slug,
            "title": a.title,
            "description": a.description,
            "app_version": getattr(a, "app_version", "1.0.0"),
            "supported_input_kinds": _app_supported_input_kinds(a, workflow_repo),
            "header_color": a.header_color,
        }
        for a in apps
    ]


@router.patch("/apps/{slug}")
def patch_app(slug: str, body: dict, db=Depends(get_db)):
    _, _, app_repo, _, _, _, _ = db
    app = app_repo.get_app_by_slug(slug)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    kwargs = {}
    if "title" in body:
        kwargs["title"] = body["title"]
    if "description" in body:
        kwargs["description"] = body["description"]
    if "ui_config" in body:
        kwargs["ui_config_json"] = json.dumps(body["ui_config"])
    if "default_inputs" in body:
        kwargs["default_inputs_json"] = json.dumps(body["default_inputs"]) if body["default_inputs"] is not None else None
    if "default_outputs" in body:
        kwargs["default_outputs_json"] = json.dumps(body["default_outputs"]) if body["default_outputs"] is not None else None
    if "is_public" in body:
        kwargs["is_public"] = bool(body["is_public"])
    if "comfyui_url" in body:
        kwargs["comfyui_url"] = body["comfyui_url"] if isinstance(body["comfyui_url"], str) else None
    if "supported_input_kinds" in body:
        kwargs["supported_input_kinds_json"] = json.dumps(body["supported_input_kinds"]) if body["supported_input_kinds"] is not None else None
    if "header_color" in body:
        hc = body["header_color"]
        kwargs["header_color"] = hc.strip() if isinstance(hc, str) and hc.strip() else None
    if "embed_workflowui_metadata_on_download" in body:
        v = body["embed_workflowui_metadata_on_download"]
        kwargs["embed_workflowui_metadata_on_download"] = bool(v) if isinstance(v, bool) else None
    if "embed_workflowui_metadata_on_save" in body:
        v = body["embed_workflowui_metadata_on_save"]
        kwargs["embed_workflowui_metadata_on_save"] = bool(v) if isinstance(v, bool) else None
    updated = app_repo.update_app(slug, **kwargs)
    if not updated:
        raise HTTPException(status_code=500, detail="Update failed")
    embed_cfg = get_workflowui_embed_config()
    return {
        "id": updated.id,
        "slug": updated.slug,
        "workflow_version_id": updated.workflow_version_id,
        "title": updated.title,
        "description": updated.description,
        "ui_config": json.loads(updated.ui_config_json),
        "default_inputs": json.loads(updated.default_inputs_json) if updated.default_inputs_json else None,
        "default_outputs": json.loads(updated.default_outputs_json) if updated.default_outputs_json else None,
        "is_public": updated.is_public,
        "created_at": updated.created_at,
        "app_version": getattr(updated, "app_version", "1.0.0"),
        "comfyui_url": updated.comfyui_url,
        "supported_input_kinds": json.loads(updated.supported_input_kinds_json) if updated.supported_input_kinds_json else None,
        "header_color": updated.header_color,
        "embedWorkflowuiMetadataOnDownload": updated.embed_workflowui_metadata_on_download if updated.embed_workflowui_metadata_on_download is not None else embed_cfg.embed_on_download,
        "embedWorkflowuiMetadataOnSave": updated.embed_workflowui_metadata_on_save if updated.embed_workflowui_metadata_on_save is not None else embed_cfg.embed_on_save,
    }


@router.delete("/apps/{slug}")
def delete_app(slug: str, db=Depends(get_db)):
    _, _, app_repo, _, _, preset_repo, _ = db
    app = app_repo.get_app_by_slug(slug)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    for p in preset_repo.list_by_app_id(app.id):
        preset_repo.delete(p.id)
    app_repo.delete_app_by_id(app.id)
    return Response(status_code=204)


@router.post("/apps/{slug}/copy")
def copy_app(slug: str, body: dict | None = None, db=Depends(get_db)):
    body = body or {}
    _, _, app_repo, _, _, _, _ = db
    app = app_repo.get_app_by_slug(slug)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    new_title = (body.get("new_title") or f"Copy of {app.title or slug}").strip() or "Copy of App"
    raw_slug = body.get("new_slug")
    if isinstance(raw_slug, str) and raw_slug.strip():
        base_slug = raw_slug.strip().lower().replace(" ", "-")
    else:
        base_slug = new_title.lower().replace(" ", "-")
    new_slug = _find_available_slug(base_slug, app_repo)
    app_id = str(uuid.uuid4())
    created_at = int(time.time() * 1000)
    created_from_image_import = getattr(app, "created_from_image_import", False)
    created = app_repo.create_app(
        app_id,
        app.workflow_version_id,
        new_slug,
        new_title,
        app.description,
        app.ui_config_json,
        app.default_inputs_json,
        app.default_outputs_json,
        app.is_public,
        created_at,
        comfyui_url=app.comfyui_url,
        supported_input_kinds_json=app.supported_input_kinds_json,
        header_color=app.header_color,
        created_from_image_import=created_from_image_import,
        embed_workflowui_metadata_on_download=app.embed_workflowui_metadata_on_download,
        embed_workflowui_metadata_on_save=app.embed_workflowui_metadata_on_save,
    )
    embed_cfg = get_workflowui_embed_config()
    return {
        "id": created.id,
        "slug": created.slug,
        "workflow_version_id": created.workflow_version_id,
        "title": created.title,
        "description": created.description,
        "ui_config": json.loads(created.ui_config_json),
        "default_inputs": json.loads(created.default_inputs_json) if created.default_inputs_json else None,
        "default_outputs": json.loads(created.default_outputs_json) if created.default_outputs_json else None,
        "is_public": created.is_public,
        "created_at": created.created_at,
        "app_version": created.app_version,
        "comfyui_url": created.comfyui_url,
        "supported_input_kinds": json.loads(created.supported_input_kinds_json) if created.supported_input_kinds_json else None,
        "header_color": created.header_color,
        "embedWorkflowuiMetadataOnDownload": created.embed_workflowui_metadata_on_download if created.embed_workflowui_metadata_on_download is not None else embed_cfg.embed_on_download,
        "embedWorkflowuiMetadataOnSave": created.embed_workflowui_metadata_on_save if created.embed_workflowui_metadata_on_save is not None else embed_cfg.embed_on_save,
    }


@router.get("/app/{slug}")
def get_app_by_slug(slug: str, db=Depends(get_db)):
    _, workflow_repo, app_repo, _, _, _, _ = db
    app = app_repo.get_app_by_slug(slug)
    if not app:
        logger.info("GET /app/%s: app not found in DB", slug)
        raise HTTPException(status_code=404, detail="App not found")
    version = workflow_repo.get_workflow_version(app.workflow_version_id)
    if not version:
        logger.warning("GET /app/%s: app found but workflow_version_id=%s not found", slug, app.workflow_version_id)
        raise HTTPException(status_code=404, detail="Workflow version not found")
    detected_inputs = json.loads(version.detected_inputs_json)
    supported = json.loads(app.supported_input_kinds_json) if app.supported_input_kinds_json else None
    if supported is None:
        supported = _derived_supported_input_kinds(detected_inputs) or None
    graph = json.loads(version.original_graph_json)
    analyzed = analyze_workflow(graph)
    internal_nodes = analyzed.get("internal_nodes") or []
    form_label = extract_form_label_from_graph(graph)
    wv_payload: dict[str, Any] = {
        "graph_hash": version.graph_hash,
        "detected_inputs": detected_inputs,
        "detected_outputs": json.loads(version.detected_outputs_json),
        "internal_nodes": internal_nodes,
    }
    if form_label:
        wv_payload["form_label"] = form_label
    return {
        "workflow_version": wv_payload,
        "app": {
            "id": app.id,
            "slug": app.slug,
            "title": app.title,
            "description": app.description,
            "ui_config": json.loads(app.ui_config_json),
            "default_inputs": json.loads(app.default_inputs_json) if app.default_inputs_json else None,
            "default_outputs": json.loads(app.default_outputs_json) if app.default_outputs_json else None,
            "app_version": getattr(app, "app_version", "1.0.0"),
            "comfyui_url": app.comfyui_url,
            "supported_input_kinds": supported,
            "header_color": app.header_color,
            "created_from_image_import": getattr(app, "created_from_image_import", False),
            "embedWorkflowuiMetadataOnDownload": _resolved_embed_on_download(app),
            "embedWorkflowuiMetadataOnSave": _resolved_embed_on_save(app),
        },
    }


@router.get("/app/{slug}/workflow/download")
def download_app_workflow(slug: str, db=Depends(get_db)):
    _, workflow_repo, app_repo, _, _, _, _ = db
    app = app_repo.get_app_by_slug(slug)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    version = workflow_repo.get_workflow_version(app.workflow_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Workflow version not found")
    graph = json.loads(version.original_graph_json)
    detected_inputs = json.loads(version.detected_inputs_json)
    default_inputs = json.loads(app.default_inputs_json) if app.default_inputs_json else None
    graph = normalize_workflow_to_api_format(graph)
    apply_default_inputs_to_graph(graph, detected_inputs, default_inputs or {})
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in (app.title or "")).strip() or "workflow"
    filename = f"{safe_name}-workflow.json"
    return Response(
        content=json.dumps(graph, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/app/{slug}/presets")
def list_app_presets(slug: str, db=Depends(get_db)):
    _, _, app_repo, _, _, preset_repo, _ = db
    app = app_repo.get_app_by_slug(slug)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    presets = preset_repo.list_by_app_id(app.id)
    return [
        {
            "id": p.id,
            "app_id": p.app_id,
            "name": p.name,
            "description": p.description,
            "keys": json.loads(p.keys_json),
            "values": json.loads(p.values_json),
            "created_at": p.created_at,
        }
        for p in presets
    ]


@router.post("/app/{slug}/presets")
def create_app_preset(slug: str, body: dict[str, Any], db=Depends(get_db)):
    _, _, app_repo, _, _, preset_repo, _ = db
    app = app_repo.get_app_by_slug(slug)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    name = body.get("name")
    if not name or not str(name).strip():
        raise HTTPException(status_code=400, detail="name is required")
    keys = body.get("keys")
    values = body.get("values")
    if not isinstance(keys, list) or not isinstance(values, dict):
        raise HTTPException(status_code=400, detail="keys (array) and values (object) are required")
    preset_id = str(uuid.uuid4())
    created_at = int(time.time() * 1000)
    keys_json = json.dumps(keys)
    values_json = json.dumps(values)
    description = body.get("description")
    if description is not None:
        description = str(description).strip() or None
    preset = preset_repo.create(
        id=preset_id,
        app_id=app.id,
        name=str(name).strip(),
        description=description,
        keys_json=keys_json,
        values_json=values_json,
        created_at=created_at,
    )
    return {
        "id": preset.id,
        "app_id": preset.app_id,
        "name": preset.name,
        "description": preset.description,
        "keys": json.loads(preset.keys_json),
        "values": json.loads(preset.values_json),
        "created_at": preset.created_at,
    }


@router.delete("/app/{slug}/presets/{preset_id}")
def delete_app_preset(slug: str, preset_id: str, db=Depends(get_db)):
    _, _, app_repo, _, _, preset_repo, _ = db
    app = app_repo.get_app_by_slug(slug)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    preset = preset_repo.get_by_id(preset_id)
    if not preset or preset.app_id != app.id:
        raise HTTPException(status_code=404, detail="Preset not found")
    deleted = preset_repo.delete(preset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"ok": True}
