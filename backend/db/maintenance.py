"""SQLite maintenance: VACUUM and WAL checkpoint for space reclamation and WAL control."""
from __future__ import annotations

import sqlite3
from pathlib import Path


def vacuum_db(db_path: Path | str) -> None:
    """Run VACUUM to reclaim free pages and shrink the database file.
    Call after bulk deletes or periodically during low usage.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("VACUUM")
    finally:
        conn.close()


def checkpoint_wal(db_path: Path | str, mode: str = "TRUNCATE") -> None:
    """Checkpoint WAL so the WAL file does not grow unbounded.
    mode: PASSIVE, FULL, RESTART, or TRUNCATE. TRUNCATE truncates the WAL file after checkpoint.
    Call during maintenance windows or periodically.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(f"PRAGMA wal_checkpoint({mode})")
    finally:
        conn.close()
