"""프로젝트·회차 라우터 (사양 §5 M1, Sprint 1 범위)."""
import asyncio
import inspect
import logging
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse  # pyright: ignore[reportMissingImports]
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Chapter,
    ChapterFlowEvent,
    ChapterGoal,
    ChapterGoalEvidenceLink,
    ChapterGoalRevision,
    ChapterSnapshot,
    Character,
    Foreshadow,
    MemoryEntry,
    EventImpact,
    Project,
    ProjectFinalEdition,
    RefineRun,
    Relationship,
    Scene,
)
from app.schemas import BootstrapRequest, BootstrapResponse, PlusStatusOut, PLUS_MIN_CHAPTERS, PLUS_MIN_CHARS_DONE
from app.services import bootstrap as bootstrap_service
from app.services import manuscripts
from app.schemas import (
    ChaptersReorder,
    ChapterContentPut,
    ChapterCreate,
    ChapterFlowEventOut,
    ChapterFlowOut,
    ChapterFlowTransition,
    ChapterResumeOut,
    EvidenceLinkCreate,
    EvidenceLinkListOut,
    EvidenceLinkOut,
    ChapterGoalOut,
    ChapterGoalPayload,
    ChapterGoalRestoreRequest,
    ChapterGoalRevisionOut,
    ChapterGoalVersionOut,
    ChapterGoalWrite,
    ChapterRestorePost,
    ChapterSnapshotDetail,
    ChapterSnapshotOut,
    ChapterDetail,
    ChapterOut,
    ChapterUpdate,
    CompletionChecklist,
    EndingImpactOut,
    FinalEditionChapterEntry,
    FinalEditionCreate,
    FinalEditionDetail,
    FinalEditionOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    StyleAnalysisRequest,
    StyleAnalysisResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------- helpers ----------
def _get_project_or_404(pid: int, db: Session) -> Project:
    project = db.get(Project, pid)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _get_chapter_or_404(cid: int, db: Session) -> Chapter:
    chapter = db.get(Chapter, cid)
    if chapter is None:
        raise HTTPException(status_code=404, detail="chapter not found")
    return chapter


# ---------- project bootstrap ----------
@router.post("/projects/bootstrap/stream")
async def bootstrap_project_stream(payload: BootstrapRequest, db: Session = Depends(get_db)):
    """SSE 스트리밍 bootstrap — 단계별 진행 상태를 실시간으로 전송한다.

    이벤트: stage_started / stage_done / stage_failed / done / error
    마지막 done 이벤트의 data에 BootstrapResponse JSON이 들어 있다.
    """
    import json

    queue: asyncio.Queue = asyncio.Queue()
    heartbeat_interval = 15.0
    current_stage = "starting"

    async def on_stage(stage: str, status_: str, label: str):
        nonlocal current_stage
        if status_ == "started":
            current_stage = stage
        await queue.put({"event": f"stage_{status_}", "data": json.dumps(
            {"stage": stage, "label": label}, ensure_ascii=False)})

    async def run_bootstrap():
        client = None
        try:
            if payload.use_ai:
                try:
                    provider = bootstrap_service.resolve_provider()
                except bootstrap_service.NoEndpointError as exc:
                    await queue.put({"event": "error", "data": json.dumps(
                        {"status": 503, "detail": str(exc)}, ensure_ascii=False)})
                    return
                from app.services import llm
                client = llm.make_long_running_client(provider.base_url, None)
                try:
                    structure = await bootstrap_service.generate_structure(
                        payload.genre, payload.premise, payload.title_style,
                        payload.volume_count, payload.chapters_per_volume,
                        client, provider.default_model,
                        reasoning_effort=provider.reasoning_effort,
                        db=db,
                        on_stage=on_stage)
                    body = bootstrap_service.persist_structure(
                        db, payload.genre, payload.premise, structure,
                        generated_by="ai",
                        volume_count=payload.volume_count,
                        chapters_per_volume=payload.chapters_per_volume)
                except bootstrap_service.BootstrapAIError as exc:
                    structure = bootstrap_service.fallback_structure(
                        payload.genre, payload.premise,
                        payload.volume_count, payload.chapters_per_volume)
                    body = bootstrap_service.persist_structure(
                        db, payload.genre, payload.premise, structure,
                        generated_by="fallback",
                        volume_count=payload.volume_count,
                        chapters_per_volume=payload.chapters_per_volume)
                    body["detail"] = "AI 생성에 실패해 규칙 기반 폴백으로 저장했습니다."
            else:
                structure = bootstrap_service.fallback_structure(
                    payload.genre, payload.premise,
                    payload.volume_count, payload.chapters_per_volume)
                body = bootstrap_service.persist_structure(
                    db, payload.genre, payload.premise, structure,
                    generated_by="fallback",
                    volume_count=payload.volume_count,
                    chapters_per_volume=payload.chapters_per_volume)
            await queue.put({"event": "done", "data": json.dumps(body, ensure_ascii=False)})
        except Exception as exc:
            logger.exception("bootstrap stream failed")
            await queue.put({"event": "error", "data": json.dumps(
                {"status": 500, "detail": "작품 생성 중 서버 오류가 발생했습니다."}, ensure_ascii=False)})
        finally:
            if client is not None:
                closer = getattr(client, "aclose", None)
                if closer is not None:
                    result = closer()
                    if inspect.isawaitable(result):
                        await result
            await queue.put(None)  # 종료 sentinel

    async def event_stream():
        task = asyncio.create_task(run_bootstrap())
        started = asyncio.get_running_loop().time()
        queue_task = asyncio.create_task(queue.get())
        try:
            while True:
                done, _ = await asyncio.wait(
                    {queue_task}, timeout=heartbeat_interval)
                if not done:
                    # 콘텐츠·provider 응답은 노출하지 않는 상태 전용 heartbeat.
                    yield {"event": "heartbeat", "data": json.dumps({
                        "stage": current_stage,
                        "elapsed_seconds": int(asyncio.get_running_loop().time() - started),
                    })}
                    continue
                item = queue_task.result()
                if item is None:
                    break
                yield item
                queue_task = asyncio.create_task(queue.get())
        finally:
            if not queue_task.done():
                queue_task.cancel()
            await asyncio.gather(queue_task, return_exceptions=True)
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    return EventSourceResponse(event_stream(), ping=15)


@router.post("/projects/bootstrap", response_model=BootstrapResponse)
async def bootstrap_project(payload: BootstrapRequest, db: Session = Depends(get_db)):
    """입력 하나(장르 등)로 작품 전체 구조를 AI 생성해 일괄 저장한다.

    - use_ai=false 또는 LLM 실패 시 규칙 기반 폴백으로 템플릿 생성
    - AI를 시도했으나 최종 실패한 경우 502 + 폴백 본문을 반환한다
      (요청은 실패로 표시하되 결과물은 템플릿으로라도 제공)
    """
    if payload.use_ai:
        try:
            provider = bootstrap_service.resolve_provider()
        except bootstrap_service.NoEndpointError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail=str(exc)) from exc
        from app.services import llm
        client = llm.make_long_running_client(provider.base_url, None)
        logger.info(
            "bootstrap provider resolved: provider=%s base_url=%s model=%s reasoning=%s",
            provider.name, provider.base_url, provider.default_model,
            bootstrap_service.BOOTSTRAP_REASONING_EFFORT)
        try:
            structure = await bootstrap_service.generate_structure(
                payload.genre, payload.premise, payload.title_style,
                payload.volume_count, payload.chapters_per_volume,
                client, provider.default_model,
                reasoning_effort=bootstrap_service.BOOTSTRAP_REASONING_EFFORT,
                db=db)
            body = bootstrap_service.persist_structure(
                db, payload.genre, payload.premise, structure,
                generated_by="ai",
                volume_count=payload.volume_count,
                chapters_per_volume=payload.chapters_per_volume)
            return body
        except bootstrap_service.BootstrapAIError as exc:
            # 규칙 기반 폴백 — 템플릿으로라도 생성하고 502로 응답
            structure = bootstrap_service.fallback_structure(
                payload.genre, payload.premise,
                payload.volume_count, payload.chapters_per_volume)
            body = bootstrap_service.persist_structure(
                db, payload.genre, payload.premise, structure,
                generated_by="fallback",
                volume_count=payload.volume_count,
                chapters_per_volume=payload.chapters_per_volume)
            body["detail"] = f"AI 생성 실패 — 규칙 기반 폴백으로 저장했습니다: {exc}"
            return JSONResponse(status_code=502, content=body)

    structure = bootstrap_service.fallback_structure(
        payload.genre, payload.premise,
        payload.volume_count, payload.chapters_per_volume)
    return bootstrap_service.persist_structure(
        db, payload.genre, payload.premise, structure,
        generated_by="fallback",
        volume_count=payload.volume_count,
        chapters_per_volume=payload.chapters_per_volume)


