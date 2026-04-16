import json
import uuid

from db.init import init_db
from repositories.sqlite import SqliteProjectRepository, SqliteRunRepository, SqliteWorkflowAppRepository
from routers import projects as projects_router


class _DummyMediaStorageService:
    def get_run_local_storage_bytes(self, _run):
        return None


def _create_run(run_repo, project_id: str, media_entries: list[dict], *, images_entries: list[dict] | None = None) -> str:
    run_id = str(uuid.uuid4())
    run_repo.create_run(
        run_id,
        project_id,
        workflow_version_id=str(uuid.uuid4()),
        app_id=None,
        status="done",
        created_at=0,
        images_json=json.dumps(images_entries) if images_entries is not None else None,
        media_json=json.dumps(media_entries) if media_entries is not None else None,
        input_snapshot_json="{}",
        metadata_snapshot_json="{}",
    )
    return run_id


def test_storage_sizes_uses_media_json_for_video_audio_and_mixed(tmp_path, monkeypatch):
    db_path = str(tmp_path / "projects_storage_sizes.db")
    init_db(db_path)
    project_repo = SqliteProjectRepository(db_path)
    run_repo = SqliteRunRepository(db_path)
    app_repo = SqliteWorkflowAppRepository(db_path)

    project = project_repo.create_project(str(uuid.uuid4()), "p", None, 0, 0)
    run_video = _create_run(
        run_repo,
        project.id,
        [{"filename": "video_only.mp4", "subfolder": "", "kind": "video"}],
    )
    run_audio = _create_run(
        run_repo,
        project.id,
        [{"filename": "audio_only.mp3", "subfolder": "", "kind": "audio"}],
    )
    run_mixed = _create_run(
        run_repo,
        project.id,
        [
            {"filename": "mixed_video.webm", "subfolder": "", "kind": "video"},
            {"filename": "mixed_audio.wav", "subfolder": "", "kind": "audio"},
        ],
    )
    run_media_only = _create_run(
        run_repo,
        project.id,
        [{"filename": "media_only.webm", "subfolder": "", "kind": "video"}],
        images_entries=None,
    )

    captured_groups: list[list[dict]] = []

    def fake_batch(_url: str, groups: list[list[dict]]) -> list[int]:
        captured_groups.extend(groups)
        by_ext = {
            ".mp4": 10,
            ".webm": 11,
            ".mp3": 20,
            ".wav": 21,
        }
        sizes: list[int] = []
        for group in groups:
            total = 0
            for ent in group:
                filename = (ent.get("filename") or "").lower()
                for ext, size in by_ext.items():
                    if filename.endswith(ext):
                        total += size
                        break
            sizes.append(total)
        return sizes

    monkeypatch.setattr(projects_router, "ensure_project_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(projects_router, "get_runs_remote_storage_bytes_batch", fake_batch)
    monkeypatch.setattr(projects_router, "get_runs_remote_storage_bytes_deduplicated", lambda *_args, **_kwargs: [])

    db = (None, None, app_repo, run_repo, project_repo, None, None)
    result = projects_router.get_project_runs_storage_sizes(
        project.id,
        run_ids=",".join([run_video, run_audio, run_mixed, run_media_only]),
        db=db,
        service=_DummyMediaStorageService(),
        ctx=None,
    )

    assert result[run_video]["remote_storage_bytes"] == 10
    assert result[run_audio]["remote_storage_bytes"] == 20
    assert result[run_mixed]["remote_storage_bytes"] == 32
    assert result[run_media_only]["remote_storage_bytes"] == 11

    # Normalization should map media_json.kind -> type before remote sizing.
    assert all(isinstance(group, list) for group in captured_groups)
    assert all(isinstance(ent, dict) and ent.get("type") in {"video", "audio"} for group in captured_groups for ent in group)
