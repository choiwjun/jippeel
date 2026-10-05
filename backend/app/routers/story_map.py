"""Story map and author review records. Plans are never inferred manuscript facts."""
from typing import Literal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chapter, ChapterGoal, Project, Scene, StoryReviewDecision
from app.schemas import ChapterGoalPayload, FlowStage
from app.services.chapter_order import chapter_ordering
from app.services import story_map_evidence, story_workbench

router = APIRouter()


class MapCounts(BaseModel):
    total: int
    written: int
    confirmed: int


class MapVolume(MapCounts):
    volume: int | None
    first_chapter_id: int


class MapNode(BaseModel):
    id: int
    position: int
    volume: int | None
    title: str
    flow_stage: FlowStage
    word_count: int
    revision: int
    goal: ChapterGoalPayload | None
    goal_version: int | None
    goal_base_revision: int | None
    scene_count: int


class StoryMapOut(BaseModel):
    project_id: int
    anchor_id: int | None
    scope: Literal["near", "volume", "all"]
    counts: MapCounts
    volumes: list[MapVolume]
    nodes: list[MapNode]
    offset: int
    next_offset: int | None


def _counts(rows) -> MapCounts:
    # Same saved character-count definition as the editor (Novelpia mode).
    return MapCounts(total=len(rows), written=sum(r.word_count_cache > 0 for r in rows),
                     confirmed=sum(r.flow_stage == "confirmed" for r in rows))


