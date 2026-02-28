import pytest

from domain.run import Run
from domain.workflow import WorkflowDefinition, WorkflowVersion


def test_run_creation():
    r = Run(
        id="run-1",
        project_id="proj-1",
        workflow_version_id="ver-1",
        app_id=None,
        status="queued",
        created_at=1234567890,
    )
    assert r.id == "run-1"
    assert r.project_id == "proj-1"
    assert r.status == "queued"
    assert r.run_group_id is None
    assert r.queue_position is None
    assert r.local_storage_status == "none"
    assert r.remote_status == "unknown"


def test_run_with_optionals():
    r = Run(
        id="run-2",
        project_id="p",
        workflow_version_id="v",
        app_id="app-1",
        status="done",
        created_at=0,
        run_group_id="grp-1",
        queue_position=2,
        seed=42,
        error="Something failed",
    )
    assert r.run_group_id == "grp-1"
    assert r.queue_position == 2
    assert r.seed == 42
    assert r.error == "Something failed"


def test_workflow_definition_creation():
    w = WorkflowDefinition(id="wf-1", name="MyWorkflow", created_at=100)
    assert w.id == "wf-1"
    assert w.name == "MyWorkflow"
    assert w.deleted_at is None


def test_workflow_definition_frozen():
    w = WorkflowDefinition(id="wf-1", name="MyWorkflow", created_at=100)
    with pytest.raises(AttributeError):
        w.name = "Other"


def test_workflow_version_creation():
    v = WorkflowVersion(
        id="ver-1",
        workflow_id="wf-1",
        version=2,
        graph_hash="abc123",
        original_graph_json="{}",
        detected_inputs_json="[]",
        detected_outputs_json="[]",
        created_at=200,
    )
    assert v.id == "ver-1"
    assert v.workflow_id == "wf-1"
    assert v.version == 2
    assert v.graph_hash == "abc123"


def test_workflow_version_frozen():
    v = WorkflowVersion(
        id="v1",
        workflow_id="w1",
        version=1,
        graph_hash="h",
        original_graph_json="{}",
        detected_inputs_json="[]",
        detected_outputs_json="[]",
        created_at=0,
    )
    with pytest.raises(AttributeError):
        v.version = 2
