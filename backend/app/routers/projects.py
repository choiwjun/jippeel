"""프로젝트·회차 라우터 (사양 §5 M1, Sprint 1 범위)."""
import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chapter, ChapterSnapshot, Character, Foreshadow, MemoryEntry, Project, Relationship
from app.schemas import BootstrapRequest, BootstrapResponse, PlusStatusOut, PLUS_MIN_CHAPTERS, PLUS_MIN_CHARS_DONE
from app.services import bootstrap as bootstrap_service
from app.services import manuscripts
from app.schemas import (
    ChaptersReorder,
    ChapterContentPut,
    ChapterCreate,
    ChapterRestorePost,
    ChapterSnapshotDetail,
    ChapterSnapshotOut,
    ChapterDetail,
    ChapterOut,
    ChapterUpdate,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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
        client = llm.make_client(provider.base_url, None)
        try:
            structure = await bootstrap_service.generate_structure(
                payload.genre, payload.premise, payload.title_style,
                payload.volume_count, payload.chapters_per_volume,
                client, provider.default_model,
                reasoning_effort=provider.reasoning_effort)
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
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
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
