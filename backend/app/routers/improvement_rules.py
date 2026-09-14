"""작가 개선 규칙 API — 작가 피드백 자가개선 E4.

규칙은 작품(project)에 귀속되고 다른 작품과 섞이지 않는다. HTTP 경로의
생성은 항상 author_written — 시스템 제안은 E5 제안 job만이 만든다.
상태 전이는 상태 기계를 따르며 이력은 status_events_json에 append만 한다.
규칙은 원고·설정을 건드리지 않는다 — 적용은 승인 후 생성 컨텍스트 주입뿐.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ImprovementRule, Project
from app.schemas import (
    ImprovementProposalResult,
    ImprovementRuleCreate,
    ImprovementRuleDecision,
    ImprovementRuleOut,
    ImprovementRuleUpdate,
)
from app.services import improvement_proposals

router = APIRouter()

# 규칙 상태 기계 — rejected·retired는 종결. 승인된 규칙의 수정은
# retire 후 새 proposed로 재제안한다(본문 불변 원칙).
_DECISION_TRANSITIONS: dict[str, tuple[str, str]] = {
    "approve": ("proposed", "approved"),
    "reject": ("proposed", "rejected"),
    "retire": ("approved", "retired"),
}


def _get_rule_or_404(pid: int, rid: int, db: Session) -> ImprovementRule:
    rule = db.get(ImprovementRule, rid)
    if rule is None or rule.project_id != pid:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "improvement rule not found")
    return rule


def _get_project_or_404(pid: int, db: Session) -> Project:
    project = db.get(Project, pid)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    return project


@router.get("/projects/{pid}/improvement-rules",
            response_model=list[ImprovementRuleOut])
def list_rules(pid: int, status_filter: str | None = None,
               db: Session = Depends(get_db)):
    """작품의 규칙 목록 — status 필터(단일 값) 지원, 최신순."""
    _get_project_or_404(pid, db)
    stmt = (
        select(ImprovementRule)
        .where(ImprovementRule.project_id == pid)
        .order_by(ImprovementRule.id.desc())
    )
    if status_filter is not None:
        stmt = stmt.where(ImprovementRule.status == status_filter)
    return db.scalars(stmt).all()


@router.post("/projects/{pid}/improvement-rules",
             response_model=ImprovementRuleOut,
             status_code=status.HTTP_201_CREATED)
def create_rule(pid: int, payload: ImprovementRuleCreate,
                db: Session = Depends(get_db)):
    """작가 작성 규칙 — 생성 즉시 approved도 허용(작성 자체가 명시 승인)."""
    _get_project_or_404(pid, db)
    now = datetime.now(timezone.utc)
    rule = ImprovementRule(
        project_id=pid,
        category=payload.category,
        rule_text=payload.rule_text.strip(),
        status=payload.status,
        source="author_written",
        evidence_json=[e.model_dump() for e in payload.evidence],
        rationale=payload.rationale,
        status_events_json=[{"from": None, "to": payload.status,
                             "at": now.isoformat()}],
        decided_at=now if payload.status == "approved" else None,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/projects/{pid}/improvement-rules/{rid}",
            response_model=ImprovementRuleOut)
def get_rule(pid: int, rid: int, db: Session = Depends(get_db)):
    """규칙 상세 — 전이 이력 포함. 다른 작품 규칙은 404."""
    return _get_rule_or_404(pid, rid, db)


@router.patch("/projects/{pid}/improvement-rules/{rid}",
              response_model=ImprovementRuleOut)
def update_rule(pid: int, rid: int, payload: ImprovementRuleUpdate,
                db: Session = Depends(get_db)):
    """본문·근거 수정 — proposed 상태에서만 가능(승인 후 불변)."""
    rule = _get_rule_or_404(pid, rid, db)
    if rule.status != "proposed":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "rule text is immutable after decision — retire and re-propose",
        )
    if payload.category is not None:
        rule.category = payload.category
    if payload.rule_text is not None:
        rule.rule_text = payload.rule_text.strip()
    if payload.rationale is not None:
        rule.rationale = payload.rationale
    if payload.evidence is not None:
        rule.evidence_json = [e.model_dump() for e in payload.evidence]
    db.commit()
    db.refresh(rule)
    return rule


@router.post("/projects/{pid}/improvement-rules/{rid}/decision",
             response_model=ImprovementRuleOut)
def decide_rule(pid: int, rid: int, payload: ImprovementRuleDecision,
                db: Session = Depends(get_db)):
    """상태 전이 — approve·reject는 proposed에서만, retire는 approved에서만.

    유효하지 않은 전이는 409. 전이 이력은 status_events_json에 append만 한다.
    """
    rule = _get_rule_or_404(pid, rid, db)
    expected_from, to = _DECISION_TRANSITIONS[payload.decision]
    if rule.status != expected_from:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"rule transition {rule.status} → {to} not allowed",
        )
    now = datetime.now(timezone.utc)
    events = list(rule.status_events_json or [])
    events.append({"from": rule.status, "to": to, "at": now.isoformat()})
    rule.status_events_json = events
    rule.status = to
    rule.decided_at = now
    db.commit()
    db.refresh(rule)
    return rule


@router.post("/projects/{pid}/improvement-rules/propose",
             response_model=ImprovementProposalResult)
def run_proposal_job(pid: int, db: Session = Depends(get_db)):
    """E5 제안 job — 결정론 신호가 임계를 넘으면 proposed 초안만 만든다.

    LLM 호출·자동 승인 없음. 동일 (category, rule_text) 규칙이 어떤
    상태로든 존재하면 건너뛰어 재실행해도 결과가 같다(idempotent).
    """
    _get_project_or_404(pid, db)
    result = improvement_proposals.propose_rules_for_project(db, pid)
    return ImprovementProposalResult(
        created=result["created"],
        created_count=len(result["created"]),
        skipped_existing=result["skipped_existing"],
        signals_evaluated=result["signals"],
    )
