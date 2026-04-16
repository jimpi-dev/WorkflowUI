from __future__ import annotations

import json
from typing import Any, Protocol

from domain.app import WorkflowApp
from version import ENGINE_VERSION
from domain.project import Project
from domain.run import Run
from domain.workflow import WorkflowDefinition, WorkflowVersion


class RunRepo(Protocol):
    def get_run(self, run_id: str) -> Run | None: ...


class WorkflowRepo(Protocol):
    def get_workflow_version(self, version_id: str) -> WorkflowVersion | None: ...
    def get_workflow_definition(self, workflow_id: str) -> WorkflowDefinition | None: ...


class AppRepo(Protocol):
    def get_app_by_id(self, app_id: str) -> WorkflowApp | None: ...


class ProjectRepo(Protocol):
    def get_project(self, project_id: str) -> Project | None: ...


def build_workflowui_metadata_payload(
    run_id: str,
    run_repo: RunRepo,
    workflow_repo: WorkflowRepo,
    app_repo: AppRepo,
    project_repo: ProjectRepo,
) -> dict[str, Any] | None:
    run = run_repo.get_run(run_id)
    if not run:
        return None
    version = workflow_repo.get_workflow_version(run.workflow_version_id)
    if not version:
        return None
    definition = workflow_repo.get_workflow_definition(version.workflow_id)
    if not definition:
        return None
    app: WorkflowApp | None = None
    if run.app_id:
        app = app_repo.get_app_by_id(run.app_id)

    def _parse(s: str | None) -> Any:
        if not s:
            return None
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return None

    workflow_payload = {
        "name": definition.name,
        "graph": _parse(version.original_graph_json),
        "graph_hash": version.graph_hash,
        "detected_inputs": _parse(version.detected_inputs_json),
        "detected_outputs": _parse(version.detected_outputs_json),
    }
    if workflow_payload["graph"] is None:
        return None

    app_payload: dict[str, Any] | None = None
    if app:
        app_payload = {
            "slug": app.slug,
            "title": app.title,
            "description": app.description,
            "app_version": getattr(app, "app_version", "1.0.0"),
            "ui_config": _parse(app.ui_config_json),
            "default_inputs": _parse(app.default_inputs_json),
            "default_outputs": _parse(app.default_outputs_json),
            "is_public": app.is_public,
            "comfyui_url": app.comfyui_url,
            "supported_input_kinds": _parse(app.supported_input_kinds_json),
        }
    else:
        app_payload = {
            "slug": "",
            "title": "",
            "description": None,
            "app_version": "1.0.0",
            "ui_config": {},
            "default_inputs": None,
            "default_outputs": None,
            "is_public": False,
            "comfyui_url": None,
            "supported_input_kinds": None,
        }

    payload = {
        "v": 1,
        "engine_version": ENGINE_VERSION,
        "workflow_version_id": run.workflow_version_id,
        "app_id": run.app_id,
        "workflow": workflow_payload,
        # Backward-compatible aliases used by older sidecar helpers/tests.
        "comfy_api_prompt": workflow_payload["graph"],
        "comfy_ui_workflow": None,
        "workflow_hash": version.graph_hash,
        "app": app_payload,
        "run_id": run.id,
        "input_snapshot": _parse(run.input_snapshot_json),
        "metadata_snapshot": _parse(run.metadata_snapshot_json),
    }
    return payload


def workflowui_metadata_to_json_string(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def comfy_sidecar_json_string(payload: dict[str, Any]) -> str:
    """Legacy Comfy sidecar format kept for backward compatibility."""
    prompt = payload.get("comfy_api_prompt")
    if prompt is None:
        workflow = payload.get("workflow")
        if isinstance(workflow, dict):
            prompt = workflow.get("graph")
    sidecar = {
        "prompt": prompt,
        "workflow": payload.get("comfy_ui_workflow"),
    }
    return json.dumps(sidecar, ensure_ascii=True, separators=(",", ":"))
