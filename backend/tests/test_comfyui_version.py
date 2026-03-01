import pytest

from db.comfyui_version import compute_comfyui_metadata_hash
from db.init import init_db
from repositories.sqlite import SqliteRunRepository


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "comfyui_version.db"
    init_db(str(path))
    return str(path)


@pytest.fixture
def run_repo(db_path):
    return SqliteRunRepository(db_path)


def test_compute_comfyui_metadata_hash_deterministic():
    info = {"comfyui_base_url": "http://localhost:8188/", "system_stats": {"a": 1}, "fetched_at_ms": 12345}
    h1 = compute_comfyui_metadata_hash(info)
    h2 = compute_comfyui_metadata_hash(info)
    assert h1 == h2


def test_compute_comfyui_metadata_hash_excludes_fetched_at_ms():
    info1 = {"comfyui_base_url": "http://localhost:8188/", "fetched_at_ms": 11111}
    info2 = {"comfyui_base_url": "http://localhost:8188/", "fetched_at_ms": 99999}
    assert compute_comfyui_metadata_hash(info1) == compute_comfyui_metadata_hash(info2)


def test_compute_comfyui_metadata_hash_different_content_different_hash():
    info1 = {"comfyui_base_url": "http://localhost:8188/", "system_stats": {"v": 1}}
    info2 = {"comfyui_base_url": "http://localhost:8188/", "system_stats": {"v": 2}}
    assert compute_comfyui_metadata_hash(info1) != compute_comfyui_metadata_hash(info2)


def test_get_or_create_comfyui_version_same_hash_returns_same_id(run_repo):
    info = {"comfyui_base_url": "http://localhost:8188/", "object_info_node_classes": ["A", "B"]}
    id1 = run_repo.get_or_create_comfyui_version(info)
    id2 = run_repo.get_or_create_comfyui_version(info)
    assert id1 == id2


def test_get_or_create_comfyui_version_different_hash_returns_different_id(run_repo):
    info1 = {"comfyui_base_url": "http://localhost:8188/", "object_info_node_classes": ["A"]}
    info2 = {"comfyui_base_url": "http://localhost:8188/", "object_info_node_classes": ["A", "B"]}
    id1 = run_repo.get_or_create_comfyui_version(info1)
    id2 = run_repo.get_or_create_comfyui_version(info2)
    assert id1 != id2


def test_get_resolved_metadata_snapshot_without_comfyui_version_id(run_repo):
    from domain.run import Run
    run = Run(
        id="r1",
        project_id="p1",
        workflow_version_id="v1",
        app_id=None,
        status="done",
        created_at=0,
        metadata_snapshot_json='{"workflow_version_id":"v1","app_version":"1.0.0"}',
        comfyui_version_id=None,
    )
    resolved = run_repo.get_resolved_metadata_snapshot(run)
    assert resolved.get("workflow_version_id") == "v1"
    assert "ComfyUI-VersionInfo" not in resolved


def test_get_resolved_metadata_snapshot_with_comfyui_version_id(run_repo):
    from domain.run import Run
    info = {"comfyui_base_url": "http://localhost:8188/", "object_info_node_classes": ["SaveImage"]}
    version_id = run_repo.get_or_create_comfyui_version(info)
    run = Run(
        id="r1",
        project_id="p1",
        workflow_version_id="v1",
        app_id=None,
        status="done",
        created_at=0,
        metadata_snapshot_json='{"workflow_version_id":"v1","comfyui_version_id":"' + version_id + '"}',
        comfyui_version_id=version_id,
    )
    resolved = run_repo.get_resolved_metadata_snapshot(run)
    assert resolved.get("workflow_version_id") == "v1"
    assert "ComfyUI-VersionInfo" in resolved
    assert resolved["ComfyUI-VersionInfo"].get("comfyui_base_url") == "http://localhost:8188/"
