"""인지 상태·사건 영향 API — D02.

주체별 인지(knowledge_states)와 사건 영향(event_impacts)을 작가가 수동으로
기록·승인·폐기한다. 파생 job이 만든 draft도 같은 테이블에 쌓이며, 승인 전에는
컨텍스트 주입·조회 결과에서 제외된다. 상태 전이는 append-only다.
"""
from __future__ import annotations

import logging
import math

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Character,
    Chapter,
    EventImpact,
    KnowledgeState,
    Project,
)
from app.schemas import (
    EventImpactCreate,
    EventImpactOut,
    EventImpactUpdate,
    KnowledgeStateCreate,
    KnowledgeStateOut,
    KnowledgeStateUpdate,
    KnowledgeVisibleEntry,
    KnowledgeVisibleOut,
    KnowledgeVisibleRequest,
)
from app.services.cognitive_worker import (
    CognitiveProviderResponseError,
    extract_cognitive_candidates,
    make_gpt_cognitive_provider,
    plan_cognitive_jobs,
)
from app.services import gpt_oauth
import openai

router = APIRouter()
logger = logging.getLogger(__name__)
_MAX_QUERY_ROWS = 500

_TARGET_TABLES = {
    "fact": "memory_entries",
    "foreshadow": "foreshadows",
    "lore": "lore_entries",
    "event": "event_impacts",
}


# ---- helpers ----

def _get_project_or_404(pid: int, db: Session) -> Project:
    project = db.get(Project, pid)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _get_chapter_for_project(pid: int, chapter_id: int, db: Session) -> Chapter:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="chapter not found")
    if chapter.project_id != pid:
        raise HTTPException(status_code=422, detail="chapter belongs to another project")
    return chapter


def _get_character_for_project(pid: int, character_id: int, db: Session) -> Character:
    character = db.get(Character, character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="character not found")
    if character.project_id != pid:
        raise HTTPException(status_code=422, detail="character belongs to another project")
    return character


def _get_knowledge_or_404(pid: int, kid: int, db: Session) -> KnowledgeState:
    row = db.get(KnowledgeState, kid)
    if row is None:
        raise HTTPException(status_code=404, detail="knowledge state not found")
    if row.project_id != pid:
        raise HTTPException(status_code=422, detail="knowledge state belongs to another project")
    return row


def _get_impact_or_404(pid: int, iid: int, db: Session) -> EventImpact:
    row = db.get(EventImpact, iid)
    if row is None:
        raise HTTPException(status_code=404, detail="event impact not found")
    if row.project_id != pid:
        raise HTTPException(status_code=422, detail="event impact belongs to another project")
    return row


def _current_successor_id(row: KnowledgeState | EventImpact, db: Session) -> int:
    """transition chain에서 주어진 행의 최신 successor를 찾는다."""
    model = type(row)
    rows = db.scalars(select(model).where(model.project_id == row.project_id)).all()
    current = row
    while True:
        successors = [
            candidate for candidate in rows
            if (candidate.provenance_json or {}).get("supersedes_id") == current.id
        ]
        if not successors:
            return current.id
        current = max(successors, key=lambda candidate: candidate.id)


def _require_current_transition(row: KnowledgeState | EventImpact, db: Session) -> None:
    if row.visibility == "retired":
        raise HTTPException(status_code=409, detail="retired transition cannot be changed")
    if _current_successor_id(row, db) != row.id:
        raise HTTPException(status_code=409, detail="historical transition cannot be changed")


