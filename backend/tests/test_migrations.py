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



def test_populated_upgrade_to_manuscript_preservation_preserves_data(alembic_config):
    """A populated pre-preservation DB upgrades with revision defaults."""
    from sqlalchemy import text

    command.upgrade(alembic_config, "f9a1b2c3d4e5")

    engine = create_db_engine(_current_url())
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO projects (id, title) VALUES (1, 'populated')"
        ))
        conn.execute(text(
            "INSERT INTO chapters "
            "(id, project_id, volume, sort_order, title, content_md, status, word_count_cache) "
            "VALUES (1, 1, NULL, 0.0, 'one', 'old manuscript', '초고', 13)"
        ))
        conn.execute(text(
            "INSERT INTO refine_runs "
            "(id, chapter_id, route_hint, changed_ratio, report_json, result_text, accepted) "
            "VALUES (1, 1, 'standard', 0.1, '{}', 'refined', 0)"
        ))
    engine.dispose()

    command.upgrade(alembic_config, "head")

    engine = create_db_engine(_current_url())
    with engine.connect() as conn:
        chapter = conn.execute(text(
            "SELECT content_md, revision FROM chapters WHERE id = 1"
        )).mappings().one()
        run = conn.execute(text(
            "SELECT base_revision FROM refine_runs WHERE id = 1"
        )).mappings().one()
        snapshots = conn.execute(text("SELECT count(*) FROM chapter_snapshots")).scalar_one()
    engine.dispose()

    assert chapter["content_md"] == "old manuscript"
    assert chapter["revision"] == 0
    assert run["base_revision"] is None
    assert snapshots == 0


def test_startup_rejects_existing_db_missing_preservation_columns(alembic_config, monkeypatch):
    """Existing DBs must be migrated; startup must not silently patch them."""
    from app.database import assert_manuscript_schema_current

    monkeypatch.delenv("JIPPEEL_ALLOW_TEMP_CREATE_ALL", raising=False)
    command.upgrade(alembic_config, "f9a1b2c3d4e5")
    engine = create_db_engine(_current_url())
    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        assert_manuscript_schema_current(engine)
    engine.dispose()



def test_startup_accepts_alembic_head_schema(alembic_config, monkeypatch):
    from app.database import assert_manuscript_schema_current

    monkeypatch.delenv("JIPPEEL_ALLOW_TEMP_CREATE_ALL", raising=False)
    command.upgrade(alembic_config, "head")
    engine = create_db_engine(_current_url())
    assert_manuscript_schema_current(engine)
    engine.dispose()



def test_populated_historical_upgrade_from_initial_with_references(alembic_config):
    """Regression for FK failure while upgrading populated d85 DB through nullable volume."""
    from sqlalchemy import text

    command.upgrade(alembic_config, "d85fdcab0808")

    engine = create_db_engine(_current_url())
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO projects (id, title) VALUES (1, 'historical')"))
        conn.execute(text(
            "INSERT INTO chapters "
            "(id, project_id, volume, sort_order, title, content_md, status, word_count_cache) "
            "VALUES (1, 1, 1, 1.0, 'one', 'old manuscript', '초고', 13)"
        ))
        conn.execute(text(
            "INSERT INTO refine_runs "
            "(id, chapter_id, route_hint, changed_ratio, report_json, result_text, accepted) "
            "VALUES (1, 1, 'standard', 0.1, '{}', 'refined', 0)"
        ))
        conn.execute(text(
            "INSERT INTO characters (id, project_id, name, aliases, card_json) "
            "VALUES (1, 1, 'A', '[]', '{}')"
        ))
        conn.execute(text(
            "INSERT INTO characters (id, project_id, name, aliases, card_json) "
            "VALUES (2, 1, 'B', '[]', '{}')"
        ))
        conn.execute(text(
            "INSERT INTO relationships (id, from_character_id, to_character_id, label, note) "
            "VALUES (1, 1, 2, 'ally', 'kept')"
        ))
        conn.execute(text(
            "INSERT INTO lore_entries (id, project_id, category, title, content, keywords) "
            "VALUES (1, 1, '용어', '검', 'kept lore', '[]')"
        ))
    engine.dispose()

    command.upgrade(alembic_config, "head")

    engine = create_db_engine(_current_url())
    with engine.connect() as conn:
        chapter = conn.execute(text(
            "SELECT volume, content_md, revision FROM chapters WHERE id = 1"
        )).mappings().one()
        run = conn.execute(text(
            "SELECT chapter_id, base_revision FROM refine_runs WHERE id = 1"
        )).mappings().one()
        rel_count = conn.execute(text("SELECT count(*) FROM relationships WHERE note = 'kept'")).scalar_one()
        lore_count = conn.execute(text("SELECT count(*) FROM lore_entries WHERE content = 'kept lore'")).scalar_one()
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    engine.dispose()

    assert chapter == {"volume": 1, "content_md": "old manuscript", "revision": 0}
    assert run == {"chapter_id": 1, "base_revision": None}
    assert rel_count == 1
    assert lore_count == 1
    assert version == "0a1b2c3d4e5f"


def test_schema_guard_temp_bypass_uses_passed_engine_url(tmp_path, monkeypatch):
    from app import database

    allowed_root = tmp_path / "allowed-temp-root"
    allowed_root.mkdir()
    monkeypatch.setattr(database.tempfile, "gettempdir", lambda: str(allowed_root))
    monkeypatch.setenv("JIPPEEL_ALLOW_TEMP_CREATE_ALL", "1")
    monkeypatch.setattr(
        database,
        "DATABASE_URL",
        f"sqlite:///{(allowed_root / 'lifespan.db').as_posix()}",
    )

    other_root = tmp_path / "not-the-bound-engine-temp-root"
    other_root.mkdir()
    engine = create_db_engine(f"sqlite:///{(other_root / 'empty.db').as_posix()}")
    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        database.assert_manuscript_schema_current(engine)
    engine.dispose()
