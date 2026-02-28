import sqlite3
from pathlib import Path

from db.migrate import migrate

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "workflow.db"

def init_db(db_path: Path | str | None = None) -> str:
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    schema_path = Path(__file__).resolve().parent / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()

    migrate(path)
    return str(path)
