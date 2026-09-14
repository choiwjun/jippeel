"""Alembic 마이그레이션 검증 (Sprint 2).

- upgrade head: 모든 모델 테이블 + FTS 인덱스가 생성되는지
- downgrade base: 롤백 가능 여부
"""
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.database import Base, create_db_engine


_engines = []
_conns = []


@pytest.fixture(autouse=True)
def _dispose_engines():
    """테스트가 만든 엔진·Inspector 연결이 ResourceWarning을 내지 않게 매 테스트 폐기한다."""
    _engines.clear()
    _conns.clear()
    yield
    for conn in _conns:
        conn.close()
    _conns.clear()
    for engine in _engines:
        engine.dispose()
    _engines.clear()


def _engine(url: str):
    engine = create_db_engine(url)
    _engines.append(engine)
    return engine


def _inspect(engine):
    """inspect(engine)은 transient Inspector가 연결을 잡아두므로 명시적 연결로 바인딩한다."""
    conn = engine.connect()
    _conns.append(conn)
    return inspect(conn)


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

    engine = _engine(_current_url())
    inspector = _inspect(engine)
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

    engine = _engine(_current_url())
    tables = set(_inspect(engine).get_table_names())
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

    engine = _engine(_current_url())
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

    engine = _engine(_current_url())
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
    engine = _engine(_current_url())
    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        assert_manuscript_schema_current(engine)
    engine.dispose()



def test_startup_accepts_alembic_head_schema(alembic_config, monkeypatch):
    from app.database import assert_manuscript_schema_current

    monkeypatch.delenv("JIPPEEL_ALLOW_TEMP_CREATE_ALL", raising=False)
    command.upgrade(alembic_config, "head")
    engine = _engine(_current_url())
    assert_manuscript_schema_current(engine)
    engine.dispose()



def test_populated_historical_upgrade_from_initial_with_references(alembic_config):
    """Regression for FK failure while upgrading populated d85 DB through nullable volume."""
    from sqlalchemy import text

    command.upgrade(alembic_config, "d85fdcab0808")

    engine = _engine(_current_url())
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

    engine = _engine(_current_url())
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
    assert version == "d1e2f3a4b5c6"


def test_populated_upgrade_backfills_flow_stage(alembic_config):
    """D03-1 — 기존 행의 flow_stage를 status·본문 유무로 근사 매핑한다."""
    from sqlalchemy import text

    command.upgrade(alembic_config, "2c3d4e5f6a70")  # D01 head — flow_stage 이전

    engine = _engine(_current_url())
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO projects (id, title) VALUES (1, 'p')"))
        conn.execute(text(
            "INSERT INTO chapters "
            "(id, project_id, sort_order, title, content_md, status, word_count_cache) "
            "VALUES (1, 1, 0.0, 'a', 'text', '초고', 4)"
        ))
        conn.execute(text(
            "INSERT INTO chapters "
            "(id, project_id, sort_order, title, content_md, status, word_count_cache) "
            "VALUES (2, 1, 1.0, 'b', '', '초고', 0)"
        ))
        conn.execute(text(
            "INSERT INTO chapters "
            "(id, project_id, sort_order, title, content_md, status, word_count_cache) "
            "VALUES (3, 1, 2.0, 'c', 'text', '수정중', 4)"
        ))
        conn.execute(text(
            "INSERT INTO chapters "
            "(id, project_id, sort_order, title, content_md, status, word_count_cache) "
            "VALUES (4, 1, 3.0, 'd', 'text', '완료', 4)"
        ))
    engine.dispose()

    command.upgrade(alembic_config, "head")

    engine = _engine(_current_url())
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, flow_stage FROM chapters ORDER BY id")
        ).all()
        events = conn.execute(
            text("SELECT count(*) FROM chapter_flow_events")
        ).scalar_one()
        status_vals = conn.execute(
            text("SELECT status FROM chapters ORDER BY id")
        ).scalars().all()
    engine.dispose()

    assert [r[1] for r in rows] == ["writing", "planning", "revising", "confirmed"]
    assert events == 0
    assert status_vals == ["초고", "초고", "수정중", "완료"]  # status는 건드리지 않는다

    # 리빌드 후 ck_chapter_flow_stage check constraint가 실제로 강제된다
    engine = _engine(_current_url())
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO chapters "
                "(id, project_id, sort_order, title, content_md, status, word_count_cache, flow_stage) "
                "VALUES (9, 1, 9.0, 'bad', 'x', '초고', 1, 'bogus')"
            ))
    engine.dispose()


