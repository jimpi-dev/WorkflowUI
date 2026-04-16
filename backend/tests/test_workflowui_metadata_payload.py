from __future__ import annotations

import json

from domain.app import WorkflowApp
from domain.run import Run
from domain.workflow import WorkflowDefinition, WorkflowVersion
from services.workflowui_metadata import build_workflowui_metadata_payload, comfy_sidecar_json_string


def test_build_workflowui_metadata_payload_omits_project_id() -> None:
    run = Run(
        id="run-1",
        project_id="source-project-id",
        workflow_version_id="wv-1",
        app_id="app-1",
        status="done",
        created_at=0,
        input_snapshot_json='{"values":{"seed":123}}',
        metadata_snapshot_json='{"master_seed":123}',
    )
    version = WorkflowVersion(
        id="wv-1",
        workflow_id="wf-1",
        version=1,
        graph_hash="hash-123",
        original_graph_json='{"nodes":{}}',
        detected_inputs_json="{}",
        detected_outputs_json="{}",
        created_at=0,
    )
    definition = WorkflowDefinition(id="wf-1", name="TestWorkflow", created_at=0)
    app = WorkflowApp(
        id="app-1",
        workflow_version_id="wv-1",
        slug="test-app",
        title="Test App",
        description=None,
        ui_config_json="{}",
        default_inputs_json=None,
        default_outputs_json=None,
        is_public=False,
        created_at=0,
    )

    class RunRepo:
        def get_run(self, run_id: str) -> Run | None:
            return run if run_id == run.id else None

    class WorkflowRepo:
        def get_workflow_version(self, version_id: str) -> WorkflowVersion | None:
            return version if version_id == version.id else None

        def get_workflow_definition(self, workflow_id: str) -> WorkflowDefinition | None:
            return definition if workflow_id == definition.id else None

    class AppRepo:
        def get_app_by_id(self, app_id: str) -> WorkflowApp | None:
            return app if app_id == app.id else None

    class ProjectRepo:
        def get_project(self, project_id: str):
            raise AssertionError("project_repo should not be called by build_workflowui_metadata_payload")

    payload = build_workflowui_metadata_payload(
        run_id=run.id,
        run_repo=RunRepo(),
        workflow_repo=WorkflowRepo(),
        app_repo=AppRepo(),
        project_repo=ProjectRepo(),
    )

    assert payload is not None
    assert "project_id" not in payload
    assert payload.get("comfy_api_prompt") == {"nodes": {}}
    assert payload.get("comfy_ui_workflow") is None
    side = json.loads(comfy_sidecar_json_string(payload))
    assert side["prompt"] == {"nodes": {}}
    assert side["workflow"] is None

