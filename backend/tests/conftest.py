import sys
from pathlib import Path

_backend = Path(__file__).resolve().parent.parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

import pytest
from domain.workflow import WorkflowDefinition, WorkflowVersion


SAMPLE_WORKFLOW_GRAPH = {
    "3": {
        "class_type": "KSampler",
        "inputs": {"seed": 12345, "steps": 20, "cfg": 7.5},
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "a photo"},
        "_meta": {"title": "Prompt"},
    },
    "7": {
        "class_type": "SaveImage",
        "inputs": {},
    },
}


@pytest.fixture
def sample_workflow_graph():
    return dict(SAMPLE_WORKFLOW_GRAPH)


@pytest.fixture
def mock_workflow_repo():
    definitions: dict[str, WorkflowDefinition] = {}
    versions: list[WorkflowVersion] = []

    class MockRepo:
        def get_workflow_by_name(self, name: str) -> WorkflowDefinition | None:
            for w in definitions.values():
                if w.name == name:
                    return w
            return None

        def get_latest_version(self, workflow_id: str) -> WorkflowVersion | None:
            candidates = [v for v in versions if v.workflow_id == workflow_id]
            if not candidates:
                return None
            return max(candidates, key=lambda v: v.version)

        def create_workflow_definition(
            self, id: str, name: str, created_at: int, *, conn=None, created_from_image_import: bool = False
        ) -> WorkflowDefinition:
            w = WorkflowDefinition(id=id, name=name, created_at=created_at)
            definitions[id] = w
            return w

        def create_workflow_version(
            self,
            id: str,
            workflow_id: str,
            version: int,
            graph_hash: str,
            original_graph_json: str,
            detected_inputs_json: str,
            detected_outputs_json: str,
            created_at: int,
            *,
            conn=None,
        ) -> WorkflowVersion:
            v = WorkflowVersion(
                id=id,
                workflow_id=workflow_id,
                version=version,
                graph_hash=graph_hash,
                original_graph_json=original_graph_json,
                detected_inputs_json=detected_inputs_json,
                detected_outputs_json=detected_outputs_json,
                created_at=created_at,
            )
            versions.append(v)
            return v

        def run_in_transaction(self, fn):
            return fn(None)

    return MockRepo()


@pytest.fixture
def client(tmp_path):
    from db.init import init_db
    from fastapi.testclient import TestClient
    from repositories.sqlite import (
        SqliteWorkflowRepository,
        SqliteWorkflowAppRepository,
        SqliteRunRepository,
        SqliteProjectRepository,
        SqliteAppPresetRepository,
        SqliteUserRepository,
    )
    from services.workflow_import_service import WorkflowImportService
    from services.media_storage_service import MediaStorageService
    from run_queue_state import RunQueueState

    import main
    import dependencies

    db_path = str(tmp_path / "api_test.db")
    init_db(db_path)

    workflow_repo = SqliteWorkflowRepository(db_path)
    app_repo = SqliteWorkflowAppRepository(db_path)
    run_repo = SqliteRunRepository(db_path)
    project_repo = SqliteProjectRepository(db_path)
    preset_repo = SqliteAppPresetRepository(db_path)
    user_repo = SqliteUserRepository(db_path)
    import_service = WorkflowImportService(workflow_repo)
    media_storage_service = MediaStorageService(run_repo, project_repo, app_repo, workflow_repo)

    dependencies._db_path = db_path
    dependencies._workflow_repo = workflow_repo
    dependencies._app_repo = app_repo
    dependencies._run_repo = run_repo
    dependencies._project_repo = project_repo
    dependencies._preset_repo = preset_repo
    dependencies._user_repo = user_repo
    dependencies._import_service = import_service
    dependencies._media_storage_service = media_storage_service
    dependencies._executor = None
    dependencies._run_queue_state = RunQueueState()

    with TestClient(main.app) as c:
        yield c