def test_populated_downgrade_from_head_removes_flow_keeps_data(alembic_config):
    """D03-1 downgrade — flow 컬럼·이벤트 테이블 제거, 기존 회차 데이터 보존."""
    from sqlalchemy import text

    command.upgrade(alembic_config, "head")

    engine = _engine(_current_url())
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO projects (id, title) VALUES (1, 'p')"))
        conn.execute(text(
            "INSERT INTO chapters "
            "(id, project_id, sort_order, title, content_md, status, word_count_cache, flow_stage) "
            "VALUES (1, 1, 0.0, 'a', 'kept manuscript', '수정중', 14, 'confirmed')"
        ))
        conn.execute(text(
            "INSERT INTO chapter_flow_events "
            "(chapter_id, from_stage, to_stage, goal_version, manuscript_revision, created_at) "
            "VALUES (1, 'revising', 'confirmed', NULL, 0, '2026-09-13T00:00:00')"
        ))
    engine.dispose()

    command.downgrade(alembic_config, "2c3d4e5f6a70")  # 3d4e(D03-1)→4e5f(D03-3)를 지나 한 번에 내린다

    engine = _engine(_current_url())
    inspector = _inspect(engine)
    assert "chapter_flow_events" not in inspector.get_table_names()
    assert "flow_stage" not in {c["name"] for c in inspector.get_columns("chapters")}
    project_cols = {c["name"] for c in inspector.get_columns("projects")}
    assert "serial_state" not in project_cols
    assert "serial_completed_at" not in project_cols
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT content_md, status, word_count_cache FROM chapters WHERE id = 1"
        )).mappings().one()
        # 4e5f downgrade는 projects 테이블을 재작성한다 — 행 자체가 살아 있어야 한다
        project_row = conn.execute(text(
            "SELECT title FROM projects WHERE id = 1"
        )).mappings().one()
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    engine.dispose()

    assert row == {"content_md": "kept manuscript", "status": "수정중", "word_count_cache": 14}
    assert project_row == {"title": "p"}
    assert version == "2c3d4e5f6a70"


def test_populated_upgrade_backfills_serial_state(alembic_config):
    """D03-3 — 기존 프로젝트는 serial_state='ongoing', completed_at=NULL로 backfill된다."""
    from sqlalchemy import text

    command.upgrade(alembic_config, "3d4e5f6a7b81")  # serial_state 이전 head

    engine = _engine(_current_url())
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO projects (id, title) VALUES (1, 'existing')"))
    engine.dispose()

    command.upgrade(alembic_config, "head")

    engine = _engine(_current_url())
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT serial_state, serial_completed_at, title FROM projects WHERE id = 1")
        ).mappings().one()
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    engine.dispose()

    assert row == {"serial_state": "ongoing", "serial_completed_at": None, "title": "existing"}
    assert version == "d1e2f3a4b5c6"

    # 리빌드 후 ck_project_serial_state가 강제된다
    engine = _engine(_current_url())
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO projects (id, title, serial_state) VALUES (2, 'bad', 'bogus')"
            ))
    engine.dispose()


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
    engine = _engine(f"sqlite:///{(other_root / 'empty.db').as_posix()}")
    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        database.assert_manuscript_schema_current(engine)
    engine.dispose()


