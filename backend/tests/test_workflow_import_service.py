import pytest

from services.workflow_import_service import (
    WorkflowImportService,
    IdempotentImport,
)
from services.graph_hash import graph_hash


def test_preview_new_workflow(mock_workflow_repo, sample_workflow_graph):
    svc = WorkflowImportService(mock_workflow_repo)
    out = svc.preview_import("MyWorkflow", sample_workflow_graph)
    assert out["is_new_workflow"] is True
    assert out["is_new_version"] is True
    assert out["existing_workflow_id"] is None
    assert "graph_hash" in out
    assert "detected_inputs" in out
    assert "detected_outputs" in out


def test_preview_existing_same_hash(mock_workflow_repo, sample_workflow_graph):
    svc = WorkflowImportService(mock_workflow_repo)
    svc.import_workflow("SameWorkflow", sample_workflow_graph)
    out = svc.preview_import("SameWorkflow", sample_workflow_graph)
    assert out["is_new_workflow"] is False
    assert out["is_new_version"] is False
    assert out["existing_workflow_id"] is not None
    assert out["existing_version"] is not None


def test_preview_existing_different_hash(mock_workflow_repo, sample_workflow_graph):
    svc = WorkflowImportService(mock_workflow_repo)
    svc.import_workflow("DiffWorkflow", sample_workflow_graph)
    other_graph = {**sample_workflow_graph, "extra": {"class_type": "SaveImage", "inputs": {}}}
    out = svc.preview_import("DiffWorkflow", other_graph)
    assert out["is_new_workflow"] is False
    assert out["is_new_version"] is True


def test_import_new_workflow_creates_v1(mock_workflow_repo, sample_workflow_graph):
    svc = WorkflowImportService(mock_workflow_repo)
    result = svc.import_workflow("NewOne", sample_workflow_graph)
    assert result.workflow_id
    assert result.version == 1
    assert result.graph_hash == graph_hash(sample_workflow_graph)
    assert result.is_new is True
    assert result.workflow_version_id


def test_import_duplicate_raises_idempotent(mock_workflow_repo, sample_workflow_graph):
    svc = WorkflowImportService(mock_workflow_repo)
    svc.import_workflow("Dup", sample_workflow_graph)
    with pytest.raises(IdempotentImport) as exc_info:
        svc.import_workflow("Dup", sample_workflow_graph)
    assert exc_info.value.workflow_id
    assert exc_info.value.version == 1


def test_import_second_version(mock_workflow_repo, sample_workflow_graph):
    svc = WorkflowImportService(mock_workflow_repo)
    svc.import_workflow("Vers", sample_workflow_graph)
    other = {**sample_workflow_graph, "99": {"class_type": "SaveImage", "inputs": {}}}
    result = svc.import_workflow("Vers", other)
    assert result.version == 2
    assert result.is_new is True


def test_preview_requires_name(mock_workflow_repo, sample_workflow_graph):
    svc = WorkflowImportService(mock_workflow_repo)
    with pytest.raises(ValueError, match="name is required"):
        svc.preview_import("", sample_workflow_graph)
    with pytest.raises(ValueError, match="name is required"):
        svc.preview_import("   ", sample_workflow_graph)


def test_preview_requires_graph(mock_workflow_repo):
    svc = WorkflowImportService(mock_workflow_repo)
    with pytest.raises(ValueError, match="graph must be"):
        svc.preview_import("A", {})
    with pytest.raises(ValueError, match="graph must be"):
        svc.preview_import("A", "not a dict")


def test_import_requires_name(mock_workflow_repo, sample_workflow_graph):
    svc = WorkflowImportService(mock_workflow_repo)
    with pytest.raises(ValueError, match="name is required"):
        svc.import_workflow("", sample_workflow_graph)


def test_import_requires_graph(mock_workflow_repo):
    svc = WorkflowImportService(mock_workflow_repo)
    with pytest.raises(ValueError, match="graph must be"):
        svc.import_workflow("A", {})
