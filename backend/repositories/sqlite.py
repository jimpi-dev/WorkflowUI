"""TODO: postgres and maybe other adapters."""
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from db.comfyui_version import compute_comfyui_metadata_hash
from domain.workflow import WorkflowDefinition, WorkflowVersion
from domain.app import WorkflowApp
from domain.run import Run
from domain.project import Project
from domain.preset import AppPreset

_UNSET = object()

def _row_to_workflow_definition(row: tuple) -> WorkflowDefinition:
    return WorkflowDefinition(
        id=row[0], name=row[1], created_at=row[2],
        deleted_at=row[3] if len(row) > 3 else None,
        created_from_image_import=bool(row[4]) if len(row) > 4 else False,
    )

def _row_to_workflow_version(row: tuple) -> WorkflowVersion:
    return WorkflowVersion(
        id=row[0],
        workflow_id=row[1],
        version=row[2],
        graph_hash=row[3],
        original_graph_json=row[4],
        detected_inputs_json=row[5],
        detected_outputs_json=row[6],
        created_at=row[7],
    )


def _row_to_workflow_app(row: tuple) -> WorkflowApp:
    def _opt_bool(idx: int) -> bool | None:
        if len(row) <= idx or row[idx] is None:
            return None
        return bool(row[idx])
    return WorkflowApp(
        id=row[0],
        workflow_version_id=row[1],
        slug=row[2],
        title=row[3],
        description=row[4],
        ui_config_json=row[5],
        default_inputs_json=row[6],
        default_outputs_json=row[7],
        is_public=bool(row[8]),
        created_at=row[9],
        app_version=(row[10] if len(row) > 10 and row[10] else "1.0.0"),
        comfyui_url=row[11] if len(row) > 11 else None,
        supported_input_kinds_json=row[12] if len(row) > 12 else None,
        header_color=row[13] if len(row) > 13 else None,
        tags_json=row[14] if len(row) > 14 else None,
        created_from_image_import=bool(row[15]) if len(row) > 15 else False,
        embed_workflowui_metadata_on_download=_opt_bool(16),
        embed_workflowui_metadata_on_save=_opt_bool(17),
    )


def _run_select_cols() -> str:
    return """id, project_id, workflow_version_id, app_id, status, created_at, prompt_id, seed,
        images_json, media_json, execution_time, error, queue_position, input_snapshot_json, metadata_snapshot_json, run_group_id, comfyui_url, comfyui_version_id,
        local_storage_status, remote_status, local_path, deleted_outputs_json,
        parent_run_id, parent_media_id, root_run_id, deleted_at"""


def _row_to_run(row: tuple) -> Run:
    n = len(row)
    return Run(
        id=row[0],
        project_id=row[1],
        workflow_version_id=row[2],
        app_id=row[3],
        status=row[4],
        created_at=row[5],
        prompt_id=row[6] if n > 6 else None,
        seed=row[7] if n > 7 else None,
        images_json=row[8] if n > 8 else None,
        media_json=row[9] if n > 9 else None,
        execution_time=row[10] if n > 10 else None,
        error=row[11] if n > 11 else None,
        queue_position=row[12] if n > 12 else None,
        input_snapshot_json=row[13] if n > 13 else None,
        metadata_snapshot_json=row[14] if n > 14 else None,
        run_group_id=row[15] if n > 15 else None,
        comfyui_url=row[16] if n > 16 else None,
        comfyui_version_id=row[17] if n > 17 else None,
        local_storage_status=row[18] if n > 18 else None,
        remote_status=row[19] if n > 19 else None,
        local_path=row[20] if n > 20 else None,
        deleted_outputs_json=row[21] if n > 21 else None,
        parent_run_id=row[22] if n > 22 else None,
        parent_media_id=row[23] if n > 23 else None,
        root_run_id=row[24] if n > 24 else None,
        deleted_at=row[25] if n > 25 else None,
    )


def _row_to_app_preset(row: tuple) -> AppPreset:
    return AppPreset(
        id=row[0],
        app_id=row[1],
        name=row[2],
        description=row[3],
        keys_json=row[4],
        values_json=row[5],
        created_at=row[6],
    )


def _row_to_project(row: tuple) -> Project:
    return Project(
        id=row[0],
        name=row[1],
        description=row[2],
        created_at=row[3],
        updated_at=row[4],
        metadata_json=row[5],
        tags_json=row[6],
        storage_mode=row[7] if len(row) > 7 else None,
        header_color=row[8] if len(row) > 8 else None,
        archived_at=row[9] if len(row) > 9 else None,
    )


