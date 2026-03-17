import json
import sqlite3
from pathlib import Path

QUICK_RUNS_PROJECT_ID = "00000000-0000-0000-0000-000000000002"
QUICK_RUNS_PROJECT_NAME = "Quick runs"


def _run_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [r[1] for r in rows]


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    ).fetchone() is not None


def _ensure_run_generation_tables(conn: sqlite3.Connection) -> None:
    """Ensure normalized run (group) + generation tables exist; migrate legacy run rows if needed."""
    has_generation = _table_exists(conn, "generation")
    has_run = _table_exists(conn, "run")
    if not has_run and not has_generation:
        conn.execute("""
            CREATE TABLE run (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES project(id),
                workflow_version_id TEXT NOT NULL REFERENCES workflow_version(id),
                app_id TEXT REFERENCES workflow_app(id),
                created_at INTEGER NOT NULL,
                input_snapshot_json TEXT,
                metadata_snapshot_json TEXT,
                run_group_id TEXT,
                comfyui_url TEXT,
                comfyui_version_id TEXT REFERENCES comfyui_version(id)
            )
        """)
        conn.execute("""
            CREATE TABLE generation (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES run(id) ON DELETE CASCADE,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                prompt_id TEXT,
                seed INTEGER,
                images_json TEXT,
                media_json TEXT,
                execution_time REAL,
                error TEXT,
                queue_position INTEGER,
                local_storage_status TEXT DEFAULT 'none',
                remote_status TEXT DEFAULT 'unknown',
                local_path TEXT,
                deleted_outputs_json TEXT,
                parent_run_id TEXT,
                parent_media_id TEXT,
                root_run_id TEXT,
                deleted_at INTEGER NULL
            )
        """)
        return

    if not has_generation and has_run:
        # Legacy schema: run table holds generations. Migrate to run + generation.
        run_cols = _run_columns(conn, "run")
        if "status" in run_cols:
            def _col(name: str, default: str = "NULL") -> str:
                return name if name in run_cols else default

            group_id_expr = "COALESCE(run_group_id, id)" if "run_group_id" in run_cols else "id"
            conn.execute("""
                CREATE TABLE run_new (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES project(id),
                    workflow_version_id TEXT NOT NULL REFERENCES workflow_version(id),
                    app_id TEXT REFERENCES workflow_app(id),
                    created_at INTEGER NOT NULL,
                    input_snapshot_json TEXT,
                    metadata_snapshot_json TEXT,
                    run_group_id TEXT,
                    comfyui_url TEXT,
                    comfyui_version_id TEXT REFERENCES comfyui_version(id)
                )
            """)
            conn.execute("""
                CREATE TABLE generation (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES run_new(id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    prompt_id TEXT,
                    seed INTEGER,
                    images_json TEXT,
                    media_json TEXT,
                    execution_time REAL,
                    error TEXT,
                    queue_position INTEGER,
                    local_storage_status TEXT DEFAULT 'none',
                    remote_status TEXT DEFAULT 'unknown',
                    local_path TEXT,
                    deleted_outputs_json TEXT,
                    parent_run_id TEXT,
                    parent_media_id TEXT,
                    root_run_id TEXT,
                    deleted_at INTEGER NULL
                )
            """)
            conn.execute("""
                INSERT INTO run_new
                (id, project_id, workflow_version_id, app_id, created_at,
                 input_snapshot_json, metadata_snapshot_json, run_group_id, comfyui_url, comfyui_version_id)
                SELECT
                    """ + group_id_expr + """ AS run_id,
                    project_id,
                    workflow_version_id,
                    app_id,
                    MIN(created_at) AS created_at,
                    MAX(""" + _col("input_snapshot_json") + """) AS input_snapshot_json,
                    MAX(""" + _col("metadata_snapshot_json") + """) AS metadata_snapshot_json,
                    MAX(""" + _col("run_group_id") + """) AS run_group_id,
                    MAX(""" + _col("comfyui_url") + """) AS comfyui_url,
                    MAX(""" + _col("comfyui_version_id") + """) AS comfyui_version_id
                FROM run
                GROUP BY """ + group_id_expr + """
            """)
            conn.execute("""
                INSERT INTO generation
                (id, run_id, status, created_at, prompt_id, seed, images_json, media_json,
                 execution_time, error, queue_position, local_storage_status, remote_status,
                 local_path, deleted_outputs_json, parent_run_id, parent_media_id, root_run_id, deleted_at)
                SELECT
                    id,
                    """ + group_id_expr + """ AS run_id,
                    status,
                    created_at,
                    prompt_id,
                    seed,
                    images_json,
                    """ + _col("media_json") + """,
                    execution_time,
                    error,
                    queue_position,
                    """ + _col("local_storage_status", "'none'") + """,
                    """ + _col("remote_status", "'unknown'") + """,
                    """ + _col("local_path") + """,
                    """ + _col("deleted_outputs_json") + """,
                    """ + _col("parent_run_id") + """,
                    """ + _col("parent_media_id") + """,
                    """ + _col("root_run_id") + """,
                    """ + _col("deleted_at") + """
                FROM run
            """)
            conn.execute("DROP TABLE run")
            conn.execute("ALTER TABLE run_new RENAME TO run")
        else:
            # New run table exists but generation missing; create generation.
            conn.execute("""
                CREATE TABLE generation (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES run(id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    prompt_id TEXT,
                    seed INTEGER,
                    images_json TEXT,
                    media_json TEXT,
                    execution_time REAL,
                    error TEXT,
                    queue_position INTEGER,
                    local_storage_status TEXT DEFAULT 'none',
                    remote_status TEXT DEFAULT 'unknown',
                    local_path TEXT,
                    deleted_outputs_json TEXT,
                    parent_run_id TEXT,
                    parent_media_id TEXT,
                    root_run_id TEXT,
                    deleted_at INTEGER NULL
                )
            """)


