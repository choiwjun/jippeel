"""Summary backfill worker — D04-1.

provider는 주입된 callable(`provider(SummaryJob) -> str`). 테스트는 fake
provider만 사용한다. 실제 provider 호출·운영 DB는 승인 게이트(G01/G02/G03) 대상.
모든 결과는 MemoryEntry draft로 append만 하며 자동 승인하지 않는다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import ObjectDeletedError

from app.models import Chapter, MemoryEntry, SummaryJob
from app.services.long_memory import content_sha256, create_memory_entry
from app.services.summary_jobs import build_summary_manifest

SummaryProvider = Callable[[SummaryJob], str]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def plan_summary_jobs(
    db: Session,
    *,
    project_id: int,
    chapter_ids: Sequence[int],
    prompt_version: str,
    provider_identity: str,
    model_snapshot: str,
    request_options: Mapping[str, Any],
) -> tuple[list[SummaryJob], list[SummaryJob]]:
    """manifest를 job 행으로 영속한다. 동일 manifest는 기존 job을 재사용한다.

    Returns:
        (created, duplicates) — 새로 만든 job과, 동일 idempotency_key로
        이미 존재해 재사용된 job.
    """
    manifest = build_summary_manifest(
        db,
        project_id=project_id,
        chapter_ids=chapter_ids,
        prompt_version=prompt_version,
        provider_identity=provider_identity,
        model_snapshot=model_snapshot,
        request_options=request_options,
    )
    options_json = dict(request_options)
    created: list[SummaryJob] = []
    duplicates: list[SummaryJob] = []
    for item in manifest:
        existing = db.scalar(
            select(SummaryJob).where(SummaryJob.idempotency_key == item.idempotency_key)
        )
        if existing is not None:
            duplicates.append(existing)
            continue
        job = SummaryJob(
            project_id=project_id,
            chapter_id=item.chapter_id,
            source_revision=item.source_revision,
            source_sha256=item.source_sha256,
            source_sort_order=item.source_sort_order,
            source_content_length=item.source_content_length,
            kind="summary",
            prompt_version=item.prompt_version,
            provider_identity=item.provider_identity,
            model_snapshot=item.model_snapshot,
            request_options_hash=item.request_options_hash,
            request_options_json=options_json,
            idempotency_key=item.idempotency_key,
            status=item.status,
        )
        db.add(job)
        created.append(job)
    db.commit()
    return created, duplicates


def _find_duplicate_draft(db: Session, job: SummaryJob) -> MemoryEntry | None:
    """동일 idempotency_key provenance를 가진 기존 summary draft/approved를 찾는다."""
    if job.chapter_id is None:
        return None
    entries = db.scalars(
        select(MemoryEntry).where(
            MemoryEntry.chapter_id == job.chapter_id,
            MemoryEntry.kind == "summary",
            MemoryEntry.project_id == job.project_id,
        )
    ).all()
    for entry in entries:
        prov = entry.provenance_json or {}
        if prov.get("idempotency_key") == job.idempotency_key:
            return entry
    return None


def _is_source_current(job: SummaryJob, chapter: Chapter) -> bool:
    if (chapter.revision or 0) != job.source_revision:
        return False
    return content_sha256(chapter.content_md) == job.source_sha256


def _finish(job: SummaryJob, status: str, *, error: str | None = None) -> None:
    job.status = status
    job.error = error
    job.finished_at = _utcnow()


def _process_job(db: Session, job: SummaryJob, provider: SummaryProvider) -> None:
    # populate_existing — 같은 세션에 캐시된 오래된 chapter 상태를 읽지 않는다.
    chapter = (
        db.get(Chapter, job.chapter_id, populate_existing=True)
        if job.chapter_id is not None
        else None
    )
    if chapter is None or chapter.project_id != job.project_id:
        _finish(job, "rejected", error="chapter missing or foreign")
        return
    if not (chapter.content_md or "").strip():
        _finish(job, "skipped_empty")
        return
    if not _is_source_current(job, chapter):
        _finish(job, "stale_source", error="source changed since planning")
        return

    try:
        text = provider(job)
    except Exception as exc:  # provider 실패만 재시도 대상
        _finish(job, "provider_error", error=str(exc)[:2000])
        return

    # 생성 완료 시점 재검증 — 호출 중 원문이 바뀌면 결과를 저장하지 않는다.
    try:
        db.refresh(chapter)
    except (ObjectDeletedError, InvalidRequestError):
        _finish(job, "rejected", error="chapter deleted during generation")
        return
    if chapter.project_id != job.project_id or not _is_source_current(job, chapter):
        _finish(job, "stale_source", error="source changed during generation")
        return

    existing = _find_duplicate_draft(db, job)
    if existing is not None:
        job.memory_entry_id = existing.id
        _finish(job, "duplicate_skipped")
        return

    try:
        entry = create_memory_entry(
            db,
            project_id=job.project_id,
            chapter_id=chapter.id,
            source_revision=job.source_revision,
            source_text=chapter.content_md,
            kind="summary",
            body=text or "",
            visibility="draft",
            effective_from_sort_order=job.source_sort_order,
            provenance={
                "generated_by": "summary-worker",
                "job_id": job.id,
                "idempotency_key": job.idempotency_key,
                "prompt_version": job.prompt_version,
                "provider_identity": job.provider_identity,
                "model_snapshot": job.model_snapshot,
                "request_options_hash": job.request_options_hash,
            },
        )
    except ValueError as exc:
        # 결정적 결과 검증 실패(빈 본문·kind·소유권 등)만 provider_error — 재시도 가능.
        # SQLAlchemyError 같은 저장 계층 오류는 밖으로 던져 배치 안전망이 처리한다.
        db.rollback()
        _finish(job, "provider_error", error=f"result rejected: {exc}"[:2000])
        return
    job.memory_entry_id = entry.id
    _finish(job, "draft_saved")


def run_pending_summary_jobs(
    db: Session,
    provider: SummaryProvider,
    *,
    project_id: int | None = None,
    limit: int | None = None,
) -> list[SummaryJob]:
    """planned job을 id 순으로 처리한다. running 잔여는 planned로 복구한다.

    각 job은 독립 트랜잭션으로 마무리 — 한 job 실패가 다른 job을 막지 않는다.
    """
    running_q = select(SummaryJob).where(SummaryJob.status == "running")
    if project_id is not None:
        running_q = running_q.where(SummaryJob.project_id == project_id)
    for stale in db.scalars(running_q).all():
        stale.status = "planned"
    db.commit()

    planned_q = (
        select(SummaryJob).where(SummaryJob.status == "planned").order_by(SummaryJob.id)
    )
    if project_id is not None:
        planned_q = planned_q.where(SummaryJob.project_id == project_id)
    if limit is not None:
        planned_q = planned_q.limit(limit)

    processed: list[SummaryJob] = []
    for job in db.scalars(planned_q).all():
        job.status = "running"
        job.attempt_count += 1
        job.finished_at = None
        db.commit()
        try:
            _process_job(db, job, provider)
        except Exception as exc:
            # 예상 밖 오류(저장 계층 등)도 이 job만 종결시키고 배치를 계속한다.
            db.rollback()
            _finish(job, "provider_error", error=f"worker error: {exc}"[:2000])
        db.commit()
        processed.append(job)
    return processed


def retry_summary_job(db: Session, job_id: int) -> SummaryJob:
    """provider_error만 planned로 되돌린다. stale_source는 새 계획 대상."""
    job = db.get(SummaryJob, job_id)
    if job is None:
        raise ValueError("summary job not found")
    if job.status != "provider_error":
        raise ValueError(f"only provider_error jobs are retryable: {job.status}")
    job.status = "planned"
    job.error = None
    job.finished_at = None
    db.commit()
    return job


def list_summary_jobs(db: Session, *, project_id: int) -> list[SummaryJob]:
    return list(
        db.scalars(
            select(SummaryJob)
            .where(SummaryJob.project_id == project_id)
            .order_by(SummaryJob.id)
        ).all()
    )
