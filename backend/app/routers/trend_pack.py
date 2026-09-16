"""작품별 trend_pack CRUD — 승인된 시장 참고자료의 명시적 저장·주입 경계."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project, ProjectTrendPack
from app.schemas import TrendPackOut, TrendPackWrite, TrendSignal

router = APIRouter()
SCHEMA_VERSION = "trend-pack-v1"


def _project_or_404(pid: int, db: Session) -> Project:
    project = db.get(Project, pid)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _signals(row: ProjectTrendPack) -> list[TrendSignal]:
    payload = row.payload_json
    if not isinstance(payload, dict) or not isinstance(payload.get("signals"), list):
        return []
    try:
        return [TrendSignal.model_validate(item) for item in payload["signals"]]
    except Exception:
        return []


def _out(row: ProjectTrendPack) -> TrendPackOut:
    return TrendPackOut(
        id=row.id,
        project_id=row.project_id,
        schema_version=row.schema_version,
        status=row.status,
        source=row.source,
        as_of=row.as_of,
        version=row.version,
        signals=_signals(row),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/projects/{pid}/trend-pack", response_model=TrendPackOut)
def get_trend_pack(pid: int, db: Session = Depends(get_db)):
    _project_or_404(pid, db)
    row = db.query(ProjectTrendPack).filter(ProjectTrendPack.project_id == pid).first()
    if row is None:
        raise HTTPException(status_code=404, detail="trend pack not found")
    return _out(row)


@router.put("/projects/{pid}/trend-pack", response_model=TrendPackOut)
def upsert_trend_pack(pid: int, payload: TrendPackWrite, db: Session = Depends(get_db)):
    _project_or_404(pid, db)
    row = db.query(ProjectTrendPack).filter(ProjectTrendPack.project_id == pid).first()
    if row is None:
        if payload.status is None or payload.source is None or payload.as_of is None or payload.signals is None:
            raise HTTPException(status_code=422, detail="new trend pack requires status, source, as_of, and signals")
        row = ProjectTrendPack(
            project_id=pid,
            schema_version=SCHEMA_VERSION,
            status=payload.status,
            source=payload.source,
            as_of=payload.as_of,
            version=1,
            payload_json={"signals": [item.model_dump() for item in payload.signals]},
        )
        db.add(row)
    else:
        if row.schema_version != SCHEMA_VERSION:
            raise HTTPException(status_code=409, detail="unsupported trend pack schema cannot be updated")
        if payload.status is not None:
            row.status = payload.status
        if payload.source is not None:
            row.source = payload.source
        if payload.as_of is not None:
            row.as_of = payload.as_of
        if payload.signals is not None:
            row.payload_json = {"signals": [item.model_dump() for item in payload.signals]}
        row.version = int(row.version or 0) + 1
    db.commit()
    db.refresh(row)
    return _out(row)


@router.delete("/projects/{pid}/trend-pack", status_code=status.HTTP_204_NO_CONTENT)
def delete_trend_pack(pid: int, db: Session = Depends(get_db)):
    _project_or_404(pid, db)
    row = db.query(ProjectTrendPack).filter(ProjectTrendPack.project_id == pid).first()
    if row is not None:
        db.delete(row)
        db.commit()