def test_populated_upgrade_downgrade_evidence_links(alembic_config):
    """D03-4 — 4e5f head에서 upgrade 시 링크 테이블 생성, downgrade는 제거 + 데이터 보존."""
    from sqlalchemy import text

    command.upgrade(alembic_config, "4e5f6a7b8c92")  # 링크 테이블 이전 head

    engine = _engine(_current_url())
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO projects (id, title) VALUES (1, 'p')"))
        conn.execute(text(
            "INSERT INTO chapters "
            "(id, project_id, sort_order, title, content_md, status, word_count_cache, flow_stage) "
            "VALUES (1, 1, 0.0, 'a', '본문 발췌 포함', '초고', 3, 'writing')"
        ))
    engine.dispose()

    command.upgrade(alembic_config, "head")

    engine = _engine(_current_url())
    inspector = _inspect(engine)
    assert "chapter_goal_evidence_links" in inspector.get_table_names()
    link_cols = {c["name"] for c in inspector.get_columns("chapter_goal_evidence_links")}
    assert {"goal_version", "goal_field", "item_index", "goal_item_text", "excerpt"} <= link_cols
    link_indexes = {
        tuple(i["column_names"]) for i in inspector.get_indexes("chapter_goal_evidence_links")
    }
    assert ("chapter_id",) in link_indexes
    # 헤드에서 링크 작성·조회가 된다
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO chapter_goal_evidence_links "
            "(chapter_id, goal_version, goal_field, item_index, goal_item_text, excerpt, created_at) "
            "VALUES (1, 1, 'core_events', 0, '검을 뽑는다', '본문 발췌', '2026-09-13T00:00:00')"
        ))
        row = conn.execute(text(
            "SELECT goal_field, excerpt FROM chapter_goal_evidence_links WHERE chapter_id = 1"
        )).mappings().one()
    engine.dispose()
    assert row == {"goal_field": "core_events", "excerpt": "본문 발췌"}

    # check constraint 강제
    engine = _engine(_current_url())
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO chapter_goal_evidence_links "
                "(chapter_id, goal_version, goal_field, goal_item_text, excerpt, created_at) "
                "VALUES (1, 1, 'bogus', 'x', 'y', '2026-09-13T00:00:00')"
            ))
    engine.dispose()

    # populated downgrade — 테이블 제거 + 기존 데이터 보존
    command.downgrade(alembic_config, "4e5f6a7b8c92")

    engine = _engine(_current_url())
    inspector = _inspect(engine)
    assert "chapter_goal_evidence_links" not in inspector.get_table_names()
    with engine.connect() as conn:
        chapter_row = conn.execute(text(
            "SELECT title, content_md FROM chapters WHERE id = 1"
        )).mappings().one()
        project_row = conn.execute(text(
            "SELECT serial_state FROM projects WHERE id = 1"
        )).mappings().one()
    engine.dispose()
    assert chapter_row == {"title": "a", "content_md": "본문 발췌 포함"}
    assert project_row == {"serial_state": "ongoing"}


def test_populated_upgrade_downgrade_foreshadow_disposition(alembic_config):
    """D03-5 — 5f6a head에서 upgrade 시 disposition 컬럼+제약 추가, downgrade는 제거+행 보존."""
    from sqlalchemy import text

    command.upgrade(alembic_config, "5f6a7b8c9d03")  # disposition 이전 head

    engine = _engine(_current_url())
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO projects (id, title) VALUES (1, 'p')"))
        conn.execute(text(
            "INSERT INTO foreshadows (id, project_id, title, status) "
            "VALUES (1, 1, '검의 주인', '회수')"
        ))
    engine.dispose()

    command.upgrade(alembic_config, "head")

    engine = _engine(_current_url())
    inspector = _inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("foreshadows")}
    assert "disposition" in cols
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE foreshadows SET disposition = 'side_story' WHERE id = 1"
        ))
        row = conn.execute(text(
            "SELECT title, status, disposition FROM foreshadows WHERE id = 1"
        )).mappings().one()
    engine.dispose()
    assert row == {"title": "검의 주인", "status": "회수", "disposition": "side_story"}

    # check constraint 강제
    engine = _engine(_current_url())
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO foreshadows (id, project_id, title, status, disposition) "
                "VALUES (2, 1, 'x', '회수', 'bogus')"
            ))
    engine.dispose()

    # populated downgrade — 컬럼 제거 + 기존 행 보존
    command.downgrade(alembic_config, "5f6a7b8c9d03")

    engine = _engine(_current_url())
    inspector = _inspect(engine)
    assert "disposition" not in {
        c["name"] for c in inspector.get_columns("foreshadows")
    }
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT title, status FROM foreshadows WHERE id = 1"
        )).mappings().one()
    engine.dispose()
    assert row == {"title": "검의 주인", "status": "회수"}


