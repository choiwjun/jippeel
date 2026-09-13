"""Deterministic, provider-free summary backfill planning tests."""
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database import Base, create_db_engine
from app.models import Chapter, MemoryEntry, Project
from app.services.summary_jobs import (
    build_summary_manifest,
    canonical_request_options_hash,
)


@pytest.fixture
def db_session(tmp_path: Path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'summary-jobs.db'}")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _projects_with_chapters(db):
    project = Project(title="summary project")
    other = Project(title="other project")
    db.add_all([project, other])
    db.flush()
    chapters = [
        Chapter(project_id=project.id, sort_order=2, title="두 번째", content_md="본문 B", revision=4),
        Chapter(project_id=project.id, sort_order=1, title="빈 회차", content_md="   ", revision=2),
        Chapter(project_id=other.id, sort_order=1, title="외부 회차", content_md="외부 본문", revision=1),
    ]
    db.add_all(chapters)
    db.commit()
    return project, other, chapters


def test_build_summary_manifest_is_deterministic_and_append_free(db_session):
    project, _other, chapters = _projects_with_chapters(db_session)
    before_count = len(db_session.scalars(select(MemoryEntry.id)).all())

    manifest = build_summary_manifest(
        db_session,
        project_id=project.id,
        chapter_ids=[chapters[1].id, chapters[0].id, chapters[0].id],
        prompt_version="summary-v1",
        provider_identity="ChatGPT OAuth",
        model_snapshot="gpt-5.6-luna",
        request_options={"temperature": 0.2, "max_tokens": 500},
    )

    assert [item.chapter_id for item in manifest] == [chapters[1].id, chapters[0].id]
    assert [item.status for item in manifest] == ["skipped_empty", "planned"]
    assert manifest[1].source_revision == 4
    assert manifest[1].source_content_length == len("본문 B")
    assert len(manifest[1].source_sha256) == 64
    assert manifest[0].idempotency_key != manifest[1].idempotency_key
    assert db_session.scalar(select(MemoryEntry.id)) is None
    assert before_count == 0

    changed_model = build_summary_manifest(
        db_session,
        project_id=project.id,
        chapter_ids=[chapters[0].id],
        prompt_version="summary-v1",
        provider_identity="ChatGPT OAuth",
        model_snapshot="gpt-5.6-luna-variant",
        request_options={"temperature": 0.2, "max_tokens": 500},
    )
    assert changed_model[0].idempotency_key != manifest[1].idempotency_key


def test_manifest_rejects_missing_or_foreign_chapters(db_session):
    project, _other, chapters = _projects_with_chapters(db_session)

    with pytest.raises(ValueError, match="chapter not found"):
        build_summary_manifest(
            db_session,
            project_id=project.id,
            chapter_ids=[99999],
            prompt_version="summary-v1",
            provider_identity="fake",
            model_snapshot="fake-model",
            request_options={},
        )

    with pytest.raises(ValueError, match="belongs to another project"):
        build_summary_manifest(
            db_session,
            project_id=project.id,
            chapter_ids=[chapters[2].id],
            prompt_version="summary-v1",
            provider_identity="fake",
            model_snapshot="fake-model",
            request_options={},
        )


def test_request_options_hash_is_order_independent_and_rejects_secrets():
    first = canonical_request_options_hash({"max_tokens": 500, "temperature": 0.2})
    second = canonical_request_options_hash({"temperature": 0.2, "max_tokens": 500})

    assert first == second
    with pytest.raises(ValueError, match="secret-bearing"):
        canonical_request_options_hash({"api_key": "do-not-store"})
