"""D04-1 — summary_jobs 영속 + fake worker 생명주기 테스트.

합성 TEMP SQLite, fake provider callable만 사용. 실제 provider·운영 DB 없음.
"""
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database import Base, create_db_engine
from app.models import Chapter, MemoryEntry, Project, SummaryJob
from app.services.summary_worker import (
    list_summary_jobs,
    plan_summary_jobs,
    retry_summary_job,
    run_pending_summary_jobs,
)


@pytest.fixture
def db_session(tmp_path: Path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'summary-worker.db'}")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _seed(db, *, chapters):
    project = Project(title="worker project")
    db.add(project)
    db.flush()
    rows = []
    for sort_order, title, content in chapters:
        row = Chapter(
            project_id=project.id,
            sort_order=sort_order,
            title=title,
            content_md=content,
            revision=1,
        )
        db.add(row)
        rows.append(row)
    db.commit()
    return project, rows


def _plan(db, project_id, chapter_ids, **overrides):
    params = dict(
        project_id=project_id,
        chapter_ids=chapter_ids,
        prompt_version="summary-v1",
        provider_identity="fake-provider",
        model_snapshot="fake-model-1",
        request_options={"temperature": 0.2},
    )
    params.update(overrides)
    return plan_summary_jobs(db, **params)


def _fake_provider(job: SummaryJob) -> str:
    return f"[fake summary] chapter={job.chapter_id} rev={job.source_revision}"


# --- 계획 -----------------------------------------------------------------

def test_plan_creates_jobs_and_skips_empty(db_session):
    project, chapters = _seed(
        db_session,
        chapters=[(1, "본문 회차", "첫 회차 본문"), (2, "빈 회차", "   ")],
    )

    created, duplicates = _plan(db_session, project.id, [c.id for c in chapters])

    assert [j.status for j in created] == ["planned", "skipped_empty"]
    assert duplicates == []
    assert all(j.idempotency_key for j in created)
    assert created[0].source_revision == 1
    assert created[0].attempt_count == 0


def test_plan_deduplicates_same_manifest(db_session):
    project, chapters = _seed(db_session, chapters=[(1, "회차", "본문")])

    first_created, _ = _plan(db_session, project.id, [chapters[0].id])
    second_created, duplicates = _plan(db_session, project.id, [chapters[0].id])

    assert second_created == []
    assert [j.id for j in duplicates] == [first_created[0].id]
    assert len(db_session.scalars(select(SummaryJob)).all()) == 1


def test_plan_new_revision_makes_new_job(db_session):
    project, chapters = _seed(db_session, chapters=[(1, "회차", "본문")])
    first, _ = _plan(db_session, project.id, [chapters[0].id])

    chapters[0].content_md = "개정된 본문"
    chapters[0].revision = 2
    db_session.commit()

    second, _ = _plan(db_session, project.id, [chapters[0].id])
    assert len(second) == 1
    assert second[0].idempotency_key != first[0].idempotency_key


# --- 실행 -----------------------------------------------------------------

def test_run_saves_draft_memory_and_links_job(db_session):
    project, chapters = _seed(db_session, chapters=[(1, "회차", "요약할 본문")])
    _plan(db_session, project.id, [chapters[0].id])

    processed = run_pending_summary_jobs(db_session, _fake_provider)
    assert len(processed) == 1
    job = processed[0]
    assert job.status == "draft_saved"
    assert job.attempt_count == 1
    assert job.finished_at is not None
    assert job.memory_entry_id is not None

    entry = db_session.get(MemoryEntry, job.memory_entry_id)
    assert entry.visibility == "draft"
    assert entry.kind == "summary"
    assert entry.chapter_id == chapters[0].id
    assert entry.source_revision == 1
    assert entry.project_id == project.id
    assert "[fake summary]" in entry.body
    prov = entry.provenance_json or {}
    assert prov["generated_by"] == "summary-worker"
    assert prov["idempotency_key"] == job.idempotency_key
    assert prov["prompt_version"] == "summary-v1"


def test_run_skipped_empty_job_stays_terminal(db_session):
    project, chapters = _seed(db_session, chapters=[(1, "빈 회차", "  ")])
    _plan(db_session, project.id, [chapters[0].id])

    processed = run_pending_summary_jobs(db_session, _fake_provider)
    # skipped_empty는 planned가 아니므로 실행 대상이 아니다
    assert processed == []
    job = db_session.scalars(select(SummaryJob)).one()
    assert job.status == "skipped_empty"


def test_run_marks_stale_source_after_plan_edit(db_session):
    project, chapters = _seed(db_session, chapters=[(1, "회차", "원본")])
    _plan(db_session, project.id, [chapters[0].id])
    chapters[0].content_md = "계획 이후 수정"
    chapters[0].revision = 2
    db_session.commit()

    processed = run_pending_summary_jobs(db_session, _fake_provider)
    assert processed[0].status == "stale_source"
    assert processed[0].memory_entry_id is None
    assert db_session.scalar(select(MemoryEntry.id)) is None


