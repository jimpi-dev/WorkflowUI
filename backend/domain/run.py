from dataclasses import dataclass


@dataclass
class Run:
    id: str
    project_id: str
    workflow_version_id: str
    app_id: str | None
    status: str
    created_at: int
    run_group_id: str | None = None
    prompt_id: str | None = None
    seed: int | None = None
    images_json: str | None = None
    media_json: str | None = None
    execution_time: float | None = None
    error: str | None = None
    queue_position: int | None = None
    input_snapshot_json: str | None = None
    metadata_snapshot_json: str | None = None
    comfyui_url: str | None = None
    local_storage_status: str | None = "none"
    remote_status: str | None = "unknown"
    local_path: str | None = None
    deleted_outputs_json: str | None = None
    parent_run_id: str | None = None
    parent_media_id: str | None = None
    root_run_id: str | None = None
    deleted_at: int | None = None
