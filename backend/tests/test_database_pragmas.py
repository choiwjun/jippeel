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


# ---------- _sqlite_file_from_url 경로 해석 ----------

def test_sqlite_file_from_url_relative(tmp_path, monkeypatch):
    """`sqlite:///./x.db`는 엔진과 동일하게 cwd 기준으로 해석해야 한다.

    회귀: urlparse는 `/./x.db`를 반환해 naive Path 해석이 루트(`C:\\x.db`)로
    잘못 잡혀 자동 백업이 존재하지 않는 파일을 대상으로 삼았다.
    """
    from app.database import _sqlite_file_from_url

    monkeypatch.chdir(tmp_path)
    resolved = _sqlite_file_from_url("sqlite:///./jippeel.db")
    assert resolved == (tmp_path / "jippeel.db").resolve()


def test_sqlite_file_from_url_absolute(tmp_path):
    from app.database import _sqlite_file_from_url

    db = tmp_path / "abs.db"
    resolved = _sqlite_file_from_url(f"sqlite:///{db}")
    assert resolved == db.resolve()


def test_sqlite_file_from_url_memory_and_non_sqlite():
    from app.database import _sqlite_file_from_url

    assert _sqlite_file_from_url("sqlite:///:memory:") is None
    assert _sqlite_file_from_url("postgresql://u:p@h/db") is None