def test_run_rechecks_source_after_provider_call(db_session):
    """provider 호출 도중 원문이 바뀌면 결과를 버리고 stale_source."""
    project, chapters = _seed(db_session, chapters=[(1, "회차", "원본")])
    _plan(db_session, project.id, [chapters[0].id])

    def mutating_provider(job):
        chapters[0].content_md = "호출 중 변경"
        chapters[0].revision = 5
        db_session.commit()
        return "변경 전 내용으로 만든 요약"

    processed = run_pending_summary_jobs(db_session, mutating_provider)
    assert processed[0].status == "stale_source"
    assert db_session.scalar(select(MemoryEntry.id)) is None


def test_run_rejects_missing_chapter(db_session):
    project, chapters = _seed(db_session, chapters=[(1, "회차", "본문")])
    _plan(db_session, project.id, [chapters[0].id])
    # FK 우회 없이 직접 삭제하면 SET NULL — job만 남는다
    db_session.delete(chapters[0])
    db_session.commit()

    processed = run_pending_summary_jobs(db_session, _fake_provider)
    assert processed[0].status == "rejected"
    assert processed[0].memory_entry_id is None


def test_run_provider_error_retryable(db_session):
    project, chapters = _seed(db_session, chapters=[(1, "회차", "본문")])
    _plan(db_session, project.id, [chapters[0].id])

    def failing_provider(job):
        raise RuntimeError("fake provider down")

    processed = run_pending_summary_jobs(db_session, failing_provider)
    job = processed[0]
    assert job.status == "provider_error"
    assert "fake provider down" in (job.error or "")
    assert job.finished_at is not None

    retried = retry_summary_job(db_session, job.id)
    assert retried.status == "planned"
    assert retried.error is None

    processed2 = run_pending_summary_jobs(db_session, _fake_provider)
    assert processed2[0].status == "draft_saved"
    assert processed2[0].attempt_count == 2


def test_retry_rejects_non_error_status(db_session):
    project, chapters = _seed(db_session, chapters=[(1, "회차", "본문")])
    created, _ = _plan(db_session, project.id, [chapters[0].id])

    with pytest.raises(ValueError):
        retry_summary_job(db_session, created[0].id)


def test_interrupted_running_job_is_recovered(db_session):
    project, chapters = _seed(db_session, chapters=[(1, "회차", "본문")])
    created, _ = _plan(db_session, project.id, [chapters[0].id])
    # worker 중단 상황 시뮬레이션 — running 잔여
    created[0].status = "running"
    db_session.commit()

    processed = run_pending_summary_jobs(db_session, _fake_provider)
    assert len(processed) == 1
    assert processed[0].status == "draft_saved"


def test_run_respects_limit_and_project_scope(db_session):
    project, chapters = _seed(
        db_session, chapters=[(1, "A", "본문 A"), (2, "B", "본문 B")]
    )
    other = Project(title="other")
    db_session.add(other)
    db_session.flush()
    foreign = Chapter(
        project_id=other.id, sort_order=1, title="외부", content_md="외부 본문",
        revision=1,
    )
    db_session.add(foreign)
    db_session.commit()

    _plan(db_session, project.id, [chapters[0].id, chapters[1].id])
    _plan(db_session, other.id, [foreign.id])

    processed = run_pending_summary_jobs(
        db_session, _fake_provider, project_id=project.id, limit=1
    )
    assert len(processed) == 1
    assert processed[0].project_id == project.id
    remaining = [j for j in list_summary_jobs(db_session, project_id=project.id)
                 if j.status == "planned"]
    assert len(remaining) == 1
    foreign_job = db_session.scalar(
        select(SummaryJob).where(SummaryJob.project_id == other.id)
    )
    assert foreign_job.status == "planned"  # 범위 밖 프로젝트는 미처리

    # running 잔여 복구도 project 범위를 존중한다
    foreign_job.status = "running"
    db_session.commit()
    run_pending_summary_jobs(db_session, _fake_provider, project_id=project.id)
    db_session.refresh(foreign_job)
    assert foreign_job.status == "running"  # 다른 프로젝트의 running은 건드리지 않음


def test_run_empty_result_body_is_provider_error(db_session):
    project, chapters = _seed(db_session, chapters=[(1, "회차", "본문")])
    _plan(db_session, project.id, [chapters[0].id])

    processed = run_pending_summary_jobs(db_session, lambda job: "   ")
    assert processed[0].status == "provider_error"
    assert db_session.scalar(select(MemoryEntry.id)) is None


def test_run_chapter_deleted_during_provider_call(db_session):
    """provider 호출 중 chapter가 삭제돼도 배치가 죽지 않고 job을 종결한다."""
    project, chapters = _seed(db_session, chapters=[(1, "회차", "본문")])
    _plan(db_session, project.id, [chapters[0].id])

    def deleting_provider(job):
        db_session.delete(chapters[0])
        db_session.commit()
        return "삭제 직전 본문 요약"

    processed = run_pending_summary_jobs(db_session, deleting_provider)
    assert processed[0].status == "rejected"
    assert db_session.scalar(select(MemoryEntry.id)) is None


