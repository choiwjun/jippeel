"""생성 이력·작가 처분 API — 작가 피드백 자가개선 E1/E2.

생성 이력은 원고 정본이 아닌 참조 데이터다. 이 라우터는 이력 조회와
작가 처분(outcome) 기록만 제공하며 원고·설정을 변경하지 않는다.
처분 전이는 최소한의 상태 기계를 따른다 — 재전이는 409.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Chapter, GenerationOutput, GenerationRun
from app.schemas import (
    GenerationAnalysisOut,
    GenerationOutcomeIn,
    GenerationOutputApplyIn,
    GenerationOutputApplyResult,
    GenerationOutputOut,
    GenerationRunDetail,
    GenerationRunOut,
)
from app.services import generation_analysis, manuscripts

router = APIRouter()

# outcome 상태 기계 — copied는 "일단 복사해 둠"이라 후속 실반영(inserted/replaced)
# 또는 폐기로 이어지는 비종결 상태. 나머지는 종결.
_OUTCOME_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"inserted", "replaced", "copied", "discarded"},
    "copied": {"inserted", "replaced", "discarded"},
}


def _get_output_or_404(oid: int, db: Session) -> GenerationOutput:
    output = db.get(GenerationOutput, oid)
    if output is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "generation output not found")
    return output


@router.post("/generation-outputs/{oid}/outcome",
             response_model=GenerationOutputOut)
def record_outcome(oid: int, payload: GenerationOutcomeIn,
                   db: Session = Depends(get_db)):
    """작가 처분 기록 — pending→임의, copied→inserted|replaced|discarded.

    종결 상태(inserted·replaced·discarded)에서의 재전이는 409 — 처분 이력은
    덮어쓰지 않고 outcome_events_json에 append만 한다.
    """
    output = _get_output_or_404(oid, db)
    allowed = _OUTCOME_TRANSITIONS.get(output.outcome, set())
    if payload.outcome not in allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"outcome transition {output.outcome} → {payload.outcome} not allowed",
        )
    now = datetime.now(timezone.utc)
    events = list(output.outcome_events_json or [])
    events.append({"outcome": payload.outcome, "at": now.isoformat()})
    output.outcome_events_json = events
    output.outcome = payload.outcome
    output.outcome_at = now
    if payload.landed_text is not None:
        output.landed_text = payload.landed_text
    if payload.chapter_revision is not None:
        output.chapter_revision_at_action = payload.chapter_revision
    db.commit()
    db.refresh(output)
    return output


# 원고에 적용될 수 있는 채널 — plan/review는 원고 텍스트가 아니고
# worker는 부분 장면이라 제외한다.
_APPLIABLE_CHANNELS = {"draft", "refined"}


@router.post("/generation-outputs/{oid}/apply",
             response_model=GenerationOutputApplyResult)
def apply_output(oid: int, payload: GenerationOutputApplyIn,
                 db: Session = Depends(get_db)):
    """초안 산출물을 회차 원고에 적용하는 명시적 작가 액션.

    생성 경로는 원고를 쓰지 않는다 — 이 엔드포인트만이 산출물을 정본으로
    승격한다. CAS(expected_revision)로 드리프트를 막고, 적용 사실은
    outcome=inserted로 기록한다. 종결 처분이면 재적용은 409.
    """
    output = _get_output_or_404(oid, db)
    if output.channel not in _APPLIABLE_CHANNELS:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"channel {output.channel} cannot be applied to manuscript",
        )
    run = db.get(GenerationRun, output.run_id)
    if run is None or run.chapter_id is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "output is not anchored to a chapter")
    chapter = db.get(Chapter, run.chapter_id)
    if chapter is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "target chapter was deleted")
    if "inserted" not in _OUTCOME_TRANSITIONS.get(output.outcome, set()):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"outcome transition {output.outcome} → inserted not allowed",
        )
    expected = (
        payload.expected_revision
        if payload.expected_revision is not None
        else int(chapter.revision or 0)
    )
    try:
        saved = manuscripts.replace_manuscript(
            db, chapter.id, output.output_text, expected,
            reason="generation_output_apply",
        )
    except manuscripts.RevisionConflict as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=exc.detail()) from exc
    except manuscripts.ChapterNotFound as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "target chapter was deleted") from exc
    now = datetime.now(timezone.utc)
    events = list(output.outcome_events_json or [])
    events.append({"outcome": "inserted", "at": now.isoformat(), "via": "apply"})
    output.outcome_events_json = events
    output.outcome = "inserted"
    output.outcome_at = now
    output.landed_text = output.output_text
    output.chapter_revision_at_action = expected
    db.commit()
    return GenerationOutputApplyResult(
        output_id=output.id,
        chapter_id=saved.id,
        chapter_title=saved.title,
        revision=saved.revision,
        outcome="inserted",
    )


@router.get("/chapters/{cid}/generation-runs",
            response_model=list[GenerationRunOut])
def list_chapter_generation_runs(cid: int, db: Session = Depends(get_db)):
    """회차의 생성 이력 — 최신순. outputs는 요약(텍스트 제외)."""
    if db.get(Chapter, cid) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "chapter not found")
    runs = db.scalars(
        select(GenerationRun)
        .where(GenerationRun.chapter_id == cid)
        .options(selectinload(GenerationRun.outputs))
        .order_by(GenerationRun.id.desc())
    ).all()
    return runs


@router.get("/generation-runs/{rid}", response_model=GenerationRunDetail)
def get_generation_run(rid: int, db: Session = Depends(get_db)):
    """run 상세 — 전체 outputs(원문·landed_text 포함)."""
    run = db.scalar(
        select(GenerationRun)
        .where(GenerationRun.id == rid)
        .options(selectinload(GenerationRun.outputs))
    )
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "generation run not found")
    return run


@router.get("/projects/{pid}/generation-analysis",
            response_model=GenerationAnalysisOut)
def project_generation_analysis(pid: int, db: Session = Depends(get_db)):
    """E3 결정론 분석 — 편집거리·삭제 표현·분량·surface별 수용률.

    LLM 호출 없이 이력 테이블만 집계한다. E5 제안 job의 입력 신호이며
    원고·설정을 변경하지 않는다.
    """
    from app.models import Project
    if db.get(Project, pid) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    return generation_analysis.analyze_project_generations(db, pid)