def _validate_event_delta_references(pid: int, payload, db: Session) -> None:
    """event JSON 안의 참조도 같은 프로젝트에 속하는지 검증한다."""
    character_deltas = getattr(payload, "character_deltas", None) or []
    relationship_deltas = getattr(payload, "relationship_deltas", None) or []
    foreshadow_deltas = getattr(payload, "foreshadow_deltas", None) or []
    for delta in (*character_deltas, *relationship_deltas, *foreshadow_deltas):
        if not isinstance(delta, dict):
            raise HTTPException(status_code=422, detail="event delta must be an object")
    character_ids: set[int] = set()
    relationship_character_ids: set[int] = set()
    for delta in character_deltas:
        value = delta.get("character_id")
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise HTTPException(status_code=422, detail="invalid character delta reference")
            character_ids.add(value)
    for delta in relationship_deltas:
        pair = delta.get("pair")
        if pair is None:
            continue
        if (not isinstance(pair, list) or len(pair) != 2
                or any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in pair)):
            raise HTTPException(status_code=422, detail="invalid relationship delta reference")
        relationship_character_ids.update(pair)
    character_ids.update(relationship_character_ids)
    if character_ids:
        found = set(db.scalars(select(Character.id).where(
            Character.project_id == pid, Character.id.in_(character_ids)
        )).all())
        if found != character_ids:
            raise HTTPException(status_code=422, detail="event character reference belongs to another project")
    foreshadow_ids = {
        delta.get("foreshadow_id") for delta in foreshadow_deltas
        if delta.get("foreshadow_id") is not None
    }
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in foreshadow_ids):
        raise HTTPException(status_code=422, detail="invalid foreshadow delta reference")
    if foreshadow_ids:
        from app.models import Foreshadow
        found = set(db.scalars(select(Foreshadow.id).where(
            Foreshadow.project_id == pid, Foreshadow.id.in_(foreshadow_ids)
        )).all())
        if found != foreshadow_ids:
            raise HTTPException(status_code=422, detail="event foreshadow reference belongs to another project")


def _validate_target_exists(
    project_id: int, target_kind: str, target_id: int, db: Session
) -> None:
    """대상 행이 존재하고 현재 프로젝트에 속하는지 확인한다."""
    from app.models import Foreshadow, LoreEntry, MemoryEntry

    table_map = {
        "fact": MemoryEntry,
        "foreshadow": Foreshadow,
        "lore": LoreEntry,
        "event": EventImpact,
    }
    model = table_map.get(target_kind)
    if model is None:
        raise HTTPException(status_code=422, detail=f"unknown target_kind: {target_kind}")
    row = db.get(model, target_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=422, detail=f"target {target_kind}#{target_id} not found in project")


