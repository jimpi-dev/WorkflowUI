import json
import sqlite3
from pathlib import Path

QUICK_RUNS_PROJECT_ID = "00000000-0000-0000-0000-000000000002"
QUICK_RUNS_PROJECT_NAME = "Quick runs"
QUICK_RUNS_PROJECT_SLUG = "quick-runs"


def _run_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [r[1] for r in rows]


def migrate(db_path: Path | str) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT,
                description TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                metadata_json TEXT,
                tags_json TEXT,
                storage_mode TEXT DEFAULT 'inherit'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_project_slug ON project(slug)")
        cur = conn.execute("SELECT 1 FROM project WHERE id = ?", (QUICK_RUNS_PROJECT_ID,))
        if cur.fetchone() is None:
            conn.execute(
                """INSERT INTO project (id, name, slug, description, created_at, updated_at, metadata_json, tags_json)
                   VALUES (?, ?, ?, ?, 0, 0, NULL, NULL)""",
                (QUICK_RUNS_PROJECT_ID, QUICK_RUNS_PROJECT_NAME, QUICK_RUNS_PROJECT_SLUG, "Runs from Just generate—no project needed."),
            )
        _LEGACY_PROJECT_ID = "00000000-0000-0000-0000-000000000001"
        cur = conn.execute("SELECT 1 FROM project WHERE id = ?", (_LEGACY_PROJECT_ID,))
        if cur.fetchone() is not None:
            conn.execute("UPDATE run SET project_id = ? WHERE project_id = ?", (QUICK_RUNS_PROJECT_ID, _LEGACY_PROJECT_ID))
            conn.execute("DELETE FROM project WHERE id = ?", (_LEGACY_PROJECT_ID,))
        run_cols = _run_columns(conn, "run")
        if "project_id" not in run_cols:
            conn.execute("""
                CREATE TABLE run_new (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES project(id),
                    workflow_version_id TEXT NOT NULL REFERENCES workflow_version(id),
                    app_id TEXT REFERENCES workflow_app(id),
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    prompt_id TEXT,
                    seed INTEGER,
                    images_json TEXT,
                    execution_time REAL,
                    error TEXT,
                    queue_position INTEGER,
                    input_snapshot_json TEXT,
                    metadata_snapshot_json TEXT
                )
            """)
            conn.execute(
                """INSERT INTO run_new
                   (id, project_id, workflow_version_id, app_id, status, created_at, prompt_id, seed,
                    images_json, execution_time, error, queue_position, input_snapshot_json, metadata_snapshot_json)
                   SELECT id, ?, workflow_version_id, app_id, status, created_at, prompt_id, seed,
                          images_json, execution_time, error, queue_position, NULL, NULL
                   FROM run""",
                (QUICK_RUNS_PROJECT_ID,),
            )
            conn.execute("DROP TABLE run")
            conn.execute("ALTER TABLE run_new RENAME TO run")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_run_project_id ON run(project_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_run_app_id ON run(app_id)")
        else:
            if "input_snapshot_json" not in run_cols:
                conn.execute("ALTER TABLE run ADD COLUMN input_snapshot_json TEXT")
            if "metadata_snapshot_json" not in run_cols:
                conn.execute("ALTER TABLE run ADD COLUMN metadata_snapshot_json TEXT")
        if "run_group_id" not in _run_columns(conn, "run"):
            conn.execute("ALTER TABLE run ADD COLUMN run_group_id TEXT")
        if "comfyui_url" not in _run_columns(conn, "run"):
            conn.execute("ALTER TABLE run ADD COLUMN comfyui_url TEXT")
        run_cols = _run_columns(conn, "run")
        if "local_storage_status" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN local_storage_status TEXT DEFAULT 'none'")
        if "remote_status" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN remote_status TEXT DEFAULT 'unknown'")
        if "local_path" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN local_path TEXT")
        if "deleted_outputs_json" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN deleted_outputs_json TEXT")
        if "parent_run_id" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN parent_run_id TEXT")
        if "parent_media_id" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN parent_media_id TEXT")
        if "root_run_id" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN root_run_id TEXT")
        if "deleted_at" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN deleted_at INTEGER NULL")
        if "media_json" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN media_json TEXT")
            for row in conn.execute("SELECT id, images_json FROM run WHERE images_json IS NOT NULL AND images_json != ''").fetchall():
                rid, imgs_json = row[0], row[1]
                try:
                    imgs = json.loads(imgs_json) if imgs_json else []
                except json.JSONDecodeError:
                    continue
                media = []
                for ent in imgs:
                    if not isinstance(ent, dict):
                        continue
                    kind = ent.get("type") or "image"
                    media.append({
                        "filename": ent.get("filename", ""),
                        "subfolder": ent.get("subfolder", ""),
                        "kind": kind,
                    })
                if media:
                    conn.execute("UPDATE run SET media_json = ? WHERE id = ?", (json.dumps(media), rid))
        run_cols = _run_columns(conn, "run")
        proj_cols = _run_columns(conn, "project")
        if "storage_mode" not in proj_cols:
            conn.execute("ALTER TABLE project ADD COLUMN storage_mode TEXT DEFAULT 'inherit'")
        if "header_color" not in proj_cols:
            conn.execute("ALTER TABLE project ADD COLUMN header_color TEXT")
        if "archived_at" not in proj_cols:
            conn.execute("ALTER TABLE project ADD COLUMN archived_at INTEGER NULL")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_run_project_id ON run(project_id)")
        app_cols = _run_columns(conn, "workflow_app")
        if "comfyui_url" not in app_cols:
            conn.execute("ALTER TABLE workflow_app ADD COLUMN comfyui_url TEXT")
        if "supported_input_kinds_json" not in app_cols:
            conn.execute("ALTER TABLE workflow_app ADD COLUMN supported_input_kinds_json TEXT")
        if "header_color" not in app_cols:
            conn.execute("ALTER TABLE workflow_app ADD COLUMN header_color TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_run_prompt_id ON run(prompt_id)")
        wd_cols = _run_columns(conn, "workflow_definition")
        if "deleted_at" not in wd_cols:
            conn.execute("ALTER TABLE workflow_definition ADD COLUMN deleted_at INTEGER NULL")
        if "created_from_image_import" not in wd_cols:
            conn.execute("ALTER TABLE workflow_definition ADD COLUMN created_from_image_import INTEGER NOT NULL DEFAULT 0")
        app_cols = _run_columns(conn, "workflow_app")
        if "created_from_image_import" not in app_cols:
            conn.execute("ALTER TABLE workflow_app ADD COLUMN created_from_image_import INTEGER NOT NULL DEFAULT 0")
        if "embed_workflowui_metadata_on_download" not in app_cols:
            conn.execute("ALTER TABLE workflow_app ADD COLUMN embed_workflowui_metadata_on_download INTEGER NULL")
        if "embed_workflowui_metadata_on_save" not in app_cols:
            conn.execute("ALTER TABLE workflow_app ADD COLUMN embed_workflowui_metadata_on_save INTEGER NULL")
        if "app_version" not in app_cols:
            conn.execute("ALTER TABLE workflow_app ADD COLUMN app_version TEXT NOT NULL DEFAULT '1.0.0'")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_preset (
                id TEXT PRIMARY KEY,
                app_id TEXT NOT NULL REFERENCES workflow_app(id),
                name TEXT NOT NULL,
                description TEXT,
                keys_json TEXT NOT NULL,
                values_json TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_app_preset_app_id ON app_preset(app_id)")
        conn.commit()
    finally:
        try:
            conn.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass
        conn.close()
