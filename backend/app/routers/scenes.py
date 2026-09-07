"""장면(Scene) 라우터 — 고도화 G-010~G-013.

회차 → 장면 계층. 장면 단위 AI 생성은 POST /ai/generate의
context.scene_id로 처리한다(라우터 분리 원칙 유지).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chapter, Scene
from app.schemas import ChapterDetail, SceneCreate, SceneMergePut, SceneOut, SceneUpdate, ScenesReorder
from app.services import manuscripts

router = APIRouter()


def _get_chapter_or_404(cid: int, db: Session) -> Chapter:
    chapter = db.get(Chapter, cid)
    if chapter is None:
        raise HTTPException(status_code=404, detail="chapter not found")
    return chapter


def _get_scene_or_404(sid: int, db: Session) -> Scene:
    scene = db.get(Scene, sid)
    if scene is None:
        raise HTTPException(status_code=404, detail="scene not found")
    return scene


@router.get("/chapters/{cid}/scenes", response_model=list[SceneOut])
def list_scenes(cid: int, db: Session = Depends(get_db)):
    _get_chapter_or_404(cid, db)
    rows = db.scalars(
        select(Scene).where(Scene.chapter_id == cid).order_by(Scene.sort_order, Scene.id)
    ).all()
    return list(rows)


@router.post("/chapters/{cid}/scenes", response_model=SceneOut,
             status_code=status.HTTP_201_CREATED)
def create_scene(cid: int, payload: SceneCreate, db: Session = Depends(get_db)):
    _get_chapter_or_404(cid, db)
    scene = Scene(chapter_id=cid, title=payload.title,
                  sort_order=payload.sort_order, content_md=payload.content_md)
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return scene


@router.get("/scenes/{sid}", response_model=SceneOut)
def get_scene(sid: int, db: Session = Depends(get_db)):
    return _get_scene_or_404(sid, db)


@router.patch("/scenes/{sid}", response_model=SceneOut)
def update_scene(sid: int, payload: SceneUpdate, db: Session = Depends(get_db)):
    scene = _get_scene_or_404(sid, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(scene, field, value)
    db.commit()
    db.refresh(scene)
    return scene


@router.delete("/scenes/{sid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scene(sid: int, db: Session = Depends(get_db)):
    scene = _get_scene_or_404(sid, db)
    db.delete(scene)
    db.commit()


@router.patch("/chapters/{cid}/scenes/order", response_model=list[SceneOut])
def reorder_scenes(cid: int, payload: ScenesReorder, db: Session = Depends(get_db)):
    """장면 순서 bulk 변경 — 회차 reorder와 동일한 원자성 규칙 적용.

    소속이 다른 장면이 섞이거나 중복 id가 있으면 422(부분 적용 없음).
    """
    _get_chapter_or_404(cid, db)
    ids = [item.id for item in payload.items]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="중복된 scene id가 있습니다")
    rows = {s.id: s for s in db.scalars(
        select(Scene).where(Scene.id.in_(ids))).all()}
    if len(rows) != len(ids):
        raise HTTPException(status_code=422, detail="존재하지 않거나 소속이 다른 scene이 있습니다")
    for item in payload.items:
        if item.sort_order is not None:
            rows[item.id].sort_order = item.sort_order
    db.commit()
    rows_out = db.scalars(
        select(Scene).where(Scene.chapter_id == cid).order_by(Scene.sort_order, Scene.id)
    ).all()
    return list(rows_out)


@router.put("/chapters/{cid}/content_from_scenes", response_model=ChapterDetail)
def merge_scenes_to_content(cid: int, payload: SceneMergePut, db: Session = Depends(get_db)):
    """장면 → 회차 본문 조립 (고도화 G-013)."""
    _get_chapter_or_404(cid, db)
    scenes = db.scalars(
        select(Scene).where(Scene.chapter_id == cid)
        .order_by(Scene.sort_order, Scene.id)
    ).all()
    if not scenes:
        raise HTTPException(status_code=422, detail="조립할 장면이 없습니다")
    merged = "\n\n".join(
        (s.content_md or "").strip() for s in scenes if (s.content_md or "").strip())
    if not merged:
        raise HTTPException(status_code=422, detail="조립할 장면 본문이 없습니다")
    try:
        chapter = manuscripts.replace_manuscript(
            db, cid, merged, payload.expected_revision, reason="scene_merge"
        )
        db.commit()
        db.refresh(chapter)
        return chapter
    except manuscripts.RevisionConflict as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.detail()) from exc
