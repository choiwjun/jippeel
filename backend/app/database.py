"""DB 엔진·세션 팩토리 (사양 §2.2, §8.2)."""
import os
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# 기본: 프로젝트 루트의 SQLite 파일. 테스트/배포는 DATABASE_URL로 교체.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./jippeel.db")


class Base(DeclarativeBase):
    pass


def apply_sqlite_pragmas(dbapi_connection, connection_record) -> None:
    """SQLite 접속 프라그마 표준 (사양 §8.2 / 부록05 §⑤-4).

    모든 DB 세션에서 공통 적용:
      - journal_mode=WAL         : 읽기·쓰기 병행(자동저장+조회), NFR-204
      - synchronous=NORMAL       : WAL 모드에서 안전한 성능 최적점
      - busy_timeout=5000        : 쓰기 잠금 대기 (ms)
      - foreign_keys=ON          : FK 무결성 강제
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine(url: str | None = None) -> Engine:
    engine = create_engine(
        url or DATABASE_URL,
        connect_args={"check_same_thread": False},  # FastAPI 스레드풀 대응
    )
    event.listen(engine, "connect", apply_sqlite_pragmas)
    return engine


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


ALEMBIC_HEAD = "0a1b2c3d4e5f"
TEMP_CREATE_ALL_ENV = "JIPPEEL_ALLOW_TEMP_CREATE_ALL"


def _sqlite_file_from_url(url: str) -> Path | None:
    parsed = urlparse(url)
    if parsed.scheme != "sqlite" or not parsed.path or parsed.path == ":memory:":
        return None
    return Path(unquote(parsed.path[1:] if len(parsed.path) > 3 and parsed.path[0] == "/" and parsed.path[2] == ":" else parsed.path)).resolve()


def _allow_temp_create_all(url: str | None = None) -> bool:
    if os.environ.get(TEMP_CREATE_ALL_ENV) != "1":
        return False
    db_path = _sqlite_file_from_url(url or DATABASE_URL)
    if db_path is None:
        return False
    try:
        db_path.relative_to(Path(tempfile.gettempdir()).resolve())
        return True
    except ValueError:
        return False


def assert_manuscript_schema_current(bind: Engine) -> None:
    """Fail fast when an existing DB lacks preservation schema or Alembic head."""
    if _allow_temp_create_all(str(bind.url)):
        return

    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    problems: list[str] = []
    if "chapters" not in tables:
        problems.append("empty or unmigrated database")
    else:
        chapter_cols = {col["name"] for col in inspector.get_columns("chapters")}
        if "revision" not in chapter_cols:
            problems.append("chapters.revision")

        if "refine_runs" in tables:
            refine_cols = {col["name"] for col in inspector.get_columns("refine_runs")}
            if "base_revision" not in refine_cols:
                problems.append("refine_runs.base_revision")
        else:
            problems.append("refine_runs table")

        if "chapter_snapshots" not in tables:
            problems.append("chapter_snapshots table")
        else:
            unique_cols = {
                tuple(constraint.get("column_names") or [])
                for constraint in inspector.get_unique_constraints("chapter_snapshots")
            }
            if ("chapter_id", "revision") not in unique_cols:
                problems.append("chapter_snapshots(chapter_id, revision) unique")
            index_cols = {
                tuple(index.get("column_names") or [])
                for index in inspector.get_indexes("chapter_snapshots")
            }
            if ("chapter_id",) not in index_cols:
                problems.append("chapter_snapshots.chapter_id index")
            if ("created_at",) not in index_cols:
                problems.append("chapter_snapshots.created_at index")

    if "alembic_version" not in tables:
        problems.append("alembic_version table")
    else:
        with bind.connect() as connection:
            current = connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar()
        if current != ALEMBIC_HEAD:
            problems.append(f"alembic head {current!r} != {ALEMBIC_HEAD}")

    if problems:
        missing = ", ".join(problems)
        raise RuntimeError(
            f"DB schema is missing manuscript preservation objects ({missing}). "
            "Back up the database and run `alembic upgrade head` before starting the API."
        )


def init_db() -> None:
    """Initialize only explicitly marked temporary DBs; otherwise require Alembic."""
    from app import models  # noqa: F401  (모델 등록)

    assert_manuscript_schema_current(engine)
    if _allow_temp_create_all(str(engine.url)):
        Base.metadata.create_all(bind=engine)