# ---------- projects ----------
@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    """작품 목록 + 카드용 집계(회차 수·누적 글자 수)를 함께 반환한다."""
    from sqlalchemy import func

    rows = db.execute(
        select(
            Project,
            func.count(Chapter.id),
            func.coalesce(func.sum(Chapter.word_count_cache), 0),
        )
        .outerjoin(Chapter, Chapter.project_id == Project.id)
        .group_by(Project.id)
        .order_by(Project.updated_at.desc())
    ).all()
    out: list[ProjectOut] = []
    for project, chapter_count, total_chars in rows:
        item = ProjectOut.model_validate(project)
        item.chapter_count = chapter_count
        item.total_chars = total_chars
        out.append(item)
    return out


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects/{pid}", response_model=ProjectOut)
def get_project(pid: int, db: Session = Depends(get_db)):
    return _get_project_or_404(pid, db)


@router.patch("/projects/{pid}", response_model=ProjectOut)
def update_project(pid: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = _get_project_or_404(pid, db)
    fields = payload.model_dump(exclude_unset=True)
    # D03-7: 프론트는 빈 결말을 null로 보낸다 — 직접 API 호출의 ""도 동일하게 정규화해
    # falsy-but-nonnull 상태와 updated_at 불필요 갱신을 막는다.
    if fields.get("ending_intent") == "":
        fields["ending_intent"] = None
    # D03-7: 잠긴 결말의 실제 변경은 같은 요청의 명시적 해제 없이 거부한다.
    # 동일값은 변경이 아니므로 잠금 상태에서도 허용된다.
    ending_changing = (
        "ending_intent" in fields
        and fields["ending_intent"] != project.ending_intent
    )
    if (
        ending_changing
        and project.ending_locked
        and fields.get("ending_locked") is not False
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="결말이 잠겨 있습니다. 변경하려면 잠금 해제를 함께 요청하세요.",
        )
    for field, value in fields.items():
        setattr(project, field, value)
    # D03-3: completed 진입/재진입마다 시각을 새로 기록하고, 이탈 시 지운다.
    if "serial_state" in fields:
        if fields["serial_state"] == "completed":
            project.serial_completed_at = _utcnow()
        else:
            project.serial_completed_at = None
    # D03-7: 결말 값이 실제로 바뀐 경우에만 변경 시각을 기록한다.
    if ending_changing:
        project.ending_updated_at = _utcnow()
    db.commit()
    db.refresh(project)
    return project


@router.delete("/projects/{pid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(pid: int, db: Session = Depends(get_db)):
    project = _get_project_or_404(pid, db)
    # Relationship은 characters FK를 참조하지만 소유 계층이 없어 ORM cascade가
    # 닿지 않는다. 캐릭터 삭제 전에 이 프로젝트의 관계 행을 먼저 제거한다.
    char_ids = select(Character.id).where(Character.project_id == pid)
    db.query(Relationship).filter(
        Relationship.from_character_id.in_(char_ids)
    ).delete(synchronize_session=False)
    db.delete(project)
    db.commit()


# ---------- chapters (회차 트리 / CRUD) ----------
@router.get("/projects/{pid}/chapters", response_model=list[ChapterOut])
def list_chapters(
    pid: int,
    volume: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
):
    _get_project_or_404(pid, db)
    stmt = (
        select(Chapter)
        .where(Chapter.project_id == pid)
        .order_by(Chapter.volume.asc().nulls_last(), Chapter.sort_order)  # Q1: 권 NULL은 목록 끝으로
    )
    if volume is not None:
        stmt = stmt.where(Chapter.volume == volume)
    return db.scalars(stmt).all()


@router.post(
    "/projects/{pid}/chapters",
    response_model=ChapterDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_chapter(pid: int, payload: ChapterCreate, db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    chapter = Chapter(project_id=pid, **payload.model_dump())
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return chapter


@router.get("/chapters/{cid}", response_model=ChapterDetail)
def get_chapter(cid: int, db: Session = Depends(get_db)):
    """본문 포함 상세."""
    return _get_chapter_or_404(cid, db)


@router.patch("/chapters/{cid}", response_model=ChapterDetail)
def update_chapter(cid: int, payload: ChapterUpdate, db: Session = Depends(get_db)):
    """제목/상태/메모/권·순서 저장 (자동저장: PATCH debounce)."""
    chapter = _get_chapter_or_404(cid, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(chapter, field, value)
    db.commit()
    db.refresh(chapter)
    return chapter


def _revision_conflict(exc: manuscripts.RevisionConflict) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.detail())


@router.put("/chapters/{cid}/content", response_model=ChapterDetail)
def put_chapter_content(cid: int, payload: ChapterContentPut, db: Session = Depends(get_db)):
    """본문(content_md) 저장 + 공백 제외 글자 수 캐시 갱신."""
    try:
        chapter = manuscripts.replace_manuscript(
            db, cid, payload.content_md, payload.expected_revision, reason="autosave"
        )
        db.commit()
        db.refresh(chapter)
        return chapter
    except manuscripts.ChapterNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail="chapter not found") from exc
    except manuscripts.RevisionConflict as exc:
        db.rollback()
        raise _revision_conflict(exc) from exc


@router.post("/chapters/{cid}/content", response_model=ChapterDetail,
             status_code=status.HTTP_200_OK)
def post_chapter_content(cid: int, payload: ChapterContentPut, db: Session = Depends(get_db)):
    """PUT 별칭 — 언로드 플러시 전용(QA Minor #1)."""
    return put_chapter_content(cid, payload, db)


@router.get("/chapters/{cid}/snapshots", response_model=list[ChapterSnapshotOut])
def list_chapter_snapshots(cid: int, db: Session = Depends(get_db)):
    _get_chapter_or_404(cid, db)
    return manuscripts.list_snapshots(db, cid)


@router.get("/chapters/{cid}/snapshots/{sid}", response_model=ChapterSnapshotDetail)
def get_chapter_snapshot(cid: int, sid: int, db: Session = Depends(get_db)):
    _get_chapter_or_404(cid, db)
    snapshot = db.get(ChapterSnapshot, sid)
    if snapshot is None or snapshot.chapter_id != cid:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return snapshot


@router.post("/chapters/{cid}/restore", response_model=ChapterDetail)
def restore_chapter_snapshot(cid: int, payload: ChapterRestorePost, db: Session = Depends(get_db)):
    _get_chapter_or_404(cid, db)
    snapshot = db.get(ChapterSnapshot, payload.snapshot_id)
    if snapshot is None or snapshot.chapter_id != cid:
        raise HTTPException(status_code=422, detail="해당 회차의 복구본만 복원할 수 있습니다")
    try:
        chapter = manuscripts.replace_manuscript(
            db, cid, snapshot.content_md, payload.expected_revision, reason="restore"
        )
        db.commit()
        db.refresh(chapter)
        return chapter
    except manuscripts.RevisionConflict as exc:
        db.rollback()
        raise _revision_conflict(exc) from exc


# ---------- chapter goals (D01 회차 목표 영속화) ----------
# 목표는 원고 정본이 아닌 작가 의도 데이터다. 저장·복원·삭제가 Chapter.revision을
# 증가시키거나 ChapterSnapshot을 만들지 않으며, Chapter.memo와 혼용하지 않는다.
GOAL_CONFLICT_MESSAGE = "목표가 다른 곳에서 먼저 저장되었습니다. 최신 목표를 확인한 뒤 다시 시도하세요."

_GOAL_SCALAR_FIELDS = (
    "emotion_goal", "cost", "next_hook", "ending_intent", "scene_type",
)
_GOAL_LIST_FIELDS = ("core_events", "character_choices", "prohibitions")


def _normalize_goal_payload(payload: ChapterGoalPayload) -> dict:
    """저장용 정규화 — schema가 trim한 값을 받아 빈 문자열→None, 배열 빈 항목 제거."""
    data = payload.model_dump()
    normalized: dict = {}
    for field in _GOAL_SCALAR_FIELDS:
        value = data.get(field)
        normalized[field] = value if value not in (None, "") else None
    for field in _GOAL_LIST_FIELDS:
        items = data.get(field)
        normalized[field] = [item for item in items if item] if items is not None else None
    normalized["target_chars_novelpia"] = data.get("target_chars_novelpia")
    return normalized


def _goal_conflict(current_version: int | None) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "goal_version_conflict",
            "message": GOAL_CONFLICT_MESSAGE,
            "current_goal_version": current_version,
        },
    )


def _current_goal(db: Session, cid: int) -> ChapterGoal | None:
    return db.scalar(select(ChapterGoal).where(ChapterGoal.chapter_id == cid))


def _fresh_goal_version(db: Session, cid: int) -> int | None:
    db.expire_all()
    return db.scalar(select(ChapterGoal.goal_version).where(ChapterGoal.chapter_id == cid))


def _next_goal_version(db: Session, cid: int, current: ChapterGoal | None) -> int:
    """현재값 삭제 후에도 이력과 충돌하지 않는 단조 버전."""
    highest = current.goal_version if current is not None else 0
    history_max = db.scalar(
        select(func.max(ChapterGoalRevision.goal_version)).where(
            ChapterGoalRevision.chapter_id == cid
        )
    ) or 0
    return max(highest, history_max) + 1


def _goal_version_out(goal: ChapterGoal) -> ChapterGoalVersionOut:
    return ChapterGoalVersionOut(
        goal_version=goal.goal_version,
        goal=dict(goal.goal_json or {}),
        episode_purpose=goal.episode_purpose,
        base_manuscript_revision=goal.base_manuscript_revision,
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )


def _goal_revision_out(row: ChapterGoalRevision) -> ChapterGoalRevisionOut:
    return ChapterGoalRevisionOut(
        id=row.id,
        goal_version=row.goal_version,
        goal=dict(row.goal_json or {}),
        episode_purpose=row.episode_purpose,
        base_manuscript_revision=row.base_manuscript_revision,
        restored_from=row.restored_from,
        created_at=row.created_at,
    )


def _goal_out(db: Session, chapter: Chapter) -> ChapterGoalOut:
    goal = _current_goal(db, chapter.id)
    history_count = db.scalar(
        select(func.count(ChapterGoalRevision.id)).where(
            ChapterGoalRevision.chapter_id == chapter.id
        )
    ) or 0
    return ChapterGoalOut(
        chapter_id=chapter.id,
        project_id=chapter.project_id,
        goal=_goal_version_out(goal) if goal is not None else None,
        current_chapter_revision=int(chapter.revision or 0),
        history_count=history_count,
    )


def _apply_goal_write(
    db: Session,
    chapter: Chapter,
    *,
    goal_json: dict,
    episode_purpose: str,
    expected: int | None,
    base_revision: int | None,
    restored_from: int | None = None,
) -> ChapterGoal:
    """CAS 검사 후 현재 목표 새 버전 기록 + append-only 이력 row 추가.

    expected=None은 "현재 목표 없음" 기대, N은 현재 버전 일치 요구.
    목표 쓰기는 원문 revision·snapshot·memo를 건드리지 않는다.
    """
    current = _current_goal(db, chapter.id)
    if expected is None and current is not None:
        raise _goal_conflict(current.goal_version)
    if expected is not None and (current is None or current.goal_version != expected):
        raise _goal_conflict(current.goal_version if current is not None else None)
    next_version = _next_goal_version(db, chapter.id, current)
    try:
        if current is None:
            current = ChapterGoal(
                chapter_id=chapter.id,
                goal_json=goal_json,
                episode_purpose=episode_purpose,
                goal_version=next_version,
                base_manuscript_revision=base_revision,
            )
            db.add(current)
        else:
            result = db.execute(
                update(ChapterGoal)
                .where(ChapterGoal.id == current.id, ChapterGoal.goal_version == expected)
                .values(
                    goal_json=goal_json,
                    episode_purpose=episode_purpose,
                    goal_version=next_version,
                    base_manuscript_revision=base_revision,
                )
            )
            if result.rowcount != 1:
                db.rollback()
                raise _goal_conflict(_fresh_goal_version(db, chapter.id))
        db.add(
            ChapterGoalRevision(
                chapter_id=chapter.id,
                goal_version=next_version,
                goal_json=goal_json,
                episode_purpose=episode_purpose,
                base_manuscript_revision=base_revision,
                restored_from=restored_from,
            )
        )
        db.commit()
    except HTTPException:
        raise
    except IntegrityError as exc:
        db.rollback()
        raise _goal_conflict(_fresh_goal_version(db, chapter.id)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        error_code = getattr(getattr(exc, "orig", None), "sqlite_errorcode", None)
        if error_code is not None and error_code & 0xFF == sqlite3.SQLITE_BUSY:
            raise HTTPException(
                status_code=409,
                detail="목표가 변경 중입니다. 새로고침 후 다시 시도하세요.",
            ) from exc
        logger.exception("chapter goal write database failure: chapter_id=%s", chapter.id)
        raise HTTPException(status_code=500, detail="목표 저장 중 오류가 발생했습니다.") from exc
    db.refresh(current)
    return current


@router.get("/chapters/{cid}/goal", response_model=ChapterGoalOut)
def get_chapter_goal(cid: int, db: Session = Depends(get_db)):
    """회차 목표 조회 — 목표 없음은 goal=null(오류와 구분)."""
    chapter = _get_chapter_or_404(cid, db)
    return _goal_out(db, chapter)


@router.put("/chapters/{cid}/goal", response_model=ChapterGoalOut)
def put_chapter_goal(cid: int, payload: ChapterGoalWrite, db: Session = Depends(get_db)):
    """회차 목표 저장 — 부분·빈 저장 허용, expected_goal_version CAS."""
    chapter = _get_chapter_or_404(cid, db)
    if payload.project_id is not None and payload.project_id != chapter.project_id:
        raise HTTPException(status_code=422, detail="project_id does not match chapter project")
    _apply_goal_write(
        db,
        chapter,
        goal_json=_normalize_goal_payload(payload.goal),
        episode_purpose=payload.episode_purpose,
        expected=payload.expected_goal_version,
        base_revision=(
            payload.base_manuscript_revision
            if payload.base_manuscript_revision is not None
            else int(chapter.revision or 0)
        ),
    )
    db.refresh(chapter)
    return _goal_out(db, chapter)


@router.delete("/chapters/{cid}/goal", status_code=status.HTTP_204_NO_CONTENT)
def delete_chapter_goal(cid: int, db: Session = Depends(get_db)):
    """현재 목표만 삭제 — 이력(append-only)은 보존한다."""
    try:
        _get_chapter_or_404(cid, db)
        goal = _current_goal(db, cid)
        if goal is None:
            raise HTTPException(status_code=404, detail="goal not found")
        db.delete(goal)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        error_code = getattr(getattr(exc, "orig", None), "sqlite_errorcode", None)
        if error_code is not None and error_code & 0xFF == sqlite3.SQLITE_BUSY:
            raise HTTPException(status_code=409, detail="목표가 변경 중입니다. 새로고침 후 다시 시도하세요.") from exc
        logger.exception("chapter goal delete database failure: chapter_id=%s", cid)
        raise HTTPException(status_code=500, detail="목표 삭제 중 오류가 발생했습니다.") from exc


@router.get("/chapters/{cid}/goal/history", response_model=list[ChapterGoalRevisionOut])
def list_chapter_goal_history(cid: int, db: Session = Depends(get_db)):
    """목표 이력 — 최신 버전부터."""
    _get_chapter_or_404(cid, db)
    rows = db.scalars(
        select(ChapterGoalRevision)
        .where(ChapterGoalRevision.chapter_id == cid)
        .order_by(ChapterGoalRevision.goal_version.desc())
    ).all()
    return [_goal_revision_out(row) for row in rows]


@router.post("/chapters/{cid}/goal/restore", response_model=ChapterGoalOut)
def restore_chapter_goal(cid: int, payload: ChapterGoalRestoreRequest, db: Session = Depends(get_db)):
    """이력 버전을 현재 목표로 복원 — 과거를 덮지 않고 새 버전으로 기록한다."""
    chapter = _get_chapter_or_404(cid, db)
    revision = db.scalar(
        select(ChapterGoalRevision).where(
            ChapterGoalRevision.chapter_id == cid,
            ChapterGoalRevision.goal_version == payload.goal_version,
        )
    )
    if revision is None:
        raise HTTPException(status_code=404, detail="goal revision not found")
    _apply_goal_write(
        db,
        chapter,
        goal_json=dict(revision.goal_json or {}),
        episode_purpose=revision.episode_purpose,
        expected=payload.expected_goal_version,
        base_revision=(
            payload.base_manuscript_revision
            if payload.base_manuscript_revision is not None
            else int(chapter.revision or 0)
        ),
        restored_from=payload.goal_version,
    )
    db.refresh(chapter)
    return _goal_out(db, chapter)


# ---------- chapter flow (D03-1 집필 흐름 상태 기계) ----------
# flow_stage는 status(원고 성숙도)와 독립이다. 전이는 revision·snapshot·memo·
# 목표를 건드리지 않고, 전이 이벤트(append-only)에 목표 버전·원고 revision을
# 앵커로 기록한다. confirmed는 집필 확정이며 연재/발행 완결이 아니다.
ALLOWED_FLOW_TRANSITIONS: dict[str, frozenset[str]] = {
    "planning": frozenset({"writing"}),
    "writing": frozenset({"revising"}),
    "revising": frozenset({"writing", "confirmed"}),
    "confirmed": frozenset({"revising"}),
}

_FLOW_STAGE_LABELS = {
    "planning": "기획",
    "writing": "집필",
    "revising": "퇴고",
    "confirmed": "집필 확정",
}


def _flow_conflict(current_stage: str | None) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "flow_stage_conflict",
            "message": "집필 흐름 단계가 다른 곳에서 먼저 변경되었습니다. 최신 상태를 확인한 뒤 다시 시도하세요.",
            "current_flow_stage": current_stage,
        },
    )