class SqliteWorkflowRepository:
    def __init__(self, db_path: str | Path):
        self._db_path = str(Path(db_path).resolve())

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def run_in_transaction(self, fn: callable) -> Any:
        conn = self._conn()
        try:
            conn.execute("BEGIN")
            result = fn(conn)
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_workflow_definition(
        self,
        id: str,
        name: str,
        created_at: int,
        *,
        conn: sqlite3.Connection | None = None,
        created_from_image_import: bool = False,
    ) -> WorkflowDefinition:
        own = conn is None
        c = conn or self._conn()
        try:
            c.execute(
                "INSERT INTO workflow_definition (id, name, created_at, created_from_image_import) VALUES (?, ?, ?, ?)",
                (id, name, created_at, 1 if created_from_image_import else 0),
            )
            if own:
                c.commit()
            return WorkflowDefinition(id=id, name=name, created_at=created_at, created_from_image_import=created_from_image_import)
        finally:
            if own:
                c.close()

    def get_workflow_by_name(self, name: str) -> WorkflowDefinition | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT id, name, created_at, deleted_at, created_from_image_import FROM workflow_definition WHERE name = ? AND deleted_at IS NULL",
                (name,),
            ).fetchone()
            return _row_to_workflow_definition(row) if row else None
        finally:
            conn.close()

    def get_workflow_definition(self, workflow_id: str) -> WorkflowDefinition | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT id, name, created_at, deleted_at, created_from_image_import FROM workflow_definition WHERE id = ?",
                (workflow_id,),
            ).fetchone()
            if not row or (len(row) > 3 and row[3] is not None):
                return None
            return _row_to_workflow_definition(row)
        finally:
            conn.close()

    def get_latest_version(self, workflow_id: str) -> WorkflowVersion | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT id, workflow_id, version, graph_hash, original_graph_json,
                   detected_inputs_json, detected_outputs_json, created_at
                   FROM workflow_version WHERE workflow_id = ? ORDER BY version DESC LIMIT 1""",
                (workflow_id,),
            ).fetchone()
            return _row_to_workflow_version(row) if row else None
        finally:
            conn.close()

    def create_workflow_version(
        self,
        id: str,
        workflow_id: str,
        version: int,
        graph_hash: str,
        original_graph_json: str,
        detected_inputs_json: str,
        detected_outputs_json: str,
        created_at: int,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> WorkflowVersion:
        own = conn is None
        c = conn or self._conn()
        try:
            c.execute(
                """INSERT INTO workflow_version
                   (id, workflow_id, version, graph_hash, original_graph_json,
                    detected_inputs_json, detected_outputs_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    id,
                    workflow_id,
                    version,
                    graph_hash,
                    original_graph_json,
                    detected_inputs_json,
                    detected_outputs_json,
                    created_at,
                ),
            )
            if own:
                c.commit()
            return WorkflowVersion(
                id=id,
                workflow_id=workflow_id,
                version=version,
                graph_hash=graph_hash,
                original_graph_json=original_graph_json,
                detected_inputs_json=detected_inputs_json,
                detected_outputs_json=detected_outputs_json,
                created_at=created_at,
            )
        finally:
            if own:
                c.close()

    def get_workflow_version(self, version_id: str) -> WorkflowVersion | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT id, workflow_id, version, graph_hash, original_graph_json,
                   detected_inputs_json, detected_outputs_json, created_at
                   FROM workflow_version WHERE id = ?""",
                (version_id,),
            ).fetchone()
            return _row_to_workflow_version(row) if row else None
        finally:
            conn.close()

    def get_workflow_version_by_workflow_and_version(
        self, workflow_id: str, version: int
    ) -> WorkflowVersion | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT id, workflow_id, version, graph_hash, original_graph_json,
                   detected_inputs_json, detected_outputs_json, created_at
                   FROM workflow_version WHERE workflow_id = ? AND version = ?""",
                (workflow_id, version),
            ).fetchone()
            return _row_to_workflow_version(row) if row else None
        finally:
            conn.close()

    def list_workflow_definitions(self) -> list[WorkflowDefinition]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id, name, created_at, deleted_at, created_from_image_import FROM workflow_definition WHERE deleted_at IS NULL ORDER BY created_at DESC"
            ).fetchall()
            return [_row_to_workflow_definition(r) for r in rows]
        finally:
            conn.close()

    def list_workflow_definitions_with_app_counts(
        self,
    ) -> list[tuple[WorkflowDefinition, int, int, str | None]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT wd.id, wd.name, wd.created_at, wd.deleted_at, wd.created_from_image_import,
                   (SELECT COUNT(*) FROM workflow_version wv
                    JOIN workflow_app wa ON wa.workflow_version_id = wv.id
                    WHERE wv.workflow_id = wd.id) AS app_count,
                   (SELECT COUNT(*) FROM workflow_version wv WHERE wv.workflow_id = wd.id) AS version_count,
                   (SELECT id FROM workflow_version WHERE workflow_id = wd.id ORDER BY version DESC LIMIT 1) AS latest_version_id
                   FROM workflow_definition wd WHERE wd.deleted_at IS NULL ORDER BY wd.created_at DESC"""
            ).fetchall()
            return [
                (
                    _row_to_workflow_definition((r[0], r[1], r[2], r[3] if len(r) > 3 else None, r[4] if len(r) > 4 else 0)),
                    (r[5] or 0) if len(r) > 5 else 0,
                    (r[6] or 0) if len(r) > 6 else 0,
                    r[7] if len(r) > 7 and r[7] else None,
                )
                for r in rows
            ]
        finally:
            conn.close()

    def set_workflow_deleted_at(self, workflow_id: str, deleted_at: int, *, conn: sqlite3.Connection | None = None) -> None:
        own = conn is None
        c = conn or self._conn()
        try:
            c.execute("UPDATE workflow_definition SET deleted_at = ? WHERE id = ?", (deleted_at, workflow_id))
            if own:
                c.commit()
        finally:
            if own:
                c.close()

    def list_versions(self, workflow_id: str) -> list[WorkflowVersion]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT id, workflow_id, version, graph_hash, original_graph_json,
                   detected_inputs_json, detected_outputs_json, created_at
                   FROM workflow_version WHERE workflow_id = ? ORDER BY version ASC""",
                (workflow_id,),
            ).fetchall()
            return [_row_to_workflow_version(r) for r in rows]
        finally:
            conn.close()


