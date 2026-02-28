import json
import os
from pathlib import Path
import uuid

import pytest
from db.init import init_db
from repositories.sqlite import SqliteProjectRepository, SqliteRunRepository, SqliteWorkflowAppRepository
from services.media_storage_service import MediaStorageService
from config import update_media_storage_config


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "media_storage.db"
    init_db(str(path))
    return str(path)


@pytest.fixture
def repos(db_path):
    project_repo = SqliteProjectRepository(db_path)
    run_repo = SqliteRunRepository(db_path)
    app_repo = SqliteWorkflowAppRepository(db_path)
    return project_repo, run_repo, app_repo


@pytest.fixture
def service(repos, tmp_path):
    project_repo, run_repo, app_repo = repos
    root = tmp_path / "media"
    update_media_storage_config(enabled=True, root_path=str(root), delete_remote_after_save=False)
    return MediaStorageService(run_repo, project_repo, app_repo), root


def create_run(run_repo, project_id):
    run_id = str(uuid.uuid4())
    run_repo.create_run(
        run_id,
        project_id,
        workflow_version_id=str(uuid.uuid4()),
        app_id=None,
        status="done",
        created_at=0,
        images_json=json.dumps([{"filename": "a.png", "subfolder": "", "type": "image"}]),
        input_snapshot_json="{}",
        metadata_snapshot_json="{}",
    )
    return run_id


def test_delete_local_on_empty(service, repos):
    media_service, root = service
    project_repo, run_repo, _ = repos
    project = project_repo.create_project(str(uuid.uuid4()), "p", "p", None, 0, 0)
    run_id = create_run(run_repo, project.id)
    result = media_service.delete_local(run_id, None)
    assert result["ok"] is True
    assert result["local_storage_status"] == "none"
    assert result["local_path"] is None


def test_delete_both_after_save(monkeypatch, service, repos):
    media_service, root = service
    project_repo, run_repo, _ = repos
    project = project_repo.create_project(str(uuid.uuid4()), "p", "p", None, 0, 0)
    run_id = create_run(run_repo, project.id)

    monkeypatch.setattr(MediaStorageService, "_fetch_remote_image_bytes", lambda *_: b"data")
    monkeypatch.setattr(MediaStorageService, "_delete_remote_images", lambda *_: (True, None))

    save_result = media_service.save_run(run_id)
    assert save_result["local_storage_status"] == "saved"
    assert (root / project.id).exists()

    delete_result = media_service.delete_both(run_id, None)
    assert delete_result["ok"] is True
    assert delete_result["local_storage_status"] == "none"
    assert delete_result["remote_status"] == "deleted"
    run_dir = root / project.id / "1970-01-01" / run_id
    assert not run_dir.exists()


def test_save_uses_comfy_filename_and_unique_counter(monkeypatch, service, repos):
    media_service, root = service
    project_repo, run_repo, _ = repos
    project = project_repo.create_project(str(uuid.uuid4()), "p", "p", None, 0, 0)
    run_id = str(uuid.uuid4())
    run_repo.create_run(
        run_id,
        project.id,
        workflow_version_id=str(uuid.uuid4()),
        app_id=None,
        status="done",
        created_at=0,
        images_json=json.dumps([
            {"filename": "comfy_output.png", "subfolder": "", "type": "output"},
            {"filename": "comfy_output.png", "subfolder": "", "type": "output"},
        ]),
        input_snapshot_json="{}",
        metadata_snapshot_json="{}",
    )
    monkeypatch.setattr(MediaStorageService, "_fetch_remote_image_bytes", lambda *_: b"data")
    monkeypatch.setattr(MediaStorageService, "_delete_remote_images", lambda *_: (True, None))

    save_result = media_service.save_run(run_id)
    assert save_result["ok"] is True
    assert save_result["local_storage_status"] == "saved"
    run_dir = root / project.id / "1970-01-01" / run_id
    assert run_dir.is_dir()
    metadata_pattern = lambda n: n.startswith("metadata.") and n.endswith(".json")
    files = [p.name for p in run_dir.iterdir() if p.is_file() and not metadata_pattern(p.name)]
    files.sort()
    assert "comfy_output_1.png" in files
    assert "comfy_output_2.png" in files
    assert len(files) == 2