def _fresh_flow_stage(db: Session, cid: int) -> str | None:
    db.expire_all()
    return db.scalar(select(Chapter.flow_stage).where(Chapter.id == cid))


def _flow_event_out(row: ChapterFlowEvent) -> ChapterFlowEventOut:
    return ChapterFlowEventOut(
        id=row.id,
        chapter_id=row.chapter_id,
        from_stage=row.from_stage,
        to_stage=row.to_stage,
        goal_version=row.goal_version,
        manuscript_revision=row.manuscript_revision,
        created_at=row.created_at,
    )


def _flow_out(db: Session, chapter: Chapter) -> ChapterFlowOut:
    last_event = db.scalar(
        select(ChapterFlowEvent)
        .where(ChapterFlowEvent.chapter_id == chapter.id)
        .order_by(ChapterFlowEvent.id.desc())
        .limit(1)
    )
    goal = _current_goal(db, chapter.id)
    return ChapterFlowOut(
        chapter_id=chapter.id,
        project_id=chapter.project_id,
        flow_stage=chapter.flow_stage,
        last_event=_flow_event_out(last_event) if last_event is not None else None,
        current_goal_version=goal.goal_version if goal is not None else None,
        current_chapter_revision=int(chapter.revision or 0),
    )


@router.get("/chapters/{cid}/flow", response_model=ChapterFlowOut)
def get_chapter_flow(cid: int, db: Session = Depends(get_db)):
    """회차 집필 흐름 상태 — 재개 시 마지막 전이의 목표 버전·원고 revision 앵커 포함."""
    chapter = _get_chapter_or_404(cid, db)
    return _flow_out(db, chapter)


