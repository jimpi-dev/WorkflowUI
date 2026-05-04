from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VaultInputRow:
    filename: str
    owner_user_id: str | None
    uploaded_at: int


class SqliteVaultInputRepository:
    def __init__(self, db_path: str | Path):
        self._db_path = str(Path(db_path).resolve())

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def record_upload(self, filename: str, owner_user_id: str | None, uploaded_at_ms: int | None = None) -> None:
        ts = uploaded_at_ms if uploaded_at_ms is not None else int(time.time() * 1000)
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO vault_input (filename, owner_user_id, uploaded_at)
                VALUES (?, ?, ?)
                ON CONFLICT(filename) DO UPDATE SET
                    owner_user_id = COALESCE(vault_input.owner_user_id, excluded.owner_user_id),
                    uploaded_at = excluded.uploaded_at
                """,
                (filename, owner_user_id, ts),
            )
            conn.commit()
        finally:
            conn.close()

    def get(self, filename: str) -> VaultInputRow | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT filename, owner_user_id, uploaded_at FROM vault_input WHERE filename = ?",
                (filename,),
            ).fetchone()
            if not row:
                return None
            return VaultInputRow(filename=row[0], owner_user_id=row[1], uploaded_at=int(row[2]))
        finally:
            conn.close()

    def delete_row(self, filename: str) -> None:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM vault_input WHERE filename = ?", (filename,))
            conn.commit()
        finally:
            conn.close()

    def list_all_rows(self) -> list[VaultInputRow]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT filename, owner_user_id, uploaded_at FROM vault_input ORDER BY uploaded_at DESC"
            ).fetchall()
            return [VaultInputRow(filename=r[0], owner_user_id=r[1], uploaded_at=int(r[2])) for r in rows]
        finally:
            conn.close()

    def list_rows_for_owner(self, user_id: str) -> list[VaultInputRow]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT filename, owner_user_id, uploaded_at FROM vault_input
                   WHERE owner_user_id = ?
                   ORDER BY uploaded_at DESC""",
                (user_id,),
            ).fetchall()
            return [VaultInputRow(filename=r[0], owner_user_id=r[1], uploaded_at=int(r[2])) for r in rows]
        finally:
            conn.close()