def migrate(db_path: Path | str) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                metadata_json TEXT,
                tags_json TEXT,
                storage_mode TEXT DEFAULT 'inherit'
            )
        """)
        cur = conn.execute("SELECT 1 FROM project WHERE id = ?", (QUICK_RUNS_PROJECT_ID,))
        if cur.fetchone() is None:
            conn.execute(
                """INSERT INTO project (id, name, description, created_at, updated_at, metadata_json, tags_json)
                   VALUES (?, ?, ?, 0, 0, NULL, NULL)""",
                (QUICK_RUNS_PROJECT_ID, QUICK_RUNS_PROJECT_NAME, "Runs from Just generate—no project needed."),
            )
        _LEGACY_PROJECT_ID = "00000000-0000-0000-0000-000000000001"
        cur = conn.execute("SELECT 1 FROM project WHERE id = ?", (_LEGACY_PROJECT_ID,))
        if cur.fetchone() is not None:
            conn.execute("DELETE FROM project WHERE id = ?", (_LEGACY_PROJECT_ID,))

        _ensure_run_generation_tables(conn)

        if _table_exists(conn, "run"):
            conn.execute(
                "UPDATE run SET project_id = ? WHERE project_id = ?",
                (QUICK_RUNS_PROJECT_ID, _LEGACY_PROJECT_ID),
            )

        run_cols = _run_columns(conn, "run")
        gen_cols = _run_columns(conn, "generation")
        if "input_snapshot_json" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN input_snapshot_json TEXT")
        if "metadata_snapshot_json" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN metadata_snapshot_json TEXT")
        if "run_group_id" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN run_group_id TEXT")
        if "comfyui_url" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN comfyui_url TEXT")
        if "comfyui_version_id" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN comfyui_version_id TEXT REFERENCES comfyui_version(id)")
        run_cols = _run_columns(conn, "run")
        if "media_json" not in gen_cols:
            conn.execute("ALTER TABLE generation ADD COLUMN media_json TEXT")
        if "local_storage_status" not in gen_cols:
            conn.execute("ALTER TABLE generation ADD COLUMN local_storage_status TEXT DEFAULT 'none'")
        if "remote_status" not in gen_cols:
            conn.execute("ALTER TABLE generation ADD COLUMN remote_status TEXT DEFAULT 'unknown'")
        if "local_path" not in gen_cols:
            conn.execute("ALTER TABLE generation ADD COLUMN local_path TEXT")
        if "deleted_outputs_json" not in gen_cols:
            conn.execute("ALTER TABLE generation ADD COLUMN deleted_outputs_json TEXT")
        if "parent_run_id" not in gen_cols:
            conn.execute("ALTER TABLE generation ADD COLUMN parent_run_id TEXT")
        if "parent_media_id" not in gen_cols:
            conn.execute("ALTER TABLE generation ADD COLUMN parent_media_id TEXT")
        if "root_run_id" not in gen_cols:
            conn.execute("ALTER TABLE generation ADD COLUMN root_run_id TEXT")
        if "deleted_at" not in gen_cols:
            conn.execute("ALTER TABLE generation ADD COLUMN deleted_at INTEGER NULL")
        gen_cols = _run_columns(conn, "generation")
        if "media_json" in gen_cols:
            for row in conn.execute("SELECT id, images_json FROM generation WHERE images_json IS NOT NULL AND images_json != ''").fetchall():
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
                    conn.execute("UPDATE generation SET media_json = ? WHERE id = ?", (json.dumps(media), rid))
        run_cols = _run_columns(conn, "run")
        proj_cols = _run_columns(conn, "project")
        if "storage_mode" not in proj_cols:
            conn.execute("ALTER TABLE project ADD COLUMN storage_mode TEXT DEFAULT 'inherit'")
        if "header_color" not in proj_cols:
            conn.execute("ALTER TABLE project ADD COLUMN header_color TEXT")
        if "archived_at" not in proj_cols:
            conn.execute("ALTER TABLE project ADD COLUMN archived_at INTEGER NULL")
        if "slug" in proj_cols:
            conn.execute("DROP INDEX IF EXISTS idx_project_slug")
            conn.execute("ALTER TABLE project DROP COLUMN slug")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_run_project_id ON run(project_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_run_app_id ON run(app_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_generation_run_id ON generation(run_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_generation_prompt_id ON generation(prompt_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_generation_parent_run_id ON generation(parent_run_id)")

        # Backfill app_id for legacy runs where it was never set, but there is a single
        # unambiguous app for the workflow_version. This makes old runs show up correctly
        # under the app (and, when the app is later removed, under the \"Deleted app\" filter).
        if "app_id" in run_cols:
            # For each workflow_version_id that has exactly one app, attach that app_id
            # to any runs that currently have app_id NULL.
            rows = conn.execute(
                """
                SELECT workflow_version_id, MIN(id) AS app_id, COUNT(*) AS app_count
                FROM workflow_app
                GROUP BY workflow_version_id
                HAVING app_count = 1
                """
            ).fetchall()
            for wf_version_id, app_id, app_count in rows:
                if not wf_version_id or not app_id:
                    continue
                conn.execute(
                    "UPDATE run SET app_id = ? WHERE app_id IS NULL AND workflow_version_id = ?",
                    (app_id, wf_version_id),
                )
        app_cols = _run_columns(conn, "workflow_app")
        if "comfyui_url" not in app_cols:
            conn.execute("ALTER TABLE workflow_app ADD COLUMN comfyui_url TEXT")
        if "supported_input_kinds_json" not in app_cols:
            conn.execute("ALTER TABLE workflow_app ADD COLUMN supported_input_kinds_json TEXT")
        if "header_color" not in app_cols:
            conn.execute("ALTER TABLE workflow_app ADD COLUMN header_color TEXT")
        if "tags_json" not in app_cols:
            conn.execute("ALTER TABLE workflow_app ADD COLUMN tags_json TEXT")
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS comfyui_version (
                id TEXT PRIMARY KEY,
                metadata_hash TEXT NOT NULL UNIQUE,
                comfyui_base_url TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comfyui_version_metadata_hash ON comfyui_version(metadata_hash)")
        run_cols = _run_columns(conn, "run")
        if "comfyui_version_id" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN comfyui_version_id TEXT REFERENCES comfyui_version(id)")
        # Ensure there are no orphaned app_id references on run rows: if a run.app_id
        # does not correspond to any existing workflow_app.id, set app_id to NULL.
        if "app_id" in run_cols:
            conn.execute(
                """
                UPDATE run
                SET app_id = NULL
                WHERE app_id IS NOT NULL
                  AND app_id NOT IN (SELECT id FROM workflow_app)
                """
            )
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='saved_queue'"
        ).fetchone():
            conn.execute("""
                CREATE TABLE saved_queue (
                    id TEXT PRIMARY KEY,
                    run_ids TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)
        try:
            mode = conn.execute("PRAGMA auto_vacuum").fetchone()
            if mode and mode[0] == 0:
                conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
                conn.execute("VACUUM")
        except Exception:
            pass
        conn.commit()
    finally:
        try:
            conn.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass
        conn.close()