@router.post("/chapters/{cid}/flow/transition", response_model=ChapterFlowOut)
def transition_chapter_flow(cid: int, payload: ChapterFlowTransition, db: Session = Depends(get_db)):
    """집필 흐름 전이 — expected_flow_stage CAS + 허용 전이만. 불법 전이는 422."""
    try:
        chapter = _get_chapter_or_404(cid, db)
        if payload.expected_flow_stage != chapter.flow_stage:
            raise _flow_conflict(chapter.flow_stage)
        if payload.to_stage not in ALLOWED_FLOW_TRANSITIONS.get(chapter.flow_stage, frozenset()):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"허용되지 않는 흐름 전이입니다: "
                    f"{_FLOW_STAGE_LABELS.get(chapter.flow_stage, chapter.flow_stage)} → "
                    f"{_FLOW_STAGE_LABELS.get(payload.to_stage, payload.to_stage)}"
                ),
            )
        result = db.execute(
            update(Chapter)
            .where(Chapter.id == cid, Chapter.flow_stage == payload.expected_flow_stage)
            .values(flow_stage=payload.to_stage)
        )
        if result.rowcount != 1:
            db.rollback()
            raise _flow_conflict(_fresh_flow_stage(db, cid))
        # 앵커는 writer lock을 잡은 뒤 읽어 커밋 시점의 상태를 기록한다.
        goal = _current_goal(db, cid)
        revision = db.scalar(select(Chapter.revision).where(Chapter.id == cid))
        db.add(
            ChapterFlowEvent(
                chapter_id=cid,
                from_stage=payload.expected_flow_stage,
                to_stage=payload.to_stage,
                goal_version=goal.goal_version if goal is not None else None,
                manuscript_revision=int(revision or 0),
            )
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise _flow_conflict(_fresh_flow_stage(db, cid)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        error_code = getattr(getattr(exc, "orig", None), "sqlite_errorcode", None)
        if error_code is not None and error_code & 0xFF == sqlite3.SQLITE_BUSY:
            raise HTTPException(status_code=409, detail="집필 흐름이 변경 중입니다. 새로고침 후 다시 시도하세요.") from exc
        logger.exception("chapter flow transition database failure: chapter_id=%s", cid)
        raise HTTPException(status_code=500, detail="흐름 전이 중 오류가 발생했습니다.") from exc
    db.refresh(chapter)
    return _flow_out(db, chapter)


@router.get("/chapters/{cid}/flow/events", response_model=list[ChapterFlowEventOut])
def list_chapter_flow_events(cid: int, db: Session = Depends(get_db)):
    """집필 흐름 전이 이력 — 최신 먼저."""
    _get_chapter_or_404(cid, db)
    rows = db.scalars(
        select(ChapterFlowEvent)
        .where(ChapterFlowEvent.chapter_id == cid)
        .order_by(ChapterFlowEvent.id.desc())
    ).all()
    return [_flow_event_out(row) for row in rows]


# ---------- D03-2 재개 계약 (순수 파생 읽기) ----------

@router.get("/chapters/{cid}/resume", response_model=ChapterResumeOut)
def get_chapter_resume(cid: int, db: Session = Depends(get_db)):
    """재개 요약 — D03-1 앵커 대비 드리프트, 미해결 감수 수, 다음 빈 장면.

    어떤 테이블도 변경하지 않는 파생 데이터다. pending_refine_runs는
    accepted=false인 윤문 실행 수(거절/미적용 구분은 기존 스키마 한계).
    """
    chapter = _get_chapter_or_404(cid, db)
    out = _flow_out(db, chapter)

    last = out.last_event
    goal_drift = bool(last) and out.current_goal_version != last.goal_version
    manuscript_drift = bool(last) and out.current_chapter_revision != last.manuscript_revision

    pending = db.scalar(
        select(func.count(RefineRun.id)).where(
            RefineRun.chapter_id == cid, RefineRun.accepted.is_(False)
        )
    ) or 0

    scenes = db.scalars(
        select(Scene).where(Scene.chapter_id == cid).order_by(Scene.sort_order, Scene.id)
    ).all()
    next_scene = next((s for s in scenes if not (s.content_md or "").strip()), None)

    return ChapterResumeOut(
        chapter_id=cid,
        project_id=chapter.project_id,
        flow_stage=out.flow_stage,
        last_event=last,
        current_goal_version=out.current_goal_version,
        current_chapter_revision=out.current_chapter_revision,
        goal_changed_since_transition=goal_drift,
        manuscript_changed_since_transition=manuscript_drift,
        pending_refine_runs=int(pending),
        next_scene=next_scene,
        scene_count=len(scenes),
    )


# ---------- EvidenceLinks (D03-4 근거 연결) ----------
# 목표 필드(사건/선택/대가) ↔ 원문 발췌의 수동 링크. 자동 판정 없음 — §6.3.
_EVIDENCE_LIST_FIELDS = {"core_events", "character_choices"}


def _goal_item_at(goal_json: dict, field: str, item_index: int | None) -> str | None:
    """현재 목표 JSON에서 (field, item_index) 위치의 항목 텍스트. 없으면 None."""
    value = (goal_json or {}).get(field)
    if item_index is None:
        return value if isinstance(value, str) and value.strip() else None
    if not isinstance(value, list) or not (0 <= item_index < len(value)):
        return None
    item = value[item_index]
    return item if isinstance(item, str) and item.strip() else None


def _evidence_link_out(link: ChapterGoalEvidenceLink, chapter: Chapter, goal: ChapterGoal | None) -> EvidenceLinkOut:
    manuscript_status = "intact" if link.excerpt in (chapter.content_md or "") else "broken"
    if goal is None:
        goal_status, current_goal_version = "goal_deleted", None
    else:
        current_goal_version = goal.goal_version
        current_item = _goal_item_at(goal.goal_json, link.goal_field, link.item_index)
        goal_status = "unchanged" if current_item == link.goal_item_text else "drifted"
    return EvidenceLinkOut(
        id=link.id,
        chapter_id=link.chapter_id,
        goal_field=link.goal_field,
        item_index=link.item_index,
        goal_item_text=link.goal_item_text,
        excerpt=link.excerpt,
        goal_version=link.goal_version,
        current_goal_version=current_goal_version,
        manuscript_status=manuscript_status,
        goal_status=goal_status,
        created_at=link.created_at,
    )


@router.get("/chapters/{cid}/evidence-links", response_model=EvidenceLinkListOut)
def list_evidence_links(cid: int, db: Session = Depends(get_db)):
    """근거 링크 목록 — 파생 상태만 계산하는 읽기. 어떤 행도 쓰지 않는다."""
    chapter = _get_chapter_or_404(cid, db)
    goal = _current_goal(db, cid)
    links = db.scalars(
        select(ChapterGoalEvidenceLink)
        .where(ChapterGoalEvidenceLink.chapter_id == cid)
        .order_by(ChapterGoalEvidenceLink.id)
    ).all()
    return EvidenceLinkListOut(
        chapter_id=cid,
        links=[_evidence_link_out(link, chapter, goal) for link in links],
    )


@router.post("/chapters/{cid}/evidence-links", response_model=EvidenceLinkOut, status_code=status.HTTP_201_CREATED)
def create_evidence_link(cid: int, payload: EvidenceLinkCreate, db: Session = Depends(get_db)):
    """근거 링크 생성 — 발췌문이 현재 원문에 있고 목표 항목이 존재해야 한다."""
    try:
        # Reserve the writer slot before reading: a concurrent goal write/delete or
        # manuscript save cannot slip between validation and the INSERT.
        db.execute(text("BEGIN IMMEDIATE"))
        chapter = _get_chapter_or_404(cid, db)
        excerpt = payload.excerpt
        if not excerpt.strip():
            raise HTTPException(status_code=422, detail="excerpt must not be blank")
        if excerpt not in (chapter.content_md or ""):
            raise HTTPException(status_code=422, detail="excerpt not found in manuscript")
        if payload.goal_field in _EVIDENCE_LIST_FIELDS:
            if payload.item_index is None:
                raise HTTPException(status_code=422, detail="item_index required for list goal field")
        elif payload.item_index is not None:
            raise HTTPException(status_code=422, detail="item_index not allowed for scalar goal field")
        goal = _current_goal(db, cid)
        if goal is None:
            raise HTTPException(status_code=422, detail="no current goal to link")
        item_text = _goal_item_at(goal.goal_json, payload.goal_field, payload.item_index)
        if item_text is None:
            raise HTTPException(status_code=422, detail="goal item not found at field/index")
        link = ChapterGoalEvidenceLink(
            chapter_id=cid,
            goal_version=goal.goal_version,
            goal_field=payload.goal_field,
            item_index=payload.item_index,
            goal_item_text=item_text,
            excerpt=excerpt,
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        return _evidence_link_out(link, chapter, goal)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        error_code = getattr(getattr(exc, "orig", None), "sqlite_errorcode", None)
        if error_code is not None and error_code & 0xFF == sqlite3.SQLITE_BUSY:
            raise HTTPException(status_code=409, detail="근거 링크가 변경 중입니다. 새로고침 후 다시 시도하세요.") from exc
        logger.exception("evidence link create database failure: chapter_id=%s", cid)
        raise HTTPException(status_code=500, detail="근거 링크 저장 중 오류가 발생했습니다.") from exc


@router.delete("/chapters/{cid}/evidence-links/{lid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evidence_link(cid: int, lid: int, db: Session = Depends(get_db)):
    try:
        _get_chapter_or_404(cid, db)
        link = db.get(ChapterGoalEvidenceLink, lid)
        if link is None or link.chapter_id != cid:
            raise HTTPException(status_code=404, detail="evidence link not found")
        db.delete(link)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        error_code = getattr(getattr(exc, "orig", None), "sqlite_errorcode", None)
        if error_code is not None and error_code & 0xFF == sqlite3.SQLITE_BUSY:
            raise HTTPException(status_code=409, detail="근거 링크가 변경 중입니다. 새로고침 후 다시 시도하세요.") from exc
        logger.exception("evidence link delete database failure: chapter_id=%s, link_id=%s", cid, lid)
        raise HTTPException(status_code=500, detail="근거 링크 삭제 중 오류가 발생했습니다.") from exc


@router.delete("/chapters/{cid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chapter(cid: int, db: Session = Depends(get_db)):
    try:
        # Reserve SQLite's writer slot before any read: a new memory cannot commit
        # between the reference check and ORM/FK cascade deletion.
        db.execute(text("BEGIN IMMEDIATE"))
        chapter = _get_chapter_or_404(cid, db)
        has_foreshadow = db.scalar(
            select(Foreshadow.id).where(
                (Foreshadow.planted_chapter_id == cid)
                | (Foreshadow.resolved_chapter_id == cid)
            ).limit(1)
        )
        if has_foreshadow is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="복선이 연결된 회차는 복선 참조를 먼저 정리해야 합니다",
            )
        has_memory = db.scalar(
            select(MemoryEntry.id).where(MemoryEntry.chapter_id == cid).limit(1)
        )
        if has_memory is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="장편 기억이 연결된 회차는 근거 이력 보존을 위해 삭제할 수 없습니다. 폐기된 기억도 연결이 유지됩니다.",
            )
        has_event_impact = db.scalar(
            select(EventImpact.id).where(EventImpact.chapter_id == cid).limit(1)
        )
        if has_event_impact is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="사건 영향이 연결된 회차는 사건 영향 이력을 먼저 정리해야 합니다",
            )
        db.delete(chapter)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        error_code = getattr(getattr(exc, "orig", None), "sqlite_errorcode", None)
        if error_code is not None and error_code & 0xFF == sqlite3.SQLITE_BUSY:
            raise HTTPException(status_code=409, detail="회차가 변경 중입니다. 새로고침 후 다시 시도하세요.") from exc
        logger.exception("chapter delete database failure: chapter_id=%s", cid)
        raise HTTPException(status_code=500, detail="회차 삭제 중 오류가 발생했습니다.") from exc


# ---------- chapters bulk reorder (Sprint 2) ----------
@router.patch("/projects/{pid}/chapters/reorder", response_model=list[ChapterOut])
def reorder_chapters(pid: int, payload: ChaptersReorder, db: Session = Depends(get_db)):
    """순서/권 일괄 변경. 모든 id가 해당 프로젝트 소속이어야 한다(원자성)."""
    _get_project_or_404(pid, db)

    ids = [item.id for item in payload.items]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="duplicate chapter ids in items")

    chapters = {
        c.id: c for c in db.scalars(select(Chapter).where(Chapter.project_id == pid)).all()
    }
    missing = [cid for cid in ids if cid not in chapters]
    if missing:
        raise HTTPException(status_code=422, detail=f"chapters not in project: {missing}")

    for item in payload.items:
        chapter = chapters[item.id]
        if "volume" in item.model_fields_set:
            chapter.volume = item.volume
        if item.sort_order is not None:
            chapter.sort_order = item.sort_order

    db.commit()

    ordered = sorted(
        chapters.values(),
        key=lambda c: (c.volume is None, c.volume if c.volume is not None else 0, c.sort_order),
    )  # Q1: volume None(평면 회차)은 항상 마지막에 정렬
    return list(ordered)


# ---------- 노벨피아 PLUS 충족 현황 (A-038 / F-033) ----------
@router.get("/projects/{pid}/plus-status", response_model=PlusStatusOut)
def get_plus_status(pid: int, db: Session = Depends(get_db)):
    """노벨피아 PLUS 충족 현황을 서버 계산으로 반환한다.

    - 회차 수 기준: 프로젝트 내 회차 수 ≥ 15회 (결정사항_G4 Q3 확정)
    - 글자 수 기준: '완료' 회차가 1개 이상이고, 그 모든 회차의
      word_count_cache(노벨피아 모드: 공백·문장부호·특수문자 제외) ≥ 3,000. 완료 회차가 없으면 미충족.
      (부록06: 노벨피아 실제 집계는 공백+특수문자 제외 — 최종 확정은 G7 실측,
       본 API는 설계서 기준인 공백제외 캐시로 판정)
    """
    _get_project_or_404(pid, db)
    chapters = db.scalars(select(Chapter).where(Chapter.project_id == pid)).all()
    done = [c for c in chapters if c.status == "완료"]
    done_over_3000 = sum(1 for c in done if c.word_count_cache >= PLUS_MIN_CHARS_DONE)
    chapter_count_met = len(chapters) >= PLUS_MIN_CHAPTERS
    done_chars_met = bool(done) and done_over_3000 == len(done)
    return PlusStatusOut(
        chapter_count=len(chapters),
        chapter_count_met=chapter_count_met,
        done_chapter_count=len(done),
        done_chapters_3000=done_over_3000,
        done_chars_met=done_chars_met,
        eligible=chapter_count_met and done_chars_met,
    )


# ---------- 완결본 관리 (D03-6) ----------
# 완결 점검표는 파생 읽기, 완결본은 명시적 생성의 불변 스냅샷.
# 자동 완결 판정·자동 스냅샷 생성 없음(§6.3).

FLOW_STAGES = ("planning", "writing", "revising", "confirmed")
DISPOSITION_KEYS = ("resolved", "intentional_unresolved", "side_story", "closed_unclassified")


def _completion_checklist(db: Session, project: Project) -> CompletionChecklist:
    chapters = db.scalars(
        select(Chapter).where(Chapter.project_id == project.id)
    ).all()
    by_stage = {s: 0 for s in FLOW_STAGES}
    for ch in chapters:
        by_stage[ch.flow_stage] = by_stage.get(ch.flow_stage, 0) + 1

    foreshadows = db.scalars(
        select(Foreshadow)
        .where(Foreshadow.project_id == project.id)
        .order_by(Foreshadow.id)
    ).all()
    by_disposition = {k: 0 for k in DISPOSITION_KEYS}
    open_rows = []
    for f in foreshadows:
        if f.status == "설치":
            open_rows.append({"id": f.id, "title": f.title, "status": f.status})
        elif f.disposition:
            by_disposition[f.disposition] += 1
        else:
            by_disposition["closed_unclassified"] += 1

    chapter_ids = [c.id for c in chapters]
    pending_refine = 0
    broken_links = 0
    if chapter_ids:
        pending_refine = db.scalar(
            select(func.count(RefineRun.id)).where(
                RefineRun.chapter_id.in_(chapter_ids),
                RefineRun.accepted.is_(False),
            )
        ) or 0
        links = db.scalars(
            select(ChapterGoalEvidenceLink).where(
                ChapterGoalEvidenceLink.chapter_id.in_(chapter_ids)
            )
        ).all()
        content_by_id = {c.id: c.content_md or "" for c in chapters}
        broken_links = sum(
            1 for l in links if l.excerpt not in content_by_id.get(l.chapter_id, "")
        )

    goals = db.scalars(
        select(ChapterGoal).where(ChapterGoal.chapter_id.in_(chapter_ids or [-1]))
    ).all()
    title_by_id = {c.id: c.title for c in chapters}
    finale_missing = [
        {"chapter_id": g.chapter_id, "title": title_by_id.get(g.chapter_id, "")}
        for g in goals
        if g.episode_purpose == "series_finale"
        and not (g.goal_json or {}).get("ending_intent")
    ]
    finale_missing.sort(key=lambda g: g["chapter_id"])

    return CompletionChecklist(
        serial_state=project.serial_state,
        serial_completed_at=project.serial_completed_at,
        chapters={
            "total": len(chapters),
            "by_stage": by_stage,
            "unconfirmed": len(chapters) - by_stage["confirmed"],
        },
        foreshadows={
            "total": len(foreshadows),
            "open": open_rows,
            "by_disposition": by_disposition,
        },
        pending_refine_runs=pending_refine,
        broken_evidence_links=broken_links,
        finale_goals_missing_ending=finale_missing,
    )


@router.get("/projects/{pid}/completion-checklist", response_model=CompletionChecklist)
def get_completion_checklist(pid: int, db: Session = Depends(get_db)):
    project = _get_project_or_404(pid, db)
    return _completion_checklist(db, project)


def _final_edition_out(row: ProjectFinalEdition, detail: bool) -> FinalEditionOut | FinalEditionDetail:
    base = {
        "id": row.id,
        "project_id": row.project_id,
        "label": row.label,
        "created_at": row.created_at,
        "serial_state": row.serial_state,
        "chapter_count": row.chapter_count,
        "total_chars": row.total_chars,
    }
    if not detail:
        return FinalEditionOut(**base)
    return FinalEditionDetail(
        **base,
        manifest=[FinalEditionChapterEntry(**m) for m in (row.manifest_json or [])],
        content_md=row.content_md,
        checklist=CompletionChecklist(**(row.checklist_json or {})),
    )


@router.post(
    "/projects/{pid}/final-editions",
    response_model=FinalEditionDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_final_edition(pid: int, payload: FinalEditionCreate, db: Session = Depends(get_db)):
    try:
        db.execute(text("BEGIN IMMEDIATE"))
        project = _get_project_or_404(pid, db)
        chapters = db.scalars(
            select(Chapter)
            .where(Chapter.project_id == pid)
            .order_by(Chapter.sort_order, Chapter.id)
        ).all()
        manifest = [
            {
                "chapter_id": c.id,
                "title": c.title,
                "sort_order": c.sort_order,
                "revision": c.revision,
                "flow_stage": c.flow_stage,
                "status": c.status,
                "chars": len(c.content_md or ""),
            }
            for c in chapters
        ]
        content_md = "\n\n".join(
            f"## {c.title}\n\n{c.content_md or ''}".rstrip() for c in chapters
        )
        label = (payload.label or "").strip() or None
        row = ProjectFinalEdition(
            project_id=pid,
            label=label,
            serial_state=project.serial_state,
            chapter_count=len(chapters),
            total_chars=len(content_md),
            manifest_json=manifest,
            content_md=content_md,
            checklist_json=_completion_checklist(db, project).model_dump(mode="json"),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _final_edition_out(row, detail=True)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        error_code = getattr(getattr(exc, "orig", None), "sqlite_errorcode", None)
        if error_code is not None and error_code & 0xFF == sqlite3.SQLITE_BUSY:
            raise HTTPException(status_code=409, detail="완결본 생성이 충돌했습니다. 다시 시도하세요.") from exc
        logger.exception("final edition create database failure: project_id=%s", pid)
        raise HTTPException(status_code=500, detail="완결본 생성 중 오류가 발생했습니다.") from exc


@router.get("/projects/{pid}/final-editions", response_model=list[FinalEditionOut])
def list_final_editions(pid: int, db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    rows = db.scalars(
        select(ProjectFinalEdition)
        .where(ProjectFinalEdition.project_id == pid)
        .order_by(ProjectFinalEdition.created_at.desc(), ProjectFinalEdition.id.desc())
    ).all()
    return [_final_edition_out(r, detail=False) for r in rows]


def _get_final_edition_or_404(pid: int, eid: int, db: Session) -> ProjectFinalEdition:
    _get_project_or_404(pid, db)
    row = db.get(ProjectFinalEdition, eid)
    if row is None or row.project_id != pid:
        raise HTTPException(status_code=404, detail="final edition not found")
    return row


@router.get("/projects/{pid}/final-editions/{eid}", response_model=FinalEditionDetail)
def get_final_edition(pid: int, eid: int, db: Session = Depends(get_db)):
    row = _get_final_edition_or_404(pid, eid, db)
    return _final_edition_out(row, detail=True)


@router.delete("/projects/{pid}/final-editions/{eid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_final_edition(pid: int, eid: int, db: Session = Depends(get_db)):
    try:
        row = _get_final_edition_or_404(pid, eid, db)
        db.delete(row)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        error_code = getattr(getattr(exc, "orig", None), "sqlite_errorcode", None)
        if error_code is not None and error_code & 0xFF == sqlite3.SQLITE_BUSY:
            raise HTTPException(status_code=409, detail="완결본이 변경 중입니다. 다시 시도하세요.") from exc
        logger.exception("final edition delete database failure: project_id=%s, edition_id=%s", pid, eid)
        raise HTTPException(status_code=500, detail="완결본 삭제 중 오류가 발생했습니다.") from exc


# ---------- 결말 변경 영향 (D03-7) ----------
# 파생 읽기 전용 — 미해결 복선·옛 결말 가정 목표·최종화 회차의 사실 나열.

@router.get("/projects/{pid}/ending-impact", response_model=EndingImpactOut)
def get_ending_impact(pid: int, db: Session = Depends(get_db)):
    project = _get_project_or_404(pid, db)

    open_foreshadows = db.scalars(
        select(Foreshadow)
        .where(Foreshadow.project_id == pid, Foreshadow.status == "설치")
        .order_by(Foreshadow.id)
    ).all()

    chapters = db.scalars(
        select(Chapter).where(Chapter.project_id == pid)
    ).all()
    title_by_id = {c.id: c.title for c in chapters}
    chapter_ids = [c.id for c in chapters]

    stale: list[dict] = []
    finale: list[dict] = []
    if chapter_ids:
        goals = db.scalars(
            select(ChapterGoal).where(ChapterGoal.chapter_id.in_(chapter_ids))
        ).all()
        for g in goals:
            if (
                project.ending_updated_at is not None
                and g.updated_at is not None
                and g.updated_at < project.ending_updated_at
            ):
                stale.append({
                    "chapter_id": g.chapter_id,
                    "title": title_by_id.get(g.chapter_id, ""),
                    "goal_version": g.goal_version,
                })
            if g.episode_purpose == "series_finale":
                finale.append({
                    "chapter_id": g.chapter_id,
                    "title": title_by_id.get(g.chapter_id, ""),
                    "has_ending_intent": bool((g.goal_json or {}).get("ending_intent")),
                })
    stale.sort(key=lambda s: s["chapter_id"])
    finale.sort(key=lambda f: f["chapter_id"])

    return EndingImpactOut(
        ending_intent=project.ending_intent,
        ending_locked=project.ending_locked,
        ending_updated_at=project.ending_updated_at,
        open_foreshadows=[
            {"id": f.id, "title": f.title} for f in open_foreshadows
        ],
        stale_goal_chapters=stale,
        finale_chapters=finale,
    )


@router.get("/projects/{pid}/writing-activity")
def writing_activity(
    pid: int,
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """O03 — 일별 집필 활동 버킷(updated_at 기준, chars는 현재 길이 스냅샷)."""
    if db.get(Project, pid) is None:
        raise HTTPException(status_code=404, detail="project not found")

    day_expr = func.date(Chapter.updated_at)
    cutoff = func.date("now", f"-{days} days")
    rows = db.execute(
        select(
            day_expr.label("day"),
            func.count(Chapter.id).label("chapters"),
            func.coalesce(func.sum(Chapter.word_count_cache), 0).label("chars"),
        )
        .where(Chapter.project_id == pid, day_expr >= cutoff)
        .group_by(day_expr)
        .order_by(day_expr)
    ).all()

    buckets = [
        {"date": day, "chapters": chapters, "chars": chars}
        for day, chapters, chars in rows
    ]
    return {
        "project_id": pid,
        "days": days,
        "buckets": buckets,
        "totals": {
            "active_days": len(buckets),
            "chapters": sum(b["chapters"] for b in buckets),
            "chars": sum(b["chars"] for b in buckets),
        },
    }


# ---------- 레퍼런스 스타일 분석 ----------
@router.post("/projects/{pid}/style-analysis", response_model=StyleAnalysisResponse)
async def analyze_reference_style(
        pid: int, payload: StyleAnalysisRequest, db: Session = Depends(get_db)):
    """작가 제공 레퍼런스 텍스트 → 스타일 지표 + 문체 프로파일 초안.

    외부 인기작 자동 수집은 없다 — 작가가 붙여넣은 텍스트만 분석한다.
    profile_draft는 저장하지 않고 반환만 한다. 작가가 검토·수정 후
    PATCH /projects/{pid} 의 style_profile로 적용한다.
    """
    _get_project_or_404(pid, db)
    from app.services import gpt_oauth, llm
    from app.services import style_analysis

    metrics = style_analysis.analyze_text(payload.text)
    try:
        provider = gpt_oauth.get_provider()
    except gpt_oauth.OAuthProviderConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    messages = style_analysis.build_analysis_messages(payload.text, metrics)
    client = llm.make_client(provider.base_url, None)
    try:
        draft = await llm.complete_chat(
            client, provider.default_model, messages,
            reasoning_effort=provider.reasoning_effort)
    except Exception as exc:  # noqa: BLE001 — transport 실패를 502로 변환
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"스타일 분석 호출 실패: {type(exc).__name__}") from exc
    finally:
        await client.close()
    return StyleAnalysisResponse(
        metrics=metrics.to_dict(), profile_draft=draft.strip())
