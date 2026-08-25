"""Alembic 마이그레이션 검증 (Sprint 2).

- upgrade head: 모든 모델 테이블 + FTS 인덱스가 생성되는지
- downgrade base: 롤백 가능 여부
"""
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.database import Base, create_db_engine


@pytest.fixture()
def alembic_config(tmp_path, monkeypatch):
    """임시 DB를 향한 프로젝트 alembic 설정.

    DATABASE_URL 환경변수로 마이그레이션 대상을 테스트 임시 DB로 고정하고,
    script_location은 %(here)s 기반(alembic.ini)이라 cwd와 무관하게 동작한다.
    """
    db_path = tmp_path / "migration.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)
    return Config("alembic.ini")


def _current_url() -> str:
    import os

    return os.environ["DATABASE_URL"]


def test_upgrade_head_matches_metadata(alembic_config):
    command.upgrade(alembic_config, "head")

    engine = create_db_engine(_current_url())
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    expected = set(Base.metadata.tables.keys())

    missing = expected - tables
    assert not missing, f"마이그레이션 누락 테이블: {missing}"

    # FTS5 로어북 검색 인덱스 (선택 적용 — 지원 빌드에서는 반드시 존재)
    assert "lore_entries_fts" in tables
    engine.dispose()


def test_upgrade_head_then_downgrade_base(alembic_config):
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")

    engine = create_db_engine(_current_url())
    tables = set(inspect(engine).get_table_names())
    assert not (set(Base.metadata.tables.keys()) & tables)
    engine.dispose()


def test_upgrade_is_idempotent_at_head(alembic_config):
    command.upgrade(alembic_config, "head")
    # 이미 head인 상태에서 재실행해도 오류 없어야 함
    command.upgrade(alembic_config, "head")
