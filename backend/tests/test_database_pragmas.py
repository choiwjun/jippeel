"""SQLite 프라그마 표준 적용 검증 (사양 §8.2)."""
from app.database import create_db_engine


def test_pragmas_applied(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'p.db'}")
    with engine.connect() as conn:
        mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
        sync = conn.exec_driver_sql("PRAGMA synchronous").scalar()
        busy = conn.exec_driver_sql("PRAGMA busy_timeout").scalar()
        fk = conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
    engine.dispose()
    assert str(mode).lower() == "wal"
    assert int(sync) == 1  # NORMAL
    assert int(busy) == 5000
    assert int(fk) == 1
