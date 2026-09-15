"""자동 요약 잡 API — D04 backfill을 앱 안에서 실행한다.

계획은 결정적·멱등이다(동일 manifest는 idempotency_key로 재사용). 실행은
주입된 GPT provider로 잡을 처리하고 결과를 MemoryEntry(draft)로만 쓴다 —
자동 승인은 없고 작가가 기억 화면에서 승인한다.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chapter, Project, SummaryJob
from app.schemas import (
    SummaryJobOut, SummaryJobPlanRequest, SummaryJobPlanResult,
    SummaryJobRunResult,
)
from app.services import gpt_oauth
from app.services.summary_provider import (
    ARC_PROMPT_VERSION, SUMMARY_PROMPT_VERSION, VOLUME_PROMPT_VERSION,
    make_gpt_summary_provider,
)
from app.services.summary_worker import (
    list_summary_jobs, plan_arc_summary_jobs, plan_summary_jobs,
    plan_volume_summary_jobs, retry_summary_job, run_pending_summary_jobs,
)

router = APIRouter()


def _get_project_or_404(pid: int, db: Session) -> Project:
    project = db.get(Project, pid)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _get_job_or_404(jid: int, db: Session) -> SummaryJob:
    job = db.get(SummaryJob, jid)
    if job is None:
        raise HTTPException(status_code=404, detail="summary job not found")
    return job


@router.get("/projects/{pid}/summary-jobs", response_model=list[SummaryJobOut])
def get_summary_jobs(pid: int, db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    return list_summary_jobs(db, project_id=pid)


@router.post("/projects/{pid}/summary-jobs/plan",
             response_model=SummaryJobPlanResult)
def plan_jobs(pid: int, payload: SummaryJobPlanRequest,
              db: Session = Depends(get_db)):
    """본문 있는 회차의 요약·아크·권 잡을 멱등으로 계획한다."""
    _get_project_or_404(pid, db)
    if payload.chapter_ids is not None:
        chapter_ids = payload.chapter_ids
    else:
        chapter_ids = list(db.scalars(
            select(Chapter.id)
            .where(Chapter.project_id == pid, Chapter.content_md.is_not(None))
            .order_by(Chapter.sort_order)
        ).all())
    try:
        resolved = gpt_oauth.get_provider()
    except gpt_oauth.OAuthProviderConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    options = {"purpose": "api-backfill"}
    try:
        created, dup = plan_summary_jobs(
            db, project_id=pid, chapter_ids=chapter_ids,
            prompt_version=SUMMARY_PROMPT_VERSION,
            provider_identity=resolved.name,
            model_snapshot=resolved.default_model,
            request_options=options,
        )
        result = SummaryJobPlanResult(
            summary={"created": len(created), "duplicates": len(dup)})
        if payload.include_arc:
            created, dup = plan_arc_summary_jobs(
                db, project_id=pid,
                prompt_version=ARC_PROMPT_VERSION,
                provider_identity=resolved.name,
                model_snapshot=resolved.default_model,
                request_options=options,
            )
            result.arc = {"created": len(created), "duplicates": len(dup)}
        if payload.include_volume:
            created, dup = plan_volume_summary_jobs(
                db, project_id=pid,
                prompt_version=VOLUME_PROMPT_VERSION,
                provider_identity=resolved.name,
                model_snapshot=resolved.default_model,
                request_options=options,
            )
            result.volume = {"created": len(created), "duplicates": len(dup)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


@router.post("/projects/{pid}/summary-jobs/run",
             response_model=SummaryJobRunResult)
def run_jobs(pid: int, limit: int = Query(default=10, ge=1, le=100),
             db: Session = Depends(get_db)):
    """planned 잡을 처리한다 — provider 실패는 잡별 provider_error로 격리."""
    _get_project_or_404(pid, db)
    provider = make_gpt_summary_provider()
    processed = run_pending_summary_jobs(db, provider, project_id=pid, limit=limit)
    return SummaryJobRunResult(processed=processed)


@router.post("/summary-jobs/{jid}/retry", response_model=SummaryJobOut)
def retry_job(jid: int, db: Session = Depends(get_db)):
    job = _get_job_or_404(jid, db)
    try:
        return retry_summary_job(db, jid)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=str(exc)) from exc