def test_populated_upgrade_downgrade_project_final_editions(alembic_config):
    """D03-6 — head에서 upgrade 시 project_final_editions 생성, downgrade는 제거+프로젝트 보존."""
    from sqlalchemy import text

    command.upgrade(alembic_config, "6a7b8c9d0e14")  # final editions 이전 head

    engine = _engine(_current_url())
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO projects (id, title) VALUES (1, 'p')"))
    engine.dispose()

    command.upgrade(alembic_config, "head")

    engine = _engine(_current_url())
    inspector = _inspect(engine)
    assert "project_final_editions" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("project_final_editions")}
    assert {
        "id", "project_id", "label", "created_at", "serial_state",
        "chapter_count", "total_chars", "manifest_json", "content_md",
        "checklist_json",
    } <= cols
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO project_final_editions "
            "(project_id, label, serial_state, chapter_count, total_chars, "
            " manifest_json, content_md, checklist_json, created_at) "
            "VALUES (1, '1차', 'completed', 1, 5, '[]', '본문', '{}', "
            " '2026-09-13T00:00:00')"
        ))
    engine.dispose()

    # populated downgrade — 테이블 제거 + 프로젝트 행 보존
    command.downgrade(alembic_config, "6a7b8c9d0e14")

    engine = _engine(_current_url())
    inspector = _inspect(engine)
    assert "project_final_editions" not in inspector.get_table_names()
    with engine.connect() as conn:
        project_row = conn.execute(text(
            "SELECT title FROM projects WHERE id = 1"
        )).mappings().one()
    engine.dispose()
    assert project_row == {"title": "p"}