def test_run_one_failure_does_not_block_later_jobs(db_session):
    project, chapters = _seed(
        db_session, chapters=[(1, "A", "본문 A"), (2, "B", "본문 B")]
    )
    _plan(db_session, project.id, [chapters[0].id, chapters[1].id])
    calls = []

    def flaky_provider(job):
        calls.append(job.id)
        if len(calls) == 1:
            raise RuntimeError("first job boom")
        return "두 번째 요약"

    processed = run_pending_summary_jobs(db_session, flaky_provider)
    assert [j.status for j in processed] == ["provider_error", "draft_saved"]


def test_plan_different_options_creates_second_job(db_session):
    project, chapters = _seed(db_session, chapters=[(1, "회차", "본문")])
    first, _ = _plan(db_session, project.id, [chapters[0].id])
    second, dup = _plan(
        db_session, project.id, [chapters[0].id],
        request_options={"temperature": 0.9},
    )
    assert len(second) == 1 and dup == []
    assert second[0].idempotency_key != first[0].idempotency_key

    run_pending_summary_jobs(db_session, _fake_provider)
    entries = db_session.scalars(select(MemoryEntry)).all()
    assert len(entries) == 2  # 옵션 해시가 다르면 별도 후보


def test_run_runtime_emptied_chapter_is_skipped(db_session):
    project, chapters = _seed(db_session, chapters=[(1, "회차", "본문")])
    _plan(db_session, project.id, [chapters[0].id])
    chapters[0].content_md = "   "  # 계획 후 비워짐 — revision 불변 해시만 변경
    db_session.commit()

    processed = run_pending_summary_jobs(db_session, _fake_provider)
    # 본문 공백 검사가 stale 검사보다 먼저 — skipped_empty
    assert processed[0].status == "skipped_empty"


def test_retry_rejects_terminal_statuses(db_session):
    project, chapters = _seed(db_session, chapters=[(1, "회차", "본문")])
    created, _ = _plan(db_session, project.id, [chapters[0].id])
    created[0].status = "stale_source"
    db_session.commit()

    with pytest.raises(ValueError):
        retry_summary_job(db_session, created[0].id)


def test_recovery_preserves_attempt_count(db_session):
    project, chapters = _seed(db_session, chapters=[(1, "회차", "본문")])
    created, _ = _plan(db_session, project.id, [chapters[0].id])
    created[0].status = "running"
    created[0].attempt_count = 3  # 실제 중단 잔여는 호출 시도 이력이 있다
    db_session.commit()

    processed = run_pending_summary_jobs(db_session, _fake_provider)
    assert processed[0].status == "draft_saved"
    assert processed[0].attempt_count == 4  # 복구가 시도 수를 지우지 않는다


def test_duplicate_skipped_when_draft_already_exists(db_session):
    """동일 provenance idempotency_key의 draft가 이미 있으면 새 draft를 만들지 않는다."""
    from app.services.long_memory import create_memory_entry

    project, chapters = _seed(db_session, chapters=[(1, "회차", "본문")])
    created, _ = _plan(db_session, project.id, [chapters[0].id])
    job = created[0]
    existing = create_memory_entry(
        db_session,
        project_id=project.id,
        chapter_id=chapters[0].id,
        source_revision=1,
        source_text="본문",
        kind="summary",
        body="기존 요약",
        visibility="draft",
        provenance={"idempotency_key": job.idempotency_key},
    )
    db_session.commit()

    processed = run_pending_summary_jobs(db_session, _fake_provider)
    assert processed[0].status == "duplicate_skipped"
    assert processed[0].memory_entry_id == existing.id
    assert db_session.scalar(
        select(MemoryEntry.id).where(MemoryEntry.id != existing.id)
    ) is None


def test_existing_memory_rows_untouched(db_session):
    from app.services.long_memory import create_memory_entry

    project, chapters = _seed(db_session, chapters=[(1, "회차", "본문")])
    approved = create_memory_entry(
        db_session,
        project_id=project.id,
        chapter_id=chapters[0].id,
        source_revision=1,
        source_text="본문",
        kind="fact",
        body="기존 승인 기억",
        visibility="approved",
    )
    _plan(db_session, project.id, [chapters[0].id])
    run_pending_summary_jobs(db_session, _fake_provider)

    db_session.refresh(approved)
    assert approved.visibility == "approved"
    assert approved.body == "기존 승인 기억"


def test_list_summary_jobs_orders_by_id(db_session):
    project, chapters = _seed(
        db_session, chapters=[(2, "B", "본문 B"), (1, "A", "본문 A")]
    )
    _plan(db_session, project.id, [chapters[0].id, chapters[1].id])

    jobs = list_summary_jobs(db_session, project_id=project.id)
    assert [j.id for j in jobs] == sorted(j.id for j in jobs)
    assert all(j.project_id == project.id for j in jobs)