def _knowledge_to_out(row: KnowledgeState, db: Session) -> KnowledgeStateOut:
    char_name = None
    if row.character_id is not None:
        ch = db.get(Character, row.character_id)
        char_name = ch.name if ch else None
    rev_title = None
    if row.revealed_chapter_id is not None:
        ch = db.get(Chapter, row.revealed_chapter_id)
        rev_title = ch.title if ch else None
    return KnowledgeStateOut(
        id=row.id,
        project_id=row.project_id,
        subject_type=row.subject_type,
        character_id=row.character_id,
        character_name=char_name,
        target_kind=row.target_kind,
        target_id=row.target_id,
        status=row.status,
        revealed_chapter_id=row.revealed_chapter_id,
        revealed_chapter_title=rev_title,
        effective_from_sort_order=row.effective_from_sort_order,
        visibility=row.visibility,
        source_sha256=row.source_sha256,
        generated_by=row.generated_by,
        provenance=row.provenance_json,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _impact_to_out(row: EventImpact, db: Session) -> EventImpactOut:
    ch = db.get(Chapter, row.chapter_id)
    return EventImpactOut(
        id=row.id,
        project_id=row.project_id,
        chapter_id=row.chapter_id,
        chapter_title=ch.title if ch else None,
        chapter_sort_order=ch.sort_order if ch else None,
        label=row.label,
        character_deltas=row.character_deltas_json or [],
        relationship_deltas=row.relationship_deltas_json or [],
        foreshadow_deltas=row.foreshadow_deltas_json or [],
        state_after=row.state_after,
        visibility=row.visibility,
        source_sha256=row.source_sha256,
        generated_by=row.generated_by,
        provenance=row.provenance_json,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# ---- knowledge states CRUD ----

@router.get("/projects/{pid}/knowledge-states", response_model=list[KnowledgeStateOut])
def list_knowledge_states(
    pid: int,
    subject_type: str | None = Query(default=None),
    character_id: int | None = Query(default=None),
    target_kind: str | None = Query(default=None),
    visibility: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _get_project_or_404(pid, db)
    stmt = select(KnowledgeState).where(KnowledgeState.project_id == pid)
    if subject_type:
        stmt = stmt.where(KnowledgeState.subject_type == subject_type)
    if character_id is not None:
        stmt = stmt.where(KnowledgeState.character_id == character_id)
    if target_kind:
        stmt = stmt.where(KnowledgeState.target_kind == target_kind)
    if visibility:
        stmt = stmt.where(KnowledgeState.visibility == visibility)
    stmt = stmt.order_by(KnowledgeState.id).limit(_MAX_QUERY_ROWS)
    rows = list(db.execute(stmt).scalars().all())
    return [_knowledge_to_out(r, db) for r in rows]


@router.post(
    "/projects/{pid}/knowledge-states",
    response_model=KnowledgeStateOut,
    status_code=201,
)
def create_knowledge_state(pid: int, payload: KnowledgeStateCreate, db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    if payload.subject_type == "character":
        _get_character_for_project(pid, payload.character_id, db)
    if payload.revealed_chapter_id is not None:
        _get_chapter_for_project(pid, payload.revealed_chapter_id, db)
    _validate_target_exists(pid, payload.target_kind, payload.target_id, db)

    row = KnowledgeState(
        project_id=pid,
        subject_type=payload.subject_type,
        character_id=payload.character_id,
        target_kind=payload.target_kind,
        target_id=payload.target_id,
        status=payload.status,
        revealed_chapter_id=payload.revealed_chapter_id,
        effective_from_sort_order=payload.effective_from_sort_order,
        visibility="approved",  # 수동 입력은 즉시 승인 상태
        generated_by="author_manual",
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("knowledge_state create failed: %s", exc)
        raise HTTPException(status_code=500, detail="failed to create knowledge state")
    return _knowledge_to_out(row, db)


@router.patch(
    "/projects/{pid}/knowledge-states/{kid}",
    response_model=KnowledgeStateOut,
)
def update_knowledge_state(
    pid: int, kid: int, payload: KnowledgeStateUpdate, db: Session = Depends(get_db)
):
    _get_project_or_404(pid, db)
    row = _get_knowledge_or_404(pid, kid, db)
    _require_current_transition(row, db)
    if payload.revealed_chapter_id is not None:
        _get_chapter_for_project(pid, payload.revealed_chapter_id, db)
    # 상태/공개 시점의 변화는 새 행으로 남긴다. 원본을 보존해 과거 이력을
    # 복원할 수 있게 하며, visibility만 바꾸는 승인/폐기도 같은 원칙을 따른다.
    transition = KnowledgeState(
        project_id=row.project_id,
        subject_type=row.subject_type,
        character_id=row.character_id,
        target_kind=row.target_kind,
        target_id=row.target_id,
        status=payload.status if payload.status is not None else row.status,
        revealed_chapter_id=(payload.revealed_chapter_id
                             if payload.revealed_chapter_id is not None
                             else row.revealed_chapter_id),
        effective_from_sort_order=(payload.effective_from_sort_order
                                   if payload.effective_from_sort_order is not None
                                   else row.effective_from_sort_order),
        visibility=payload.visibility if payload.visibility is not None else row.visibility,
        source_sha256=row.source_sha256,
        generated_by=row.generated_by or "author_manual",
        provenance_json={**(row.provenance_json or {}), "supersedes_id": row.id},
    )
    try:
        db.add(transition)
        db.commit()
        db.refresh(transition)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("knowledge_state update failed: %s", exc)
        raise HTTPException(status_code=500, detail="failed to create knowledge transition")
    return _knowledge_to_out(transition, db)


@router.delete("/projects/{pid}/knowledge-states/{kid}", status_code=204)
def delete_knowledge_state(pid: int, kid: int, db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    row = _get_knowledge_or_404(pid, kid, db)
    _require_current_transition(row, db)
    transition = KnowledgeState(
        project_id=row.project_id,
        subject_type=row.subject_type,
        character_id=row.character_id,
        target_kind=row.target_kind,
        target_id=row.target_id,
        status=row.status,
        revealed_chapter_id=row.revealed_chapter_id,
        effective_from_sort_order=row.effective_from_sort_order,
        visibility="retired",
        source_sha256=row.source_sha256,
        generated_by=row.generated_by or "author_manual",
        provenance_json={**(row.provenance_json or {}), "supersedes_id": row.id},
    )
    try:
        db.add(transition)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("knowledge_state delete failed: %s", exc)
        raise HTTPException(status_code=500, detail="failed to retire knowledge state")


# ---- knowledge visibility query ----

@router.post("/projects/{pid}/knowledge-visible", response_model=KnowledgeVisibleOut)
def knowledge_visible(pid: int, payload: KnowledgeVisibleRequest, db: Session = Depends(get_db)):
    """특정 시점·주체 기준으로 승인된 인지 상태만 반환한다."""
    _get_project_or_404(pid, db)
    if payload.subject_type == "character":
        _get_character_for_project(pid, payload.character_id, db)

    stmt = (
        select(KnowledgeState)
        .where(
            KnowledgeState.project_id == pid,
            KnowledgeState.subject_type == payload.subject_type,
            KnowledgeState.visibility.in_(["draft", "approved", "retired"]),
        )
        .order_by(KnowledgeState.effective_from_sort_order, KnowledgeState.id)
    )
    if payload.subject_type == "character":
        stmt = stmt.where(KnowledgeState.character_id == payload.character_id)
    if payload.at_sort_order is not None:
        stmt = stmt.where(
            (KnowledgeState.effective_from_sort_order.is_(None))
            | (KnowledgeState.effective_from_sort_order <= payload.at_sort_order)
        )
    stmt = stmt.limit(_MAX_QUERY_ROWS)
    rows = list(db.execute(stmt).scalars().all())

    # 같은 (target_kind, target_id)에 대해 가장 최신 행만 남긴다.
    latest: dict[tuple[str, int], KnowledgeState] = {}
    for r in rows:
        key = (r.target_kind, r.target_id)
        existing = latest.get(key)
        if existing is None or (r.effective_from_sort_order or -math.inf, r.id) > (
            existing.effective_from_sort_order or -math.inf,
            existing.id,
        ):
            latest[key] = r

    entries = [
        KnowledgeVisibleEntry(target_kind=r.target_kind, target_id=r.target_id, status=r.status)
        for r in latest.values()
        if r.visibility == "approved"
    ]
    return KnowledgeVisibleOut(
        subject_type=payload.subject_type,
        character_id=payload.character_id,
        at_sort_order=payload.at_sort_order,
        entries=entries,
    )


# ---- event impacts CRUD ----

@router.get("/projects/{pid}/event-impacts", response_model=list[EventImpactOut])
def list_event_impacts(
    pid: int,
    chapter_id: int | None = Query(default=None),
    visibility: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _get_project_or_404(pid, db)
    stmt = select(EventImpact).where(EventImpact.project_id == pid)
    if chapter_id is not None:
        stmt = stmt.where(EventImpact.chapter_id == chapter_id)
    if visibility:
        stmt = stmt.where(EventImpact.visibility == visibility)
    stmt = stmt.order_by(EventImpact.chapter_id, EventImpact.id).limit(_MAX_QUERY_ROWS)
    rows = list(db.execute(stmt).scalars().all())
    return [_impact_to_out(r, db) for r in rows]


@router.post(
    "/projects/{pid}/event-impacts",
    response_model=EventImpactOut,
    status_code=201,
)
def create_event_impact(pid: int, payload: EventImpactCreate, db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    _get_chapter_for_project(pid, payload.chapter_id, db)
    _validate_event_delta_references(pid, payload, db)

    row = EventImpact(
        project_id=pid,
        chapter_id=payload.chapter_id,
        label=payload.label.strip(),
        character_deltas_json=payload.character_deltas,
        relationship_deltas_json=payload.relationship_deltas,
        foreshadow_deltas_json=payload.foreshadow_deltas,
        state_after=payload.state_after,
        visibility="approved",  # 수동 입력은 즉시 승인
        generated_by="author_manual",
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("event_impact create failed: %s", exc)
        raise HTTPException(status_code=500, detail="failed to create event impact")
    return _impact_to_out(row, db)


@router.patch(
    "/projects/{pid}/event-impacts/{iid}",
    response_model=EventImpactOut,
)
def update_event_impact(
    pid: int, iid: int, payload: EventImpactUpdate, db: Session = Depends(get_db)
):
    _get_project_or_404(pid, db)
    row = _get_impact_or_404(pid, iid, db)
    _require_current_transition(row, db)
    _validate_event_delta_references(pid, payload, db)
    if payload.label is not None and not payload.label.strip():
        raise HTTPException(status_code=422, detail="label must not be empty")

    # 사건 영향도 knowledge state와 같은 append-only 이력 계약을 따른다.
    # 원본을 직접 수정하지 않고 successor를 추가해 이전 사건 스냅샷과
    # 승인/폐기 이력을 보존한다.
    transition = EventImpact(
        project_id=row.project_id,
        chapter_id=row.chapter_id,
        label=payload.label.strip() if payload.label is not None else row.label,
        character_deltas_json=(payload.character_deltas
                               if payload.character_deltas is not None
                               else row.character_deltas_json),
        relationship_deltas_json=(payload.relationship_deltas
                                  if payload.relationship_deltas is not None
                                  else row.relationship_deltas_json),
        foreshadow_deltas_json=(payload.foreshadow_deltas
                                if payload.foreshadow_deltas is not None
                                else row.foreshadow_deltas_json),
        state_after=payload.state_after if payload.state_after is not None else row.state_after,
        visibility=payload.visibility if payload.visibility is not None else row.visibility,
        source_sha256=row.source_sha256,
        generated_by=row.generated_by or "author_manual",
        provenance_json={**(row.provenance_json or {}), "supersedes_id": row.id},
    )
    try:
        db.add(transition)
        db.commit()
        db.refresh(transition)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("event_impact update failed: %s", exc)
        raise HTTPException(status_code=500, detail="failed to create event impact transition")
    return _impact_to_out(transition, db)


@router.delete("/projects/{pid}/event-impacts/{iid}", status_code=204)
def delete_event_impact(pid: int, iid: int, db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    row = _get_impact_or_404(pid, iid, db)
    _require_current_transition(row, db)
    transition = EventImpact(
        project_id=row.project_id,
        chapter_id=row.chapter_id,
        label=row.label,
        character_deltas_json=row.character_deltas_json,
        relationship_deltas_json=row.relationship_deltas_json,
        foreshadow_deltas_json=row.foreshadow_deltas_json,
        state_after=row.state_after,
        visibility="retired",
        source_sha256=row.source_sha256,
        generated_by=row.generated_by or "author_manual",
        provenance_json={**(row.provenance_json or {}), "supersedes_id": row.id},
    )
    try:
        db.add(transition)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("event_impact delete failed: %s", exc)
        raise HTTPException(status_code=500, detail="failed to retire event impact")


# ---- 파생 job (P2) ----

class DeriveRequest(BaseModel):
    """회차 인지·사건 파생 요청. provider는 주입된다."""

    model_config = ConfigDict(extra="forbid")

    chapter_ids: list[int] | None = None


class DeriveResult(BaseModel):
    chapter_id: int
    events_created: int
    knowledge_created: int
    skipped: bool


@router.post("/projects/{pid}/derive-cognitive", response_model=list[DeriveResult])
def derive_cognitive(
    pid: int,
    payload: DeriveRequest,
    db: Session = Depends(get_db),
):
    """회차 본문에서 사건·인지 후보를 draft로 추출한다.

    고정 GPT OAuth bridge만 사용한다. bridge 설정이 없거나 호출에 실패하면
    성공한 것처럼 빈 결과를 반환하지 않고 명시적으로 오류를 반환한다.
    """
    _get_project_or_404(pid, db)
    chapters = plan_cognitive_jobs(db, project_id=pid, chapter_ids=payload.chapter_ids)
    if not chapters:
        return []

    try:
        provider = make_gpt_cognitive_provider()
        results: list[DeriveResult] = []
        for ch in chapters:
            out = extract_cognitive_candidates(
                db, project_id=pid, chapter_id=ch.id, provider=provider,
            )
            results.append(DeriveResult(chapter_id=ch.id, **out))
        return results
    except gpt_oauth.OAuthProviderConfigError as exc:
        raise HTTPException(status_code=503, detail="GPT OAuth bridge is not configured") from exc
    except (CognitiveProviderResponseError, openai.APIError, ConnectionError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail="cognitive derivation provider failed") from exc