def test_populated_upgrade_downgrade_summary_jobs(alembic_config):
    """D04-1 — head에서 upgrade 시 summary_jobs 생성, downgrade는 제거+행 보존."""
    from sqlalchemy import text

    command.upgrade(alembic_config, "8c9d0e1f2636")  # summary_jobs 이전 head

    engine = _engine(_current_url())
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO projects (id, title) VALUES (1, 'p')"))
    engine.dispose()

    command.upgrade(alembic_config, "head")

    engine = _engine(_current_url())
    inspector = _inspect(engine)
    assert "summary_jobs" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("summary_jobs")}
    assert {
        "id", "project_id", "chapter_id", "memory_entry_id",
        "source_revision", "source_sha256", "source_sort_order",
        "source_content_length", "kind", "prompt_version",
        "provider_identity", "model_snapshot", "request_options_hash",
        "request_options_json", "idempotency_key", "status", "error",
        "attempt_count", "finished_at", "created_at", "updated_at",
    } <= cols
    uniques = {tuple(sorted(u["column_names"])) for u in inspector.get_unique_constraints("summary_jobs")}
    uniques |= {tuple(sorted(i["column_names"])) for i in inspector.get_indexes("summary_jobs") if i["unique"]}
    assert ("idempotency_key",) in uniques
    sha, opts_hash, idem = "a" * 64, "b" * 64, "c" * 64
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO summary_jobs "
            "(project_id, chapter_id, source_revision, source_sha256, "
            " source_sort_order, source_content_length, kind, prompt_version, "
            " provider_identity, model_snapshot, request_options_hash, "
            " idempotency_key, status, attempt_count) "
            f"VALUES (1, NULL, 1, '{sha}', 1.0, 3, 'summary', 'v1', 'fake', "
            f" 'm1', '{opts_hash}', '{idem}', 'planned', 0)"
        ))
    engine.dispose()

    # CHECK 제약 강제 — 사전 외 status는 거부된다
    other_key = "d" * 64
    engine = _engine(_current_url())
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO summary_jobs "
                "(project_id, source_revision, source_sha256, source_sort_order, "
                " source_content_length, kind, prompt_version, provider_identity, "
                " model_snapshot, request_options_hash, idempotency_key, status, "
                " attempt_count) "
                f"VALUES (1, 1, '{sha}', 1.0, 3, 'summary', 'v1', 'fake', 'm1', "
                f" '{opts_hash}', '{other_key}', 'bogus_status', 0)"
            ))
    engine.dispose()

    # unique 제약 강제 — 동일 idempotency_key 재삽입은 거부된다
    engine = _engine(_current_url())
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO summary_jobs "
                "(project_id, source_revision, source_sha256, source_sort_order, "
                " source_content_length, kind, prompt_version, provider_identity, "
                " model_snapshot, request_options_hash, idempotency_key, status, "
                " attempt_count) "
                f"VALUES (1, 1, '{sha}', 1.0, 3, 'summary', 'v1', 'fake', 'm1', "
                f" '{opts_hash}', '{idem}', 'planned', 0)"
            ))
    engine.dispose()

    # chapter 삭제 시 job 행은 SET NULL로 보존된다
    set_null_key = "e" * 64
    engine = _engine(_current_url())
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO chapters "
            "(id, project_id, sort_order, title, content_md, status, "
            " word_count_cache) VALUES (1, 1, 1.0, 'c', '본문', '초고', 0)"
        ))
        conn.execute(text(
            "INSERT INTO summary_jobs "
            "(project_id, chapter_id, source_revision, source_sha256, "
            " source_sort_order, source_content_length, kind, prompt_version, "
            " provider_identity, model_snapshot, request_options_hash, "
            " idempotency_key, status, attempt_count) "
            f"VALUES (1, 1, 1, '{sha}', 1.0, 3, 'summary', 'v1', 'fake', 'm1', "
            f" '{opts_hash}', '{set_null_key}', 'planned', 0)"
        ))
        conn.execute(text("DELETE FROM chapters WHERE id = 1"))
        row = conn.execute(text(
            "SELECT chapter_id, status FROM summary_jobs "
            f"WHERE idempotency_key = '{set_null_key}'"
        )).mappings().one()
    engine.dispose()
    assert row == {"chapter_id": None, "status": "planned"}

    # populated downgrade — 테이블 제거 + 프로젝트 행 보존
    command.downgrade(alembic_config, "8c9d0e1f2636")

    engine = _engine(_current_url())
    inspector = _inspect(engine)
    assert "summary_jobs" not in inspector.get_table_names()
    with engine.connect() as conn:
        project_row = conn.execute(text(
            "SELECT title FROM projects WHERE id = 1"
        )).mappings().one()
    engine.dispose()
    assert project_row == {"title": "p"}


def test_populated_upgrade_downgrade_project_ending_fields(alembic_config):
    """D03-7 — head에서 upgrade 시 projects.ending_* 컬럼, downgrade는 제거+행 보존."""
    from sqlalchemy import text

    command.upgrade(alembic_config, "7b8c9d0e1f25")  # ending 이전 head

    engine = _engine(_current_url())
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO projects (id, title) VALUES (1, 'p')"))
    engine.dispose()

    command.upgrade(alembic_config, "head")

    engine = _engine(_current_url())
    inspector = _inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("projects")}
    assert {"ending_intent", "ending_locked", "ending_updated_at"} <= cols
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT ending_intent, ending_locked, ending_updated_at FROM projects WHERE id = 1"
        )).mappings().one()
    engine.dispose()
    assert row == {"ending_intent": None, "ending_locked": 0, "ending_updated_at": None}

    # populated downgrade — 컬럼 제거 + 기존 행 보존
    command.downgrade(alembic_config, "7b8c9d0e1f25")

    engine = _engine(_current_url())
    inspector = _inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("projects")}
    assert "ending_intent" not in cols
    assert "ending_locked" not in cols
    assert "ending_updated_at" not in cols
    with engine.connect() as conn:
        project_row = conn.execute(text(
            "SELECT title FROM projects WHERE id = 1"
        )).mappings().one()
    engine.dispose()
    assert project_row == {"title": "p"}
