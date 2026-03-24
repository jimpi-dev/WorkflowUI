import json
import traceback
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, Response

from authz import require_user
from services.workflow_analyzer import analyze_workflow

from dependencies import get_db

router = APIRouter(dependencies=[Depends(require_user)])

IMAGE_OUTPUT_NODE_TYPES = {"SaveImage", "Save Image", "Save Image (api)", "SaveImageNode"}
VIDEO_OUTPUT_NODE_TYPES = {"VHS_VideoCombine"}
AUDIO_OUTPUT_NODE_TYPES = {"SaveAudioMP3"}

def _count_image_outputs(workflow: dict) -> int:
    n = 0
    for node in workflow.values():
        if isinstance(node, dict) and node.get("class_type") in IMAGE_OUTPUT_NODE_TYPES:
            n += 1
    return n


def _count_video_outputs(workflow: dict) -> int:
    n = 0
    for node in workflow.values():
        if isinstance(node, dict) and node.get("class_type") in VIDEO_OUTPUT_NODE_TYPES:
            n += 1
    return n


def _count_audio_outputs(workflow: dict) -> int:
    n = 0
    for node in workflow.values():
        if isinstance(node, dict) and node.get("class_type") in AUDIO_OUTPUT_NODE_TYPES:
            n += 1
    return n


@router.get("/workflow-definitions")
def list_workflow_definitions(db=Depends(get_db)):
    workflow_repo = db[1]
    definitions_with_counts = workflow_repo.list_workflow_definitions_with_app_counts()
    return [
        {
            "id": d.id,
            "name": d.name,
            "created_at": d.created_at,
            "app_count": app_count,
            "version_count": version_count,
            "latest_version_id": latest_version_id,
            "created_from_image_import": getattr(d, "created_from_image_import", False),
        }
        for d, app_count, version_count, latest_version_id in definitions_with_counts
    ]


@router.get("/workflow-versions/{version_id}")
def get_workflow_version_detail(version_id: str, db=Depends(get_db)):
    workflow_repo = db[1]
    v = workflow_repo.get_workflow_version(version_id)
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    graph = json.loads(v.original_graph_json)
    analyzed = analyze_workflow(graph)
    internal_nodes = analyzed.get("internal_nodes") or []
    return {
        "id": v.id,
        "workflow_id": v.workflow_id,
        "version": v.version,
        "graph_hash": v.graph_hash,
        "detected_inputs": json.loads(v.detected_inputs_json),
        "detected_outputs": json.loads(v.detected_outputs_json),
        "internal_nodes": internal_nodes,
        "created_at": v.created_at,
    }


@router.get("/workflow-versions/{version_id}/graph")
def get_workflow_version_graph(version_id: str, db=Depends(get_db)):
    workflow_repo = db[1]
    v = workflow_repo.get_workflow_version(version_id)
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    return json.loads(v.original_graph_json)


@router.get("/workflow-definitions/{workflow_id}")
def get_workflow_definition_detail(workflow_id: str, db=Depends(get_db)):
    workflow_repo = db[1]
    app_repo = db[2]
    wf = workflow_repo.get_workflow_definition(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    versions = workflow_repo.list_versions(workflow_id)
    versions_with_apps = []
    for v in versions:
        apps = app_repo.get_apps_by_workflow_version_id(v.id)
        versions_with_apps.append({
            "id": v.id,
            "workflow_id": v.workflow_id,
            "version": v.version,
            "graph_hash": v.graph_hash,
            "created_at": v.created_at,
            "apps": [
                {"id": a.id, "slug": a.slug, "title": a.title, "is_public": a.is_public, "created_from_image_import": getattr(a, "created_from_image_import", False)}
                for a in apps
            ],
        })
    return {
        "id": wf.id,
        "name": wf.name,
        "created_at": wf.created_at,
        "versions": versions_with_apps,
        "created_from_image_import": getattr(wf, "created_from_image_import", False),
    }


@router.get("/workflow-definitions/{workflow_id}/download")
def download_workflow_definition(workflow_id: str, db=Depends(get_db)):
    workflow_repo = db[1]
    wf = workflow_repo.get_workflow_definition(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    latest = workflow_repo.get_latest_version(workflow_id)
    if not latest:
        raise HTTPException(status_code=404, detail="Workflow has no versions to download")
    graph = json.loads(latest.original_graph_json)
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in wf.name).strip() or "workflow"
    filename = f"{safe_name}.json"
    return Response(
        content=json.dumps(graph, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/workflow-definitions/{workflow_id}")
def delete_workflow_definition(workflow_id: str, db=Depends(get_db)):
    _, workflow_repo, app_repo, run_repo, _, _, _ = db
    wf = workflow_repo.get_workflow_definition(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    versions = workflow_repo.list_versions(workflow_id)
    version_ids = [v.id for v in versions]
    app_ids = []
    for vid in version_ids:
        for app in app_repo.get_apps_by_workflow_version_id(vid):
            app_ids.append(app.id)
    if app_ids:
        raise HTTPException(
            status_code=400,
            detail="Workflow has apps; delete all apps from this workflow first, then you can delete the workflow.",
        )
    run_repo.null_app_ids(app_ids)
    app_repo.delete_apps_by_workflow_version_ids(version_ids)
    workflow_repo.set_workflow_deleted_at(workflow_id, int(time.time() * 1000))
    return {"ok": True}


@router.get("/workflow/{workflow_id}")
def get_workflow(workflow_id: str):
    try:
        path = Path("workflows") / f"{workflow_id}.json"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Workflow not found")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading workflow: {e!s}")


@router.get("/workflows")
def list_workflows():
    files = Path("workflows").glob("*.json")
    result = []
    for f in sorted(files):
        item = {"id": f.stem, "label": f.stem.replace("_", " ")}
        try:
            with open(f, "r", encoding="utf-8") as fp:
                wf = json.load(fp)
            item["output_count"] = _count_image_outputs(wf) + _count_video_outputs(wf) + _count_audio_outputs(wf)
        except Exception:
            item["output_count"] = 0
        result.append(item)
    return result
