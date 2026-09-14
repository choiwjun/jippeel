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
    GenerationOutcomeIn,
    GenerationOutputOut,
    GenerationRunDetail,
    GenerationRunOut,
)

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