class SqliteProjectRepository:
    def __init__(self, db_path: str | Path):
        self._db_path = str(Path(db_path).resolve())

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def create_project(
        self,
        id: str,
        name: str,
        description: str | None,
        created_at: int,
        updated_at: int,
        metadata_json: str | None = None,
        tags_json: str | None = None,
        storage_mode: str | None = "inherit",
        header_color: str | None = None,
    ) -> Project:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO project (id, name, description, created_at, updated_at, metadata_json, tags_json, storage_mode, header_color)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (id, name, description, created_at, updated_at, metadata_json, tags_json, storage_mode, header_color),
            )
            conn.commit()
            return Project(
                id=id,
                name=name,
                description=description,
                created_at=created_at,
                updated_at=updated_at,
                metadata_json=metadata_json,
                tags_json=tags_json,
                storage_mode=storage_mode,
                header_color=header_color,
            )
        finally:
            conn.close()

    def get_project(self, project_id: str) -> Project | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT id, name, description, created_at, updated_at, metadata_json, tags_json, storage_mode, header_color, archived_at FROM project WHERE id = ?",
                (project_id,),
            ).fetchone()
            return _row_to_project(row) if row else None
        finally:
            conn.close()

    def list_projects(
        self,
        tag: str | None = None,
        limit: int = 100,
        archived: bool | None = False,
    ) -> list[Project]:
        conn = self._conn()
        try:
            base_cols = "id, name, description, created_at, updated_at, metadata_json, tags_json, storage_mode, header_color, archived_at"
            if archived is False:
                where = "WHERE archived_at IS NULL"
            elif archived is True:
                where = "WHERE archived_at IS NOT NULL"
            else:
                where = ""
            if tag:
                tag_cond = "tags_json IS NOT NULL AND tags_json LIKE ?"
                if where:
                    where = where + " AND " + tag_cond
                else:
                    where = "WHERE " + tag_cond
                params_list: list[Any] = [f"%{tag}%", limit]
            else:
                params_list = [limit]
            sql = f"SELECT {base_cols} FROM project {where} ORDER BY updated_at DESC LIMIT ?"
            rows = conn.execute(sql, params_list).fetchall()
            return [_row_to_project(r) for r in rows]
        finally:
            conn.close()

    def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        updated_at: int | None = None,
        metadata_json: str | None = None,
        tags_json: str | None = None,
        storage_mode: str | None = None,
        header_color: str | None = _UNSET,
        archived_at: int | None = _UNSET,
    ) -> Project | None:
        conn = self._conn()
        try:
            proj = self.get_project(project_id)
            if not proj:
                return None
            updates = []
            params: list[Any] = []
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if updated_at is not None:
                updates.append("updated_at = ?")
                params.append(updated_at)
            if metadata_json is not None:
                updates.append("metadata_json = ?")
                params.append(metadata_json)
            if tags_json is not None:
                updates.append("tags_json = ?")
                params.append(tags_json)
            if storage_mode is not None:
                updates.append("storage_mode = ?")
                params.append(storage_mode)
            if header_color is not _UNSET:
                updates.append("header_color = ?")
                params.append(header_color)
            if archived_at is not _UNSET:
                updates.append("archived_at = ?")
                params.append(archived_at)
            if not updates:
                return proj
            params.append(project_id)
            conn.execute(f"UPDATE project SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
            return self.get_project(project_id)
        finally:
            conn.close()

    def delete_project(self, project_id: str, *, conn: sqlite3.Connection | None = None) -> bool:
        own = conn is None
        c = conn or self._conn()
        try:
            cur = c.execute("DELETE FROM project WHERE id = ?", (project_id,))
            if own:
                c.commit()
            return cur.rowcount > 0
        finally:
            if own:
                c.close()


class SqliteWorkflowAppRepository:
    def __init__(self, db_path: str | Path):
        self._db_path = str(Path(db_path).resolve())

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def create_app(
        self,
        id: str,
        workflow_version_id: str,
        slug: str,
        title: str,
        description: str | None,
        ui_config_json: str,
        default_inputs_json: str | None,
        default_outputs_json: str | None,
        is_public: bool,
        created_at: int,
        app_version: str = "1.0.0",
        comfyui_url: str | None = None,
        supported_input_kinds_json: str | None = None,
        header_color: str | None = None,
        tags_json: str | None = None,
        created_from_image_import: bool = False,
        embed_workflowui_metadata_on_download: bool | None = None,
        embed_workflowui_metadata_on_save: bool | None = None,
    ) -> WorkflowApp:
        def _bool_to_int(b: bool | None) -> int | None:
            return (1 if b else 0) if b is not None else None
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO workflow_app
                   (id, workflow_version_id, slug, title, description, ui_config_json,
                    default_inputs_json, default_outputs_json, is_public, created_at, app_version, comfyui_url, supported_input_kinds_json, header_color, tags_json, created_from_image_import, embed_workflowui_metadata_on_download, embed_workflowui_metadata_on_save)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    id,
                    workflow_version_id,
                    slug,
                    title,
                    description,
                    ui_config_json,
                    default_inputs_json,
                    default_outputs_json,
                    1 if is_public else 0,
                    created_at,
                    app_version or "1.0.0",
                    comfyui_url,
                    supported_input_kinds_json,
                    header_color,
                    tags_json,
                    1 if created_from_image_import else 0,
                    _bool_to_int(embed_workflowui_metadata_on_download),
                    _bool_to_int(embed_workflowui_metadata_on_save),
                ),
            )
            conn.commit()
            return WorkflowApp(
                id=id,
                workflow_version_id=workflow_version_id,
                slug=slug,
                title=title,
                description=description,
                ui_config_json=ui_config_json,
                default_inputs_json=default_inputs_json,
                default_outputs_json=default_outputs_json,
                is_public=is_public,
                created_at=created_at,
                app_version=app_version or "1.0.0",
                comfyui_url=comfyui_url,
                supported_input_kinds_json=supported_input_kinds_json,
                header_color=header_color,
                tags_json=tags_json,
                created_from_image_import=created_from_image_import,
                embed_workflowui_metadata_on_download=embed_workflowui_metadata_on_download,
                embed_workflowui_metadata_on_save=embed_workflowui_metadata_on_save,
            )
        finally:
            conn.close()

    _APP_SELECT_COLS = """id, workflow_version_id, slug, title, description, ui_config_json,
        default_inputs_json, default_outputs_json, is_public, created_at, app_version, comfyui_url, supported_input_kinds_json, header_color, tags_json, created_from_image_import, embed_workflowui_metadata_on_download, embed_workflowui_metadata_on_save"""

    def get_app_by_slug(self, slug: str) -> WorkflowApp | None:
        conn = self._conn()
        try:
            row = conn.execute(
                f"SELECT {self._APP_SELECT_COLS} FROM workflow_app WHERE slug = ?",
                (slug,),
            ).fetchone()
            return _row_to_workflow_app(row) if row else None
        finally:
            conn.close()

    def get_app_by_id(self, app_id: str) -> WorkflowApp | None:
        conn = self._conn()
        try:
            row = conn.execute(
                f"SELECT {self._APP_SELECT_COLS} FROM workflow_app WHERE id = ?",
                (app_id,),
            ).fetchone()
            return _row_to_workflow_app(row) if row else None
        finally:
            conn.close()

    def get_apps_by_workflow_version_id(self, workflow_version_id: str) -> list[WorkflowApp]:
        conn = self._conn()
        try:
            rows = conn.execute(
                f"SELECT {self._APP_SELECT_COLS} FROM workflow_app WHERE workflow_version_id = ? ORDER BY created_at ASC",
                (workflow_version_id,),
            ).fetchall()
            return [_row_to_workflow_app(r) for r in rows]
        finally:
            conn.close()

    def get_app_by_workflow_graph_hash(self, graph_hash: str) -> WorkflowApp | None:
        conn = self._conn()
        try:
            row = conn.execute(
                f"""SELECT {self._APP_SELECT_COLS} FROM workflow_app
                   WHERE workflow_version_id IN (SELECT id FROM workflow_version WHERE graph_hash = ?)
                   ORDER BY created_at ASC LIMIT 1""",
                (graph_hash,),
            ).fetchone()
            return _row_to_workflow_app(row) if row else None
        finally:
            conn.close()

    def delete_apps_by_workflow_version_ids(self, version_ids: list[str], *, conn: sqlite3.Connection | None = None) -> None:
        if not version_ids:
            return
        placeholders = ",".join("?" * len(version_ids))
        own = conn is None
        c = conn or self._conn()
        try:
            c.execute(
                f"DELETE FROM workflow_app WHERE workflow_version_id IN ({placeholders})",
                version_ids,
            )
            if own:
                c.commit()
        finally:
            if own:
                c.close()

    def delete_app_by_id(self, app_id: str, *, conn: sqlite3.Connection | None = None) -> None:
        own = conn is None
        c = conn or self._conn()
        try:
            c.execute("DELETE FROM workflow_app WHERE id = ?", (app_id,))
            if own:
                c.commit()
        finally:
            if own:
                c.close()

    def list_public_apps(self) -> list[WorkflowApp]:
        conn = self._conn()
        try:
            rows = conn.execute(
                f"SELECT {self._APP_SELECT_COLS} FROM workflow_app WHERE is_public = 1 ORDER BY created_at DESC",
            ).fetchall()
            return [_row_to_workflow_app(r) for r in rows]
        finally:
            conn.close()

    def list_all_apps(self) -> list[WorkflowApp]:
        conn = self._conn()
        try:
            rows = conn.execute(
                f"SELECT {self._APP_SELECT_COLS} FROM workflow_app ORDER BY created_at DESC",
            ).fetchall()
            return [_row_to_workflow_app(r) for r in rows]
        finally:
            conn.close()

    def update_app(
        self,
        slug: str,
        *,
        title: str | None = None,
        description: str | None = None,
        ui_config_json: str | None = None,
        default_inputs_json: str | None = None,
        default_outputs_json: str | None = None,
        is_public: bool | None = None,
        comfyui_url: str | None = None,
        supported_input_kinds_json: str | None = None,
        header_color: str | None = _UNSET,
        tags_json: str | None = _UNSET,
        embed_workflowui_metadata_on_download: bool | None = _UNSET,
        embed_workflowui_metadata_on_save: bool | None = _UNSET,
        new_slug: str | None = None,
    ) -> WorkflowApp | None:
        def _bool_to_int(b: bool | None) -> int | None:
            return (1 if b else 0) if b is not None else None
        conn = self._conn()
        try:
            app = self.get_app_by_slug(slug)
            if not app:
                return None
            updates: list[str] = []
            params: list[object] = []
            if title is not None:
                updates.append("title = ?")
                params.append(title)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if ui_config_json is not None:
                updates.append("ui_config_json = ?")
                params.append(ui_config_json)
            if default_inputs_json is not None:
                updates.append("default_inputs_json = ?")
                params.append(default_inputs_json)
            if default_outputs_json is not None:
                updates.append("default_outputs_json = ?")
                params.append(default_outputs_json)
            if is_public is not None:
                updates.append("is_public = ?")
                params.append(1 if is_public else 0)
            if comfyui_url is not None:
                updates.append("comfyui_url = ?")
                params.append(comfyui_url)
            if supported_input_kinds_json is not None:
                updates.append("supported_input_kinds_json = ?")
                params.append(supported_input_kinds_json)
            if header_color is not _UNSET:
                updates.append("header_color = ?")
                params.append(header_color)
            if tags_json is not _UNSET:
                updates.append("tags_json = ?")
                params.append(tags_json)
            if embed_workflowui_metadata_on_download is not _UNSET:
                updates.append("embed_workflowui_metadata_on_download = ?")
                params.append(_bool_to_int(embed_workflowui_metadata_on_download))
            if embed_workflowui_metadata_on_save is not _UNSET:
                updates.append("embed_workflowui_metadata_on_save = ?")
                params.append(_bool_to_int(embed_workflowui_metadata_on_save))
            if new_slug is not None:
                updates.append("slug = ?")
                params.append(new_slug)
            if not updates:
                return app
            params.append(slug)
            conn.execute(
                f"UPDATE workflow_app SET {', '.join(updates)} WHERE slug = ?",
                params,
            )
            conn.commit()
            return self.get_app_by_slug(new_slug or slug)
        finally:
            conn.close()


