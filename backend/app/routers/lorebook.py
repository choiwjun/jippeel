"""로어북 라우터 (사양 §5 M3, FR-301~305 / Sprint 2).

검색(FR-304)은 FTS5 인덱스를 선택 적용하고, 미지원 빌드/쿼리 오류 시 LIKE 폴백.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chapter, LoreEntry, Project
from app.schemas import ChapterOut, KeywordsPut, LoreEntryCreate, LoreEntryOut, LoreEntryUpdate
from app.services.fts import delete_fts_entry, ensure_fts_index, search_entry_ids, sync_fts_entry
from app.services.injection import score_entries

router = APIRouter()


def _get_project_or_404(pid: int, db: Session) -> Project:
    project = db.get(Project, pid)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _get_entry_or_404(lid: int, db: Session) -> LoreEntry:
    entry = db.get(LoreEntry, lid)
    if entry is None:
        raise HTTPException(status_code=404, detail="lore entry not found")
    return entry


# ---------- lore entries CRUD ----------
@router.get("/projects/{pid}/lore", response_model=list[LoreEntryOut])
def list_lore(
    pid: int,
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _get_project_or_404(pid, db)
    stmt = select(LoreEntry).where(LoreEntry.project_id == pid).order_by(LoreEntry.id)
    if category is not None:
        stmt = stmt.where(LoreEntry.category == category)
    return db.scalars(stmt).all()


@router.post(
    "/projects/{pid}/lore",
    response_model=LoreEntryOut,
    status_code=status.HTTP_201_CREATED,
)
def create_lore(pid: int, payload: LoreEntryCreate, db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    entry = LoreEntry(project_id=pid, **payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    sync_fts_entry(db, entry)
    db.commit()
    return entry


@router.get("/projects/{pid}/lore/search", response_model=list[LoreEntryOut])
def search_lore(
    pid: int,
    q: str = Query(min_length=1),
    category: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """키워드 검색 (FR-304). FTS5 MATCH → 실패 시 LIKE 폴백."""
    _get_project_or_404(pid, db)
    ids = search_entry_ids(db, q, limit=limit, project_id=pid, category=category)
    if ids is not None:
        # FTS5 경로: 매치 없으면 빈 목록 (폴백 미사용)
        if not ids:
            return []
        stmt = (
            select(LoreEntry)
            .where(LoreEntry.project_id == pid, LoreEntry.id.in_(ids))
            .order_by(LoreEntry.id)
        )
    else:
        # FTS 미지원 빌드 또는 쿼리 문법 오류 → LIKE 폴백(title/content/keywords)
        like = f"%{q}%"
        stmt = (
            select(LoreEntry)
            .where(
                LoreEntry.project_id == pid,
                LoreEntry.title.like(like)
                | LoreEntry.content.like(like)
                | LoreEntry.keywords.like(like),
            )
            .order_by(LoreEntry.id)
            .limit(limit)
        )
    if category is not None:
        stmt = stmt.where(LoreEntry.category == category)
    return db.scalars(stmt).all()


@router.get("/lore/{lid}", response_model=LoreEntryOut)
def get_lore(lid: int, db: Session = Depends(get_db)):
    return _get_entry_or_404(lid, db)


@router.get("/lore/{lid}/referencing-chapters", response_model=list[ChapterOut])
def referencing_chapters(lid: int, db: Session = Depends(get_db)):
    """이 로어 항목을 본문에서 참조하는 회차 목록 (U02 / F-016).

    AI 자동 주입과 동일한 title·keywords 부분일치 매칭을 회차 본문에 역방향으로
    적용한다 — 점수>0인 회차만 반환, sort_order 순.
    """
    entry = _get_entry_or_404(lid, db)
    chapters = db.scalars(
        select(Chapter)
        .where(Chapter.project_id == entry.project_id)
        .order_by(Chapter.sort_order, Chapter.id)
    ).all()
    return [
        chapter
        for chapter in chapters
        if score_entries([entry], chapter.content_md or "")
    ]


@router.patch("/lore/{lid}", response_model=LoreEntryOut)
def update_lore(lid: int, payload: LoreEntryUpdate, db: Session = Depends(get_db)):
    entry = _get_entry_or_404(lid, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    sync_fts_entry(db, entry)
    db.commit()
    return entry


@router.put("/lore/{lid}/keywords", response_model=LoreEntryOut)
def put_keywords(lid: int, payload: KeywordsPut, db: Session = Depends(get_db)):
    """keywords[] 전체 교체 (자동 컨텍스트 주입 기반 — 백로그 P1)."""
    entry = _get_entry_or_404(lid, db)
    entry.keywords = list(dict.fromkeys(payload.keywords))  # 중복 제거, 순서 유지
    db.commit()
    db.refresh(entry)
    sync_fts_entry(db, entry)
    db.commit()
    return entry


@router.delete("/lore/{lid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lore(lid: int, db: Session = Depends(get_db)):
    entry = _get_entry_or_404(lid, db)
    delete_fts_entry(db, entry.id)
    db.delete(entry)
    db.commit()
