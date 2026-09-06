"""복선(foreshadow) 라우터 — 고도화 G-020~G-021.

복선은 "설치 → 회수" 상태로 관리하며, 미회수(설치) 복선은
POST /ai/generate의 context.auto_foreshadow로 자동 주입된다(G-022).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chapter, Foreshadow, Project
from app.schemas import ForeshadowCreate, ForeshadowOut, ForeshadowUpdate

router = APIRouter()

VALID_STATUS = ("설치", "회수", "보류")


def _get_project_or_404(pid: int, db: Session) -> Project:
    project = db.get(Project, pid)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _get_foreshadow_or_404(fid: int, db: Session) -> Foreshadow:
    row = db.get(Foreshadow, fid)
    if row is None:
        raise HTTPException(status_code=404, detail="foreshadow not found")
    return row


def _validate_chapter_refs(payload, db: Session) -> None:
    for field in ("planted_chapter_id", "resolved_chapter_id"):
        cid = getattr(payload, field, None)
        if cid is not None and db.get(Chapter, cid) is None:
            raise HTTPException(status_code=422, detail=f"{field}가 존재하지 않는 회차입니다")


@router.get("/projects/{pid}/foreshadows", response_model=list[ForeshadowOut])
def list_foreshadows(pid: int, status_filter: str | None = None,
                     db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    stmt = select(Foreshadow).where(Foreshadow.project_id == pid).order_by(
        Foreshadow.created_at, Foreshadow.id)
    if status_filter:
        if status_filter not in VALID_STATUS:
            raise HTTPException(status_code=422,
                                detail="status는 설치|회수|보류 중 하나여야 합니다")
        stmt = stmt.where(Foreshadow.status == status_filter)
    return list(db.scalars(stmt).all())


@router.post("/projects/{pid}/foreshadows", response_model=ForeshadowOut,
             status_code=status.HTTP_201_CREATED)
def create_foreshadow(pid: int, payload: ForeshadowCreate, db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    _validate_chapter_refs(payload, db)
    row = Foreshadow(
        project_id=pid,
        title=payload.title,
        content=payload.content,
        keywords=payload.keywords or [],
        status=payload.status,
        planted_chapter_id=payload.planted_chapter_id,
        resolved_chapter_id=payload.resolved_chapter_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/foreshadows/{fid}", response_model=ForeshadowOut)
def update_foreshadow(fid: int, payload: ForeshadowUpdate, db: Session = Depends(get_db)):
    row = _get_foreshadow_or_404(fid, db)
    data = payload.model_dump(exclude_unset=True)
    _validate_chapter_refs(payload, db)
    if "status" in data and data["status"] not in VALID_STATUS:
        raise HTTPException(status_code=422, detail="status는 설치|회수|보류 중 하나여야 합니다")
    for field, value in data.items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/foreshadows/{fid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_foreshadow(fid: int, db: Session = Depends(get_db)):
    row = _get_foreshadow_or_404(fid, db)
    db.delete(row)
    db.commit()