class SqliteRunRepository:
    def __init__(self, db_path: str | Path):
        self._db_path = str(Path(db_path).resolve())

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def get_comfyui_version_metadata(self, comfyui_version_id: str) -> dict | None:
        """Return parsed metadata_json for a comfyui_version row, or None."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT metadata_json FROM comfyui_version WHERE id = ?",
                (comfyui_version_id,),
            ).fetchone()
            if not row or not row[0]:
                return None
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return None
        finally:
            conn.close()

    def get_resolved_metadata_snapshot(self, run: Run) -> dict:
        """Return full metadata_snapshot dict, merging in ComfyUI-VersionInfo from comfyui_version if run.comfyui_version_id is set."""
        current: dict = {}
        if run.metadata_snapshot_json:
            try:
                current = json.loads(run.metadata_snapshot_json)
            except (json.JSONDecodeError, TypeError):
                pass
        if not isinstance(current, dict):
            current = {}
        if run.comfyui_version_id:
            resolved = self.get_comfyui_version_metadata(run.comfyui_version_id)
            if isinstance(resolved, dict):
                current["ComfyUI-VersionInfo"] = resolved
        return current

    def get_or_create_comfyui_version(self, version_info: dict[str, Any]) -> str:
        """Get existing comfyui_version id by hash or insert new row. Returns id."""
        meta_hash = compute_comfyui_metadata_hash(version_info)
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT id FROM comfyui_version WHERE metadata_hash = ?",
                (meta_hash,),
            ).fetchone()
            if row:
                return row[0]
            version_id = str(uuid.uuid4())
            base_url = version_info.get("comfyui_base_url") or ""
            metadata_json = json.dumps(version_info, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            created_at = int(time.time() * 1000)
            conn.execute(
                """INSERT INTO comfyui_version (id, metadata_hash, comfyui_base_url, metadata_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (version_id, meta_hash, base_url, metadata_json, created_at),
            )
            conn.commit()
            return version_id
        finally:
            conn.close()

    def create_run(
        self,
        id: str,
        project_id: str,
        workflow_version_id: str,
        app_id: str | None,
        status: str,
        created_at: int,
        prompt_id: str | None = None,
        seed: int | None = None,
        images_json: str | None = None,
        media_json: str | None = None,
        execution_time: float | None = None,
        error: str | None = None,
        queue_position: int | None = None,
        input_snapshot_json: str | None = None,
        metadata_snapshot_json: str | None = None,
        run_group_id: str | None = None,
        comfyui_url: str | None = None,
        comfyui_version_id: str | None = None,
        local_storage_status: str | None = "none",
        remote_status: str | None = "unknown",
        local_path: str | None = None,
        deleted_outputs_json: str | None = None,
        parent_run_id: str | None = None,
        parent_media_id: str | None = None,
        root_run_id: str | None = None,
    ) -> Run:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO run
                   (id, project_id, workflow_version_id, app_id, status, created_at, prompt_id, seed,
                    images_json, media_json, execution_time, error, queue_position, input_snapshot_json, metadata_snapshot_json, run_group_id, comfyui_url, comfyui_version_id,
                    local_storage_status, remote_status, local_path, deleted_outputs_json,
                    parent_run_id, parent_media_id, root_run_id, deleted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    id,
                    project_id,
                    workflow_version_id,
                    app_id,
                    status,
                    created_at,
                    prompt_id,
                    seed,
                    images_json,
                    media_json,
                    execution_time,
                    error,
                    queue_position,
                    input_snapshot_json,
                    metadata_snapshot_json,
                    run_group_id,
                    comfyui_url,
                    comfyui_version_id,
                    local_storage_status,
                    remote_status,
                    local_path,
                    deleted_outputs_json,
                    parent_run_id,
                    parent_media_id,
                    root_run_id,
                    None,
                ),
            )
            conn.commit()
            return Run(
                id=id,
                project_id=project_id,
                workflow_version_id=workflow_version_id,
                app_id=app_id,
                status=status,
                created_at=created_at,
                run_group_id=run_group_id,
                prompt_id=prompt_id,
                seed=seed,
                images_json=images_json,
                media_json=media_json,
                execution_time=execution_time,
                error=error,
                queue_position=queue_position,
                input_snapshot_json=input_snapshot_json,
                metadata_snapshot_json=metadata_snapshot_json,
                comfyui_url=comfyui_url,
                comfyui_version_id=comfyui_version_id,
                local_storage_status=local_storage_status,
                remote_status=remote_status,
                local_path=local_path,
                deleted_outputs_json=deleted_outputs_json,
                parent_run_id=parent_run_id,
                parent_media_id=parent_media_id,
                root_run_id=root_run_id,
                deleted_at=None,
            )
        finally:
            conn.close()

    def get_run(self, run_id: str) -> Run | None:
        conn = self._conn()
        try:
            row = conn.execute(
                f"SELECT {_run_select_cols()} FROM run WHERE id = ?",
                (run_id,),
            ).fetchone()
            return _row_to_run(row) if row else None
        finally:
            conn.close()

    def get_saved_queue(self, queue_id: str = "default") -> tuple[list[str], int] | None:
        """Returns (run_ids list, updated_at) or None if not found."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT run_ids, updated_at FROM saved_queue WHERE id = ?",
                (queue_id,),
            ).fetchone()
            if not row:
                return None
            raw = row[0]
            if isinstance(raw, str):
                try:
                    run_ids = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    return None
            else:
                run_ids = []
            if not isinstance(run_ids, list):
                return None
            return (run_ids, int(row[1]))
        except sqlite3.OperationalError:
            return None
        finally:
            conn.close()

    def set_saved_queue(self, run_ids: list[str], queue_id: str = "default") -> None:
        conn = self._conn()
        try:
            updated_at = int(time.time() * 1000)
            conn.execute(
                "INSERT INTO saved_queue (id, run_ids, updated_at) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET run_ids = excluded.run_ids, updated_at = excluded.updated_at",
                (queue_id, json.dumps(run_ids), updated_at),
            )
            conn.commit()
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()

    def get_run_by_prompt_id(self, prompt_id: str) -> Run | None:
        conn = self._conn()
        try:
            row = conn.execute(
                f"SELECT {_run_select_cols()} FROM run WHERE prompt_id = ?",
                (prompt_id,),
            ).fetchone()
            return _row_to_run(row) if row else None
        finally:
            conn.close()

    def get_child_runs(self, parent_run_id: str, limit: int = 50) -> list[Run]:
        conn = self._conn()
        try:
            rows = conn.execute(
                f"SELECT {_run_select_cols()} FROM run WHERE parent_run_id = ? ORDER BY created_at DESC LIMIT ?",
                (parent_run_id, limit),
            ).fetchall()
            return [_row_to_run(r) for r in rows]
        finally:
            conn.close()

    def delete_run(self, run_id: str) -> bool:
        conn = self._conn()
        try:
            cur = conn.execute("DELETE FROM run WHERE id = ?", (run_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def delete_runs_by_project(
        self, project_id: str, *, conn: sqlite3.Connection | None = None
    ) -> int:
        own = conn is None
        c = conn or self._conn()
        try:
            cur = c.execute("DELETE FROM run WHERE project_id = ?", (project_id,))
            if own:
                c.commit()
            return cur.rowcount
        finally:
            if own:
                c.close()

    def list_runs_containing_image(
        self, filename: str, subfolder: str, type: str, *, limit: int = 2000
    ) -> list[Run]:
        conn = self._conn()
        try:
            rows = conn.execute(
                f"SELECT {_run_select_cols()} FROM run WHERE images_json IS NOT NULL AND images_json != '' ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            runs = [_row_to_run(r) for r in rows]
        finally:
            conn.close()
        out = []
        sub = subfolder or ""
        typ = (type or "output").strip().lower()
        for run in runs:
            try:
                images = json.loads(run.images_json) if run.images_json else []
            except Exception:
                continue
            for i, ent in enumerate(images):
                if not isinstance(ent, dict):
                    continue
                if ent.get("remote_deleted"):
                    continue
                if ent.get("filename") != filename:
                    continue
                if (ent.get("subfolder") or "") != sub:
                    continue
                if (ent.get("type") or "output").strip().lower() != typ:
                    continue
                out.append(run)
                break
        return out

    def get_runs_for_app(self, app_id: str, limit: int = 50) -> list[Run]:
        conn = self._conn()
        try:
            rows = conn.execute(
                f"SELECT {_run_select_cols()} FROM run WHERE app_id = ? ORDER BY created_at DESC LIMIT ?",
                (app_id, limit),
            ).fetchall()
            return [_row_to_run(r) for r in rows]
        finally:
            conn.close()

    def get_last_run_timestamps_for_app_ids(self, app_ids: list[str]) -> dict[str, int]:
        if not app_ids:
            return {}
        conn = self._conn()
        try:
            placeholders = ",".join("?" * len(app_ids))
            rows = conn.execute(
                "SELECT app_id, MAX(created_at) FROM run WHERE app_id IN (" + placeholders + ") GROUP BY app_id",
                app_ids,
            ).fetchall()
            return {r[0]: r[1] for r in rows}
        finally:
            conn.close()

    def get_project_ids_for_app(self, app_id: str) -> list[str]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT DISTINCT project_id FROM run WHERE app_id = ? AND (deleted_at IS NULL)",
                (app_id,),
            ).fetchall()
            return [r[0] for r in rows]
        finally:
            conn.close()

    @staticmethod
    def _escape_like(s: str) -> str:
        return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def get_runs_by_project(
        self,
        project_id: str,
        *,
        app_id: str | None = None,
        tag: str | None = None,
        workflow_version_id: str | None = None,
        since_ts: int | None = None,
        until_ts: int | None = None,
        meta_q: str | None = None,
        deleted_app: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Run]:
        conn = self._conn()
        try:
            base_sql = " FROM run WHERE project_id = ? AND (deleted_at IS NULL)"
            params: list[Any] = [project_id]
            if app_id is not None:
                base_sql += " AND app_id = ?"
                params.append(app_id)
            if workflow_version_id is not None:
                base_sql += " AND workflow_version_id = ?"
                params.append(workflow_version_id)
            if since_ts is not None:
                base_sql += " AND created_at >= ?"
                params.append(since_ts)
            if until_ts is not None:
                base_sql += " AND created_at <= ?"
                params.append(until_ts)
            if meta_q:
                pattern = f"%{self._escape_like(meta_q)}%"
                base_sql += " AND (metadata_snapshot_json LIKE ? ESCAPE '\\' OR input_snapshot_json LIKE ? ESCAPE '\\')"
                params.extend([pattern, pattern])
            if deleted_app:
                base_sql += (
                    " AND (app_id IS NULL OR app_id = '' OR NOT EXISTS ("
                    "SELECT 1 FROM workflow_app wa WHERE wa.id = run.app_id"
                    "))"
                )

            group_sql = (
                "SELECT COALESCE(run_group_id, id) AS group_id"
                + base_sql
                + " GROUP BY COALESCE(run_group_id, id) ORDER BY MAX(created_at) DESC LIMIT ? OFFSET ?"
            )
            group_params = list(params) + [limit, offset]
            group_rows = conn.execute(group_sql, group_params).fetchall()
            group_ids = [row[0] for row in group_rows]
            if not group_ids:
                return []

            placeholders = ",".join("?" * len(group_ids))
            run_sql = (
                f"SELECT {_run_select_cols()} FROM run WHERE project_id = ? AND (deleted_at IS NULL)"
            )
            run_params: list[Any] = [project_id]
            if app_id is not None:
                run_sql += " AND app_id = ?"
                run_params.append(app_id)
            if workflow_version_id is not None:
                run_sql += " AND workflow_version_id = ?"
                run_params.append(workflow_version_id)
            if since_ts is not None:
                run_sql += " AND created_at >= ?"
                run_params.append(since_ts)
            if until_ts is not None:
                run_sql += " AND created_at <= ?"
                run_params.append(until_ts)
            if meta_q:
                run_sql += " AND (metadata_snapshot_json LIKE ? ESCAPE '\\' OR input_snapshot_json LIKE ? ESCAPE '\\')"
                run_params.extend([pattern, pattern])
            if deleted_app:
                run_sql += (
                    " AND (app_id IS NULL OR app_id = '' OR NOT EXISTS ("
                    "SELECT 1 FROM workflow_app wa WHERE wa.id = run.app_id"
                    "))"
                )
            run_sql += f" AND COALESCE(run_group_id, id) IN ({placeholders}) ORDER BY created_at DESC"
            run_params.extend(group_ids)
            rows = conn.execute(run_sql, run_params).fetchall()
            runs = [_row_to_run(r) for r in rows]
            if tag:
                pass
            return runs
        finally:
            conn.close()

    def count_runs_by_project(self, project_id: str) -> int:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT COUNT(DISTINCT COALESCE(run_group_id, id)) FROM run WHERE project_id = ? AND (deleted_at IS NULL)""",
                (project_id,),
            ).fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def count_runs_by_project_filtered(
        self,
        project_id: str,
        *,
        app_id: str | None = None,
        workflow_version_id: str | None = None,
        since_ts: int | None = None,
        until_ts: int | None = None,
        meta_q: str | None = None,
        deleted_app: bool | None = None,
    ) -> int:
        conn = self._conn()
        try:
            sql = "SELECT COUNT(DISTINCT COALESCE(run_group_id, id)) FROM run WHERE project_id = ? AND (deleted_at IS NULL)"
            params: list[Any] = [project_id]
            if app_id is not None:
                sql += " AND app_id = ?"
                params.append(app_id)
            if workflow_version_id is not None:
                sql += " AND workflow_version_id = ?"
                params.append(workflow_version_id)
            if since_ts is not None:
                sql += " AND created_at >= ?"
                params.append(since_ts)
            if until_ts is not None:
                sql += " AND created_at <= ?"
                params.append(until_ts)
            if meta_q:
                pattern = f"%{self._escape_like(meta_q)}%"
                sql += " AND (metadata_snapshot_json LIKE ? ESCAPE '\\' OR input_snapshot_json LIKE ? ESCAPE '\\')"
                params.extend([pattern, pattern])
            if deleted_app:
                sql += (
                    " AND (app_id IS NULL OR app_id = '' OR NOT EXISTS ("
                    "SELECT 1 FROM workflow_app wa WHERE wa.id = run.app_id"
                    "))"
                )
            row = conn.execute(sql, params).fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def count_run_rows_by_project_filtered(
        self,
        project_id: str,
        *,
        app_id: str | None = None,
        workflow_version_id: str | None = None,
        since_ts: int | None = None,
        until_ts: int | None = None,
        meta_q: str | None = None,
        deleted_app: bool | None = None,
    ) -> int:
        conn = self._conn()
        try:
            sql = "SELECT COUNT(*) FROM run WHERE project_id = ? AND (deleted_at IS NULL)"
            params: list[Any] = [project_id]
            if app_id is not None:
                sql += " AND app_id = ?"
                params.append(app_id)
            if workflow_version_id is not None:
                sql += " AND workflow_version_id = ?"
                params.append(workflow_version_id)
            if since_ts is not None:
                sql += " AND created_at >= ?"
                params.append(since_ts)
            if until_ts is not None:
                sql += " AND created_at <= ?"
                params.append(until_ts)
            if meta_q:
                pattern = f"%{self._escape_like(meta_q)}%"
                sql += " AND (metadata_snapshot_json LIKE ? ESCAPE '\\' OR input_snapshot_json LIKE ? ESCAPE '\\')"
                params.extend([pattern, pattern])
            if deleted_app:
                sql += (
                    " AND (app_id IS NULL OR app_id = '' OR NOT EXISTS ("
                    "SELECT 1 FROM workflow_app wa WHERE wa.id = run.app_id"
                    "))"
                )
            row = conn.execute(sql, params).fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def move_runs_to_project(
        self, run_ids: list[str], target_project_id: str, *, conn: sqlite3.Connection | None = None
    ) -> int:
        if not run_ids:
            return 0
        own = conn is None
        c = conn or self._conn()
        try:
            placeholders = ",".join("?" * len(run_ids))
            cur = c.execute(
                f"UPDATE run SET project_id = ? WHERE id IN ({placeholders})",
                [target_project_id] + run_ids,
            )
            if own:
                c.commit()
            return cur.rowcount
        finally:
            if own:
                c.close()

    def null_app_ids(self, app_ids: list[str], *, conn: sqlite3.Connection | None = None) -> None:
        if not app_ids:
            return
        own = conn is None
        c = conn or self._conn()
        try:
            placeholders = ",".join("?" * len(app_ids))
            c.execute(f"UPDATE run SET app_id = NULL WHERE app_id IN ({placeholders})", app_ids)
            if own:
                c.commit()
        finally:
            if own:
                c.close()

    def update_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        prompt_id: str | None = None,
        seed: int | None = None,
        images_json: str | None = None,
        media_json: str | None = None,
        execution_time: float | None = None,
        error: str | None = None,
        queue_position: int | None = None,
        local_storage_status: str | None = None,
        remote_status: str | None = None,
        local_path: str | None = None,
        metadata_snapshot_json: str | None = None,
        deleted_outputs_json: str | None = None,
        deleted_at: int | None = None,
        comfyui_version_id: str | None = None,
    ) -> None:
        updates = []
        params = []
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if prompt_id is not None:
            updates.append("prompt_id = ?")
            params.append(prompt_id)
        if seed is not None:
            updates.append("seed = ?")
            params.append(seed)
        if images_json is not None:
            updates.append("images_json = ?")
            params.append(images_json)
        if media_json is not None:
            updates.append("media_json = ?")
            params.append(media_json)
        if execution_time is not None:
            updates.append("execution_time = ?")
            params.append(execution_time)
        if error is not None:
            updates.append("error = ?")
            params.append(error)
        if queue_position is not None:
            updates.append("queue_position = ?")
            params.append(queue_position)
        if local_storage_status is not None:
            updates.append("local_storage_status = ?")
            params.append(local_storage_status)
        if remote_status is not None:
            updates.append("remote_status = ?")
            params.append(remote_status)
        if local_path is not None:
            updates.append("local_path = ?")
            params.append(local_path)
        if metadata_snapshot_json is not None:
            updates.append("metadata_snapshot_json = ?")
            params.append(metadata_snapshot_json)
        if deleted_outputs_json is not None:
            updates.append("deleted_outputs_json = ?")
            params.append(deleted_outputs_json)
        if deleted_at is not None:
            updates.append("deleted_at = ?")
            params.append(deleted_at)
        if comfyui_version_id is not None:
            updates.append("comfyui_version_id = ?")
            params.append(comfyui_version_id)
        if not updates:
            return
        params.append(run_id)
        conn = self._conn()
        try:
            conn.execute(
                f"UPDATE run SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()
        finally:
            conn.close()


class SqliteAppPresetRepository:
    def __init__(self, db_path: str | Path):
        self._db_path = str(Path(db_path).resolve())

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def list_by_app_id(self, app_id: str) -> list[AppPreset]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT id, app_id, name, description, keys_json, values_json, created_at
                   FROM app_preset WHERE app_id = ? ORDER BY created_at DESC""",
                (app_id,),
            ).fetchall()
            return [_row_to_app_preset(r) for r in rows]
        finally:
            conn.close()

    def create(
        self,
        id: str,
        app_id: str,
        name: str,
        description: str | None,
        keys_json: str,
        values_json: str,
        created_at: int,
    ) -> AppPreset:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO app_preset (id, app_id, name, description, keys_json, values_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (id, app_id, name, description or None, keys_json, values_json, created_at),
            )
            conn.commit()
            return AppPreset(
                id=id,
                app_id=app_id,
                name=name,
                description=description,
                keys_json=keys_json,
                values_json=values_json,
                created_at=created_at,
            )
        finally:
            conn.close()

    def get_by_id(self, preset_id: str) -> AppPreset | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT id, app_id, name, description, keys_json, values_json, created_at
                   FROM app_preset WHERE id = ?""",
                (preset_id,),
            ).fetchone()
            return _row_to_app_preset(row) if row else None
        finally:
            conn.close()

    def delete(self, preset_id: str) -> bool:
        conn = self._conn()
        try:
            cur = conn.execute("DELETE FROM app_preset WHERE id = ?", (preset_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
