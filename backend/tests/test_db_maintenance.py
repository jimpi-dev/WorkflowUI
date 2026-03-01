import pytest

from db.init import init_db
from db.maintenance import checkpoint_wal, vacuum_db


def test_vacuum_db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(str(db_path))
    vacuum_db(str(db_path))


def test_checkpoint_wal(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(str(db_path))
    checkpoint_wal(str(db_path), "PASSIVE")
    checkpoint_wal(str(db_path), "TRUNCATE")
