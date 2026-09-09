"""캐릭터 카드 라우터 (사양 §5 M2, FR-201~205 / Sprint 2)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Character, Project, Relationship
from app.schemas import (
    CardJsonPatch,
    CharacterCreate,
    CharacterOut,
    CharacterUpdate,
    RelationshipCreate,
    RelationshipOut,
)

router = APIRouter()


def _get_project_or_404(pid: int, db: Session) -> Project:
    project = db.get(Project, pid)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _get_character_or_404(chid: int, db: Session) -> Character:
    character = db.get(Character, chid)
    if character is None:
        raise HTTPException(status_code=404, detail="character not found")
    return character


def _merge_patch(base: dict | None, patch: dict) -> dict:
    """JSON Merge Patch(RFC 7386): None은 제거, dict는 재귀 병합."""
    result = dict(base or {})
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_patch(result[key], value)
        else:
            result[key] = value
    return result


# ---------- characters CRUD ----------
@router.get("/projects/{pid}/characters", response_model=list[CharacterOut])
def list_characters(pid: int, db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    return db.scalars(
        select(Character).where(Character.project_id == pid).order_by(Character.id)
    ).all()


@router.post(
    "/projects/{pid}/characters",
    response_model=CharacterOut,
    status_code=status.HTTP_201_CREATED,
)
def create_character(pid: int, payload: CharacterCreate, db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    character = Character(project_id=pid, **payload.model_dump())
    db.add(character)
    db.commit()
    db.refresh(character)
    return character


@router.get("/characters/{chid}", response_model=CharacterOut)
def get_character(chid: int, db: Session = Depends(get_db)):
    return _get_character_or_404(chid, db)


@router.patch("/characters/{chid}", response_model=CharacterOut)
def update_character(chid: int, payload: CharacterUpdate, db: Session = Depends(get_db)):
    character = _get_character_or_404(chid, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(character, field, value)
    db.commit()
    db.refresh(character)
    return character


@router.patch("/characters/{chid}/card_json", response_model=CharacterOut)
def patch_card_json(chid: int, payload: CardJsonPatch, db: Session = Depends(get_db)):
    """card_json 부분 업데이트(병합). ST 카드 확장 필드 단일 키 수정용 (FR-204)."""
    character = _get_character_or_404(chid, db)
    character.card_json = _merge_patch(character.card_json, payload.patch)
    db.commit()
    db.refresh(character)
    return character


@router.delete("/characters/{chid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character(chid: int, db: Session = Depends(get_db)):
    character = _get_character_or_404(chid, db)
    has_relationship = db.scalar(
        select(Relationship.id).where(
            (Relationship.from_character_id == chid)
            | (Relationship.to_character_id == chid)
        ).limit(1)
    )
    if has_relationship is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="관계가 있는 캐릭터는 관계를 먼저 삭제해야 합니다",
        )
    db.delete(character)
    db.commit()


# ---------- relationships ----------
@router.post(
    "/projects/{pid}/characters/relations",
    response_model=RelationshipOut,
    status_code=status.HTTP_201_CREATED,
)
def create_relation(pid: int, payload: RelationshipCreate, db: Session = Depends(get_db)):
    """관계 링크 생성. 두 캐릭터 모두 같은 프로젝트 소속이어야 한다."""
    _get_project_or_404(pid, db)
    src = db.get(Character, payload.from_character_id)
    dst = db.get(Character, payload.to_character_id)
    if src is None or dst is None or src.project_id != pid or dst.project_id != pid:
        raise HTTPException(status_code=422, detail="characters must exist in the same project")
    relation = Relationship(**payload.model_dump())
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return relation


@router.get("/characters/{chid}/relations", response_model=list[RelationshipOut])
def list_relations(chid: int, db: Session = Depends(get_db)):
    """캐릭터가 from 또는 to로 연결된 관계 목록 (FR-205 상세 드로어용)."""
    _get_character_or_404(chid, db)
    stmt = select(Relationship).where(
        (Relationship.from_character_id == chid) | (Relationship.to_character_id == chid)
    )
    return db.scalars(stmt.order_by(Relationship.id)).all()


@router.delete("/relations/{rid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relation(rid: int, db: Session = Depends(get_db)):
    relation = db.get(Relationship, rid)
    if relation is None:
        raise HTTPException(status_code=404, detail="relation not found")
    db.delete(relation)
    db.commit()
