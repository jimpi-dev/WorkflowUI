import os
from pathlib import Path

from db.init import init_db
from repositories.sqlite import (
    SqliteWorkflowRepository,
    SqliteWorkflowAppRepository,
    SqliteRunRepository,
    SqliteProjectRepository,
    SqliteAppPresetRepository,
)
from services.workflow_import_service import WorkflowImportService
from services.media_storage_service import MediaStorageService
from services.run_executor import RunExecutor
from services.comfyui_info import normalize_comfy_url as _normalize_comfy_url

from run_queue_state import RunQueueState

COMFY_URL = _normalize_comfy_url(os.environ.get("COMFYUI_URL", "http://localhost:8188/"))
INPUT_DATA_DIR = Path(os.environ.get("INPUT_DATA_DIR", "input_data")).resolve()

_db_path: str | None = None
_workflow_repo: SqliteWorkflowRepository | None = None
_app_repo: SqliteWorkflowAppRepository | None = None
_run_repo: SqliteRunRepository | None = None
_project_repo: SqliteProjectRepository | None = None
_preset_repo: SqliteAppPresetRepository | None = None
_import_service: WorkflowImportService | None = None
_media_storage_service: MediaStorageService | None = None
_executor: RunExecutor | None = None
_run_queue_state: RunQueueState | None = None


def get_db():
    global _db_path, _workflow_repo, _app_repo, _run_repo, _project_repo, _preset_repo, _import_service, _media_storage_service, _executor
    if _db_path is None:
        _db_path = init_db(os.environ.get("WORKFLOWUI_DB_PATH") or None)
        _workflow_repo = SqliteWorkflowRepository(_db_path)
        _app_repo = SqliteWorkflowAppRepository(_db_path)
        _run_repo = SqliteRunRepository(_db_path)
        _project_repo = SqliteProjectRepository(_db_path)
        _preset_repo = SqliteAppPresetRepository(_db_path)
        _import_service = WorkflowImportService(_workflow_repo)
        _media_storage_service = MediaStorageService(_run_repo, _project_repo, _app_repo, _workflow_repo)
    if _media_storage_service is None and _run_repo is not None:
        _media_storage_service = MediaStorageService(_run_repo, _project_repo, _app_repo, _workflow_repo)
    if _executor is None:
        _executor = RunExecutor(COMFY_URL, INPUT_DATA_DIR)
    return _db_path, _workflow_repo, _app_repo, _run_repo, _project_repo, _preset_repo, _import_service


def get_media_storage_service() -> MediaStorageService:
    get_db()
    assert _media_storage_service is not None
    return _media_storage_service


def get_executor() -> RunExecutor:
    get_db()
    assert _executor is not None
    return _executor


def get_run_queue_state() -> RunQueueState:
    global _run_queue_state
    if _run_queue_state is None:
        _run_queue_state = RunQueueState()
    return _run_queue_state
