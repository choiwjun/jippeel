"""프로젝트·회차 라우터 (사양 §5 M1, Sprint 1 범위)."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chapter, Project
from app.schemas import BootstrapRequest, BootstrapResponse
from app.services import bootstrap as bootstrap_service
from app.schemas import (
    ChaptersReorder,
    ChapterContentPut,
    ChapterCreate,
    ChapterDetail,
    ChapterOut,
    ChapterUpdate,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
)
from app.services.wordcount import count_chars_excluding_whitespace

router = APIRouter()


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
            endpoint, model = bootstrap_service.resolve_endpoint(db)
        except bootstrap_service.NoEndpointError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=str(exc)) from exc
        from app.services import llm
        client = llm.make_client(endpoint.base_url, endpoint.api_key_encrypted)
        try:
            structure = await bootstrap_service.generate_structure(
                payload.genre, payload.premise, payload.title_style,
                payload.volume_count, payload.chapters_per_volume,
                client, model)
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
    return db.scalars(select(Project).order_by(Project.updated_at.desc())).all()


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
        .order_by(Chapter.volume, Chapter.sort_order)
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


@router.put("/chapters/{cid}/content", response_model=ChapterDetail)
def put_chapter_content(cid: int, payload: ChapterContentPut, db: Session = Depends(get_db)):
    """본문(content_md) 저장 + 공백 제외 글자 수 캐시 갱신."""
    chapter = _get_chapter_or_404(cid, db)
    chapter.content_md = payload.content_md
    chapter.word_count_cache = count_chars_excluding_whitespace(payload.content_md)
    db.commit()
    db.refresh(chapter)
    return chapter


@router.delete("/chapters/{cid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chapter(cid: int, db: Session = Depends(get_db)):
    chapter = _get_chapter_or_404(cid, db)
    db.delete(chapter)
    db.commit()


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
        if item.volume is not None:
            chapter.volume = item.volume
        if item.sort_order is not None:
            chapter.sort_order = item.sort_order

    db.commit()

    ordered = sorted(chapters.values(), key=lambda c: (c.volume, c.sort_order))
    return list(ordered)
