from typing import Any, Protocol

from domain.workflow import WorkflowDefinition, WorkflowVersion
from domain.app import WorkflowApp
from domain.run import Run
from domain.project import Project
from domain.preset import AppPreset

class WorkflowRepository(Protocol):
    def create_workflow_definition(self, id: str, name: str, created_at: int, *, created_from_image_import: bool = False) -> WorkflowDefinition: ...
    def get_workflow_by_name(self, name: str) -> WorkflowDefinition | None: ...
    def get_latest_version(self, workflow_id: str) -> WorkflowVersion | None: ...
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
    ) -> WorkflowVersion: ...
    def get_workflow_version(self, version_id: str) -> WorkflowVersion | None: ...
    def get_workflow_version_by_workflow_and_version(
        self, workflow_id: str, version: int
    ) -> WorkflowVersion | None: ...


class WorkflowAppRepository(Protocol):
    def create_app(
        self,
        id: str,
        workflow_version_id: str,
        slug: str,
        title: str,
        description: str | None,
        ui_config_json: str,
        default_inputs_json: str | None,
        default_outputs_json: str | None,
        is_public: bool,
        created_at: int,
        app_version: str = "1.0.0",
        comfyui_url: str | None = None,
        supported_input_kinds_json: str | None = None,
        header_color: str | None = None,
        created_from_image_import: bool = False,
        embed_workflowui_metadata_on_download: bool | None = None,
        embed_workflowui_metadata_on_save: bool | None = None,
    ) -> WorkflowApp: ...
    def get_app_by_slug(self, slug: str) -> WorkflowApp | None: ...
    def get_app_by_id(self, app_id: str) -> WorkflowApp | None: ...
    def get_app_by_workflow_graph_hash(self, graph_hash: str) -> WorkflowApp | None: ...
    def list_public_apps(self) -> list[WorkflowApp]: ...
    def list_all_apps(self) -> list[WorkflowApp]: ...
    def delete_app_by_id(self, app_id: str) -> None: ...


class ProjectRepository(Protocol):
    def create_project(
        self,
        id: str,
        name: str,
        description: str | None,
        created_at: int,
        updated_at: int,
        metadata_json: str | None = None,
        tags_json: str | None = None,
        storage_mode: str | None = "inherit",
        header_color: str | None = None,
    ) -> Project: ...
    def get_project(self, project_id: str) -> Project | None: ...
    def list_projects(
        self,
        tag: str | None = None,
        limit: int = 100,
        archived: bool | None = False,
    ) -> list[Project]: ...
    def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        updated_at: int | None = None,
        metadata_json: str | None = None,
        tags_json: str | None = None,
        storage_mode: str | None = None,
        header_color: str | None = None,
        archived_at: int | None = None,
    ) -> Project | None: ...
    def delete_project(self, project_id: str, *, conn: Any = None) -> bool: ...


class RunRepository(Protocol):
    def create_run(
        self,
        id: str,
        project_id: str,
        workflow_version_id: str,
        app_id: str | None,
        status: str,
        created_at: int,
        prompt_id: str | None = None,
        seed: int | None = None,
        images_json: str | None = None,
        media_json: str | None = None,
        execution_time: float | None = None,
        error: str | None = None,
        queue_position: int | None = None,
        input_snapshot_json: str | None = None,
        metadata_snapshot_json: str | None = None,
        run_group_id: str | None = None,
        comfyui_url: str | None = None,
        local_storage_status: str | None = "none",
        remote_status: str | None = "unknown",
        local_path: str | None = None,
        deleted_outputs_json: str | None = None,
        parent_run_id: str | None = None,
        parent_media_id: str | None = None,
        root_run_id: str | None = None,
    ) -> Run: ...
    def get_run(self, run_id: str) -> Run | None: ...
    def get_run_by_prompt_id(self, prompt_id: str) -> Run | None: ...
    def get_child_runs(self, parent_run_id: str, limit: int = 50) -> list[Run]: ...
    def list_runs_containing_image(
        self, filename: str, subfolder: str, type: str, *, limit: int = 2000
    ) -> list[Run]: ...
    def get_runs_for_app(self, app_id: str, limit: int = 50) -> list[Run]: ...
    def get_last_run_timestamps_for_app_ids(self, app_ids: list[str]) -> dict[str, int]: ...
    def get_runs_by_project(
        self,
        project_id: str,
        *,
        app_id: str | None = None,
        tag: str | None = None,
        workflow_version_id: str | None = None,
        since_ts: int | None = None,
        until_ts: int | None = None,
        meta_q: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Run]: ...
    def count_runs_by_project(self, project_id: str) -> int: ...
    def count_runs_by_project_filtered(
        self,
        project_id: str,
        *,
        app_id: str | None = None,
        workflow_version_id: str | None = None,
        since_ts: int | None = None,
        until_ts: int | None = None,
        meta_q: str | None = None,
    ) -> int: ...
    def count_run_rows_by_project_filtered(
        self,
        project_id: str,
        *,
        app_id: str | None = None,
        workflow_version_id: str | None = None,
        since_ts: int | None = None,
        until_ts: int | None = None,
        meta_q: str | None = None,
    ) -> int: ...
    def update_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        prompt_id: str | None = None,
        seed: int | None = None,
        images_json: str | None = None,
        media_json: str | None = None,
        execution_time: float | None = None,
        error: str | None = None,
        queue_position: int | None = None,
        local_storage_status: str | None = None,
        remote_status: str | None = None,
        local_path: str | None = None,
        metadata_snapshot_json: str | None = None,
        deleted_outputs_json: str | None = None,
        deleted_at: int | None = None,
    ) -> None: ...
    def delete_run(self, run_id: str) -> bool: ...
    def delete_runs_by_project(
        self, project_id: str, *, conn: Any = None
    ) -> int: ...


class AppPresetRepository(Protocol):
    def list_by_app_id(self, app_id: str) -> list[AppPreset]: ...
    def create(
        self,
        id: str,
        app_id: str,
        name: str,
        description: str | None,
        keys_json: str,
        values_json: str,
        created_at: int,
    ) -> AppPreset: ...
    def get_by_id(self, preset_id: str) -> AppPreset | None: ...
    def delete(self, preset_id: str) -> bool: ...
