"""Vault usage counts vs media-browser filter must agree (generation + run snapshots)."""

import json
import uuid

from db.init import init_db
from repositories.sqlite import SqliteProjectRepository, SqliteRunRepository


def test_count_generations_by_input_matches_dual_snapshot(tmp_path):
    """When generation snapshot is empty but run snapshot lists the file, counts and media filter still match."""
    db_path = str(tmp_path / "vault_usage.db")
    init_db(db_path)
    project_repo = SqliteProjectRepository(db_path)
    run_repo = SqliteRunRepository(db_path)

    project = project_repo.create_project(str(uuid.uuid4()), "p", None, 0, 0)
    run_id = str(uuid.uuid4())
    vault_name = "abc123def456.png"
    snap_run = json.dumps({"values": {"image": vault_name}, "bindings": []})
    run_repo.create_run(
        run_id,
        project.id,
        workflow_version_id=str(uuid.uuid4()),
        app_id=None,
        status="done",
        created_at=1,
        images_json=json.dumps([{"filename": "out.png", "subfolder": "", "type": "output"}]),
        input_snapshot_json=snap_run,
        metadata_snapshot_json="{}",
    )

    conn = run_repo._conn()
    try:
        conn.execute(
            "UPDATE generation SET input_snapshot_json = ? WHERE id = ?",
            ("{}", run_id),
        )
        conn.commit()
    finally:
        conn.close()

    counts = run_repo.count_generations_by_input_filenames_batch(
        [vault_name],
        owner_user_id=None,
        auth_enabled=False,
    )
    assert counts.get(vault_name) == 1

    items, total = run_repo.list_media_browser_images(
        owner_user_id=None,
        auth_enabled=False,
        source="generation",
        used_input_filename=vault_name,
        limit=20,
        offset=0,
    )
    assert total >= 1
    assert len(items) >= 1


def test_count_generations_many_filenames_no_compound_limit(tmp_path):
    """Batch counting must not exceed SQLite SQLITE_MAX_COMPOUND_SELECT (default 500)."""
    db_path = str(tmp_path / "vault_many.db")
    init_db(db_path)
    run_repo = SqliteRunRepository(db_path)
    names = [f"file_{i}.png" for i in range(600)]
    out = run_repo.count_generations_by_input_filenames_batch(
        names, owner_user_id=None, auth_enabled=False
    )
    assert len(out) == 600
    assert all(out[n] == 0 for n in names)
