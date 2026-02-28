from dataclasses import dataclass

@dataclass(frozen=True)
class WorkflowDefinition:
    id: str
    name: str
    created_at: int
    deleted_at: int | None = None
    created_from_image_import: bool = False

@dataclass(frozen=True)
class WorkflowVersion:
    id: str
    workflow_id: str
    version: int
    graph_hash: str
    original_graph_json: str
    detected_inputs_json: str
    detected_outputs_json: str
    created_at: int
