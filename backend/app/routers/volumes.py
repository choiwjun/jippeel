"""권 개요(VolumeNote) 라우터 — 고도화 G-050.

부트스트랩 목차와 회차 본문 사이의 중간 서사 레이어:
권 단위 개요·감정 곡선·고봉 노트를 관리한다. AI 패널 목차 주입(G-001)이
권 개요도 함께 전달하면 회차가 권 전체 방향과 어긋나지 않는다.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project, VolumeNote
from app.schemas import VolumeNoteCreate, VolumeNoteOut, VolumeNoteUpdate

router = APIRouter()


def _get_project_or_404(pid: int, db: Session) -> Project:
    project = db.get(Project, pid)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _get_note_or_404(nid: int, db: Session) -> VolumeNote:
    note = db.get(VolumeNote, nid)
    if note is None:
        raise HTTPException(status_code=404, detail="volume note not found")
    return note


@router.get("/projects/{pid}/volume-notes", response_model=list[VolumeNoteOut])
def list_volume_notes(pid: int, db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    rows = db.scalars(
        select(VolumeNote).where(VolumeNote.project_id == pid)
        .order_by(VolumeNote.volume)).all()
    return list(rows)


@router.post("/projects/{pid}/volume-notes", response_model=VolumeNoteOut,
             status_code=status.HTTP_201_CREATED)
def create_volume_note(pid: int, payload: VolumeNoteCreate, db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    exists = db.scalars(
        select(VolumeNote).where(
            VolumeNote.project_id == pid, VolumeNote.volume == payload.volume)).first()
    if exists is not None:
        raise HTTPException(status_code=422,
                            detail=f"{payload.volume}권 개요가 이미 있습니다 — 수정을 사용하세요")
    note = VolumeNote(project_id=pid, **payload.model_dump())
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.patch("/volume-notes/{nid}", response_model=VolumeNoteOut)
def update_volume_note(nid: int, payload: VolumeNoteUpdate, db: Session = Depends(get_db)):
    note = _get_note_or_404(nid, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(note, field, value)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/volume-notes/{nid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_volume_note(nid: int, db: Session = Depends(get_db)):
    note = _get_note_or_404(nid, db)
    db.delete(note)
    db.commit()
