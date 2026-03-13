from dataclasses import dataclass

@dataclass(frozen=True)
class WorkflowApp:
    """UI abstraction over a workflow version. Slug, ui_config, default inputs/outputs."""
    id: str
    workflow_version_id: str
    slug: str
    title: str
    description: str | None
    ui_config_json: str
    default_inputs_json: str | None
    default_outputs_json: str | None
    is_public: bool
    created_at: int
    app_version: str = "1.0.0"
    comfyui_url: str | None = None
    supported_input_kinds_json: str | None = None
    header_color: str | None = None
    tags_json: str | None = None
    created_from_image_import: bool = False
    embed_workflowui_metadata_on_download: bool | None = None
    embed_workflowui_metadata_on_save: bool | None = None
