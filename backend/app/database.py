"""DB 엔진·세션 팩토리 (사양 §2.2, §8.2)."""
import os

from sqlalchemy import create_engine, event
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


def init_db() -> None:
    """Sprint 1: create_all 사용. Alembic 마이그레이션은 다음 스프린트."""
    from app import models  # noqa: F401  (모델 등록)

    Base.metadata.create_all(bind=engine)