@router.get("/projects/{pid}/story-map", response_model=StoryMapOut)
def get_story_map(
    pid: int,
    anchor_id: int | None = Query(default=None, ge=1),
    scope: Literal["near", "volume", "all"] = "near",
    offset: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
):
    if db.scalar(select(Project.id).where(Project.id == pid)) is None:
        raise HTTPException(404, "project not found")

    # Read lightweight metadata only: no manuscripts, relationship lazy loads or AI calls.
    rows = db.execute(select(
        Chapter.id, Chapter.volume, Chapter.title, Chapter.flow_stage,
        Chapter.word_count_cache, Chapter.revision,
    ).where(Chapter.project_id == pid).order_by(*chapter_ordering())).all()
    positions = {row.id: i for i, row in enumerate(rows)}
    if anchor_id is not None and anchor_id not in positions:
        raise HTTPException(404, "chapter not found in project")
    anchor_id = anchor_id if anchor_id is not None else (rows[0].id if rows else None)
    anchor_position = positions.get(anchor_id, 0)
    groups: dict[int | None, list] = {}
    for row in rows:
        groups.setdefault(row.volume, []).append(row)
    volumes = [MapVolume(volume=volume, first_chapter_id=group[0].id,
                         **_counts(group).model_dump()) for volume, group in groups.items()]
    if scope == "near":
        selected = rows[max(0, anchor_position - 2):anchor_position + 6]
        offset = 0
    elif scope == "volume" and rows:
        selected = groups[rows[anchor_position].volume]
    else:
        selected = rows
    counts = _counts(selected)
    # Bound goal payloads and rendering to 25 nodes, including whole-project mode.
    if offset is None:
        anchor_in_scope = next((i for i, row in enumerate(selected) if row.id == anchor_id), 0)
        offset = anchor_in_scope // 25 * 25
    offset = min(offset // 25 * 25, max(0, (len(selected) - 1) // 25 * 25))
    page = selected[offset:offset + 25]
    ids = [row.id for row in page]
    goals = {g.chapter_id: g for g in db.scalars(
        select(ChapterGoal).where(ChapterGoal.chapter_id.in_(ids))
    )} if ids else {}
    scene_counts = dict(db.execute(select(Scene.chapter_id, func.count(Scene.id))
                                  .where(Scene.chapter_id.in_(ids))
                                  .group_by(Scene.chapter_id)).all()) if ids else {}
    nodes = []
    for row in page:
        goal = goals.get(row.id)
        nodes.append(MapNode(
            id=row.id, position=positions[row.id] + 1, volume=row.volume,
            title=row.title, flow_stage=row.flow_stage,
            word_count=row.word_count_cache, revision=row.revision,
            goal=ChapterGoalPayload.model_validate(goal.goal_json) if goal else None,
            goal_version=goal.goal_version if goal else None,
            goal_base_revision=goal.base_manuscript_revision if goal else None,
            scene_count=scene_counts.get(row.id, 0),
        ))
    return StoryMapOut(project_id=pid, anchor_id=anchor_id, scope=scope, counts=counts,
                       volumes=volumes, nodes=nodes, offset=offset,
                       next_offset=offset + 25 if offset + 25 < len(selected) else None)


class EvidenceSource(BaseModel):
    id: int
    title: str
    position: int
    revision: int
    future: bool = False


class ReviewDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    item_key: str
    sequence: int
    evidence_token: str
    decision: Literal["adopt", "hold", "discard"]
    proposal: str
    reason: str
    snapshot_json: dict
    created_at: datetime


class EvidenceItem(BaseModel):
    id: str
    kind: Literal["relation", "relationship_change", "foreshadow", "stale_memory", "goal_drift"]
    label: str
    excerpt: str
    basis: str
    source: EvidenceSource | None = None
    from_id: int | None = None
    to_id: int | None = None
    from_name: str | None = None
    to_name: str | None = None
    planned: EvidenceSource | None = None
    evidence_token: str | None = None
    review_text: str | None = None
    review_key: str | None = None
    latest_decision: ReviewDecisionOut | None = None
    planted: EvidenceSource | None = None
    resolved: EvidenceSource | None = None
    registered_status: str | None = None
    disposition: str | None = None
    visibility: str | None = None
    source_revision: int | None = None


class EvidenceOut(BaseModel):
    project_id: int
    chapter_id: int
    chapter_revision: int
    view: Literal["relations", "foreshadows", "review"]
    total: int
    offset: int
    next_offset: int | None
    items: list[EvidenceItem]


@router.get("/projects/{pid}/story-map/evidence", response_model=EvidenceOut)
def get_story_map_evidence(
    pid: int,
    chapter_id: int = Query(ge=1),
    view: Literal["relations", "foreshadows", "review"] = "relations",
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    chapter = db.scalar(select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == pid))
    if chapter is None:
        raise HTTPException(404, "chapter not found in project")
    refs = story_map_evidence.chapter_refs(db, pid)
    if chapter_id not in refs:
        raise HTTPException(404, "chapter not found in project")
    if view == "relations":
        items = story_map_evidence.relations(db, pid, chapter, refs)
    elif view == "foreshadows":
        items = story_map_evidence.foreshadows(db, pid, chapter, refs)
    else:
        items = story_map_evidence.reviews(db, pid, refs)
        latest_ids = select(func.max(StoryReviewDecision.id)).where(
            StoryReviewDecision.project_id == pid,
        ).group_by(StoryReviewDecision.item_key)
        latest = {r.item_key: r for r in db.scalars(select(StoryReviewDecision).where(
            StoryReviewDecision.id.in_(latest_ids)))}
        for item in items:
            item["latest_decision"] = latest.get(item["review_key"])
    offset = min(offset // 50 * 50, max(0, (len(items) - 1) // 50 * 50))
    return EvidenceOut(project_id=pid, chapter_id=chapter_id, chapter_revision=chapter.revision,
                       view=view, total=len(items), offset=offset,
                       next_offset=offset + 50 if offset + 50 < len(items) else None,
                       items=items[offset:offset + 50])


class ReviewDecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_key: str = Field(pattern=r"^(memory|goal)-[1-9][0-9]*-[0-9a-f]{24}$", max_length=64)
    evidence_token: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_last_id: int | None = Field(default=None, ge=1, strict=True)
    decision: Literal["adopt", "hold", "discard"]
    proposal: str = Field(default="", max_length=20000)
    reason: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def meaningful_input(self):
        self.reason = self.reason.strip()
        self.proposal = self.proposal.strip()
        if not self.reason or (self.decision == "adopt" and not self.proposal):
            raise ValueError("처리 이유와 채택할 검토안을 입력하세요")
        return self


@router.post("/projects/{pid}/story-map/review-decisions", response_model=ReviewDecisionOut, status_code=201)
def create_review_decision(pid: int, payload: ReviewDecisionCreate, db: Session = Depends(get_db)):
    try:
        # SQLite writer reservation precedes all source reads, matching chapter deletion.
        # Evidence validation and the append must observe one consistent source version.
        db.execute(text("BEGIN IMMEDIATE"))
        if db.get(Project, pid) is None:
            raise HTTPException(404, "project not found")
        items = story_map_evidence.reviews(db, pid, story_map_evidence.chapter_refs(db, pid))
        item = next((i for i in items if i["review_key"] == payload.item_key), None)
        if item is None or item["evidence_token"] != payload.evidence_token:
            raise HTTPException(409, "검토 근거가 달라졌습니다. 최신 내용을 다시 확인하세요.")
        previous = db.scalar(select(StoryReviewDecision).where(
            StoryReviewDecision.project_id == pid, StoryReviewDecision.item_key == payload.item_key,
        ).order_by(StoryReviewDecision.id.desc()).limit(1))
        if payload.expected_last_id != (previous.id if previous else None):
            raise HTTPException(409, "다른 검토 기록이 저장되었습니다. 이력을 다시 확인하세요.")
        row = StoryReviewDecision(
            project_id=pid, item_key=payload.item_key, sequence=previous.sequence + 1 if previous else 1,
            evidence_token=payload.evidence_token, decision=payload.decision,
            proposal=payload.proposal, reason=payload.reason, snapshot_json=item,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(409, "검토 기록을 저장하지 못했습니다. 최신 상태를 확인하고 다시 시도하세요.") from exc


class ReviewHistoryOut(BaseModel):
    total: int
    offset: int
    next_offset: int | None
    items: list[ReviewDecisionOut]


@router.get("/projects/{pid}/story-map/review-decisions", response_model=ReviewHistoryOut)
def review_history(pid: int, offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    if db.get(Project, pid) is None:
        raise HTTPException(404, "project not found")
    condition = StoryReviewDecision.project_id == pid
    total = db.scalar(select(func.count()).select_from(StoryReviewDecision).where(condition)) or 0
    offset = min(offset // 20 * 20, max(0, (total - 1) // 20 * 20))
    items = db.scalars(select(StoryReviewDecision).where(condition)
                       .order_by(StoryReviewDecision.id.desc()).offset(offset).limit(20)).all()
    return ReviewHistoryOut(total=total, offset=offset,
                            next_offset=offset + 20 if offset + 20 < total else None, items=items)


@router.get("/projects/{pid}/story-map/workbench", response_model=story_workbench.WorkbenchOut)
def get_story_workbench(pid: int, chapter_id: int = Query(ge=1), db: Session = Depends(get_db)):
    chapter = db.scalar(select(Chapter).where(Chapter.project_id == pid, Chapter.id == chapter_id))
    if chapter is None:
        raise HTTPException(404, "chapter not found in project")
    return story_workbench.build(db, pid, chapter)
