"""장편 기억 거버넌스 API.

기억은 원고 정본이 아닌 provenance-aware 파생 데이터다. 이 라우터는
작품별 목록·수동 draft 생성·명시적 승인/폐기만 제공하며 provider를 호출하거나
원고를 자동으로 변경하지 않는다.
"""
from __future__ import annotations

import logging
import math
import sqlite3
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chapter, MemoryEntry, Project
from app.schemas import (
    MemoryEntryCreate,
    MemoryEntryOut,
    MemoryEntryUpdate,
    MemoryKind,
    MemoryVisibility,
)
from app.services.long_memory import (
    MEMORY_KINDS,
    MEMORY_VISIBILITIES,
    _safe_sort_order,
    create_memory_entry,
    is_stale,
    validate_visibility_transition,
)

router = APIRouter()
logger = logging.getLogger(__name__)
_MAX_QUERY_ROWS = 500


def _get_project_or_404(pid: int, db: Session) -> Project:
    project = db.get(Project, pid)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _get_chapter_for_project(pid: int, chapter_id: int, db: Session) -> Chapter:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="chapter not found")
    if chapter.project_id != pid:
        raise HTTPException(status_code=422, detail="chapter belongs to another project")
    return chapter


def _get_memory_or_404(pid: int, mid: int, db: Session) -> MemoryEntry:
    memory = db.get(MemoryEntry, mid)
    if memory is None:
        raise HTTPException(status_code=404, detail="memory not found")
    if memory.project_id != pid:
        raise HTTPException(status_code=422, detail="memory belongs to another project")
    return memory


def _validation_error(message: str) -> HTTPException:
    return HTTPException(status_code=422, detail=message)


def _memory_sort_key(entry: MemoryEntry, source: Chapter | None) -> tuple[str, float, int]:
    source_position = _safe_sort_order(source.sort_order, default=-math.inf) if source else -math.inf
    return entry.kind, source_position, entry.id


def _to_out(entry: MemoryEntry, source: Chapter | None) -> MemoryEntryOut:
    return MemoryEntryOut(
        id=entry.id,
        project_id=entry.project_id,
        chapter_id=entry.chapter_id,
        source_revision=entry.source_revision,
        source_sha256=entry.source_sha256,
        kind=cast(MemoryKind, entry.kind),
        body=entry.body,
        visibility=cast(MemoryVisibility, entry.visibility),
        effective_from_sort_order=entry.effective_from_sort_order,
        effective_to_sort_order=entry.effective_to_sort_order,
        provenance=dict(entry.provenance_json or {}),
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        stale=is_stale(entry, source),
        source_chapter_title=source.title if source else None,
        source_chapter_revision=source.revision if source else None,
        source_chapter_sort_order=source.sort_order if source else None,
    )


def _list_rows(
    db: Session,
    *,
    pid: int,
    kind: str | None,
    visibility: str | None,
    chapter_id: int | None,
    offset: int = 0,
) -> list[MemoryEntry]:
    statement = select(MemoryEntry).where(MemoryEntry.project_id == pid)
    if kind is not None:
        statement = statement.where(MemoryEntry.kind == kind)
    if visibility is not None:
        statement = statement.where(MemoryEntry.visibility == visibility)
    if chapter_id is not None:
        statement = statement.where(MemoryEntry.chapter_id == chapter_id)
    statement = statement.outerjoin(Chapter, MemoryEntry.chapter_id == Chapter.id)
    return list(db.scalars(
        statement.order_by(
            MemoryEntry.kind.asc(),
            Chapter.sort_order.asc().nulls_first(),
            MemoryEntry.id.asc(),
        ).offset(offset).limit(_MAX_QUERY_ROWS)
    ).all())


@router.get("/projects/{pid}/memories", response_model=list[MemoryEntryOut])
def list_memories(
    pid: int,
    kind: str | None = Query(default=None),
    visibility: str | None = Query(default=None),
    chapter_id: int | None = Query(default=None, ge=1),
    stale: bool | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    _get_project_or_404(pid, db)
    if kind is not None and kind not in MEMORY_KINDS:
        raise _validation_error("unsupported memory kind")
    if visibility is not None and visibility not in MEMORY_VISIBILITIES:
        raise _validation_error("unsupported memory visibility")
    if chapter_id is not None:
        _get_chapter_for_project(pid, chapter_id, db)

    try:
        chapters = {
            chapter.id: chapter
            for chapter in db.scalars(select(Chapter).where(Chapter.project_id == pid)).all()
        }
        items: list[MemoryEntryOut] = []
        offset = 0
        while len(items) < limit:
            rows = _list_rows(
                db,
                pid=pid,
                kind=kind,
                visibility=visibility,
                chapter_id=chapter_id,
                offset=offset,
            )
            if not rows:
                break
            rows_with_source = [
                (row, chapters.get(row.chapter_id) if row.chapter_id is not None else None)
                for row in rows
            ]
            rows_with_source.sort(key=lambda pair: _memory_sort_key(*pair))
            page_items = [_to_out(row, source) for row, source in rows_with_source]
            if stale is not None:
                page_items = [item for item in page_items if item.stale is stale]
            items.extend(page_items)
            if stale is None or len(rows) < _MAX_QUERY_ROWS:
                break
            offset += len(rows)
        return items[:limit]
    except SQLAlchemyError as exc:
        logger.exception("memory list database failure: project_id=%s", pid)
        raise HTTPException(status_code=500, detail="기억 목록을 불러오는 중 오류가 발생했습니다.") from exc


@router.post("/projects/{pid}/memories", response_model=MemoryEntryOut, status_code=status.HTTP_201_CREATED)
def create_memory(pid: int, payload: MemoryEntryCreate, db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    source = _get_chapter_for_project(pid, payload.chapter_id, db) if payload.chapter_id else None
    try:
        entry = create_memory_entry(
            db,
            project_id=pid,
            chapter_id=source.id if source else None,
            source_revision=source.revision if source else None,
            source_text=source.content_md if source else None,
            kind=payload.kind,
            body=payload.body,
            visibility="draft",
            effective_from_sort_order=payload.effective_from_sort_order,
            effective_to_sort_order=payload.effective_to_sort_order,
            provenance={"source": "manual"},
        )
        db.commit()
        db.refresh(entry)
    except ValueError as exc:
        db.rollback()
        raise _validation_error(str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        error_code = getattr(getattr(exc, "orig", None), "sqlite_errorcode", None)
        if error_code == sqlite3.SQLITE_CONSTRAINT_FOREIGNKEY or (
            error_code is not None and error_code & 0xFF == sqlite3.SQLITE_BUSY
        ):
            raise HTTPException(
                status_code=409, detail="근거 회차 또는 작품이 변경 중이거나 삭제되었습니다. 새로고침 후 다시 시도하세요."
            ) from exc
        logger.exception("memory create database failure: project_id=%s", pid)
        raise HTTPException(status_code=500, detail="기억 저장 중 오류가 발생했습니다.") from exc
    return _to_out(entry, source)


@router.patch("/projects/{pid}/memories/{mid}", response_model=MemoryEntryOut)
def update_memory(pid: int, mid: int, payload: MemoryEntryUpdate, db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    entry = _get_memory_or_404(pid, mid, db)
    changes = payload.model_dump(exclude_unset=True)
    if "visibility" in changes:
        requested = changes["visibility"]
        if requested is None:
            raise _validation_error("visibility must not be null")
        try:
            validate_visibility_transition(entry.visibility, requested)
        except ValueError as exc:
            raise _validation_error(str(exc)) from exc

    next_from = changes.get("effective_from_sort_order", entry.effective_from_sort_order)
    next_to = changes.get("effective_to_sort_order", entry.effective_to_sort_order)
    if next_from is not None and next_to is not None and next_from > next_to:
        raise _validation_error("memory effective range is reversed")
    if not changes:
        source = db.get(Chapter, entry.chapter_id) if entry.chapter_id is not None else None
        return _to_out(entry, source)

    try:
        # Compare every value used to validate the transition/range, including NULL bounds.
        result = cast(
            CursorResult,
            db.execute(
                update(MemoryEntry).where(
                    MemoryEntry.id == entry.id,
                    MemoryEntry.project_id == pid,
                    MemoryEntry.visibility == entry.visibility,
                    MemoryEntry.effective_from_sort_order == entry.effective_from_sort_order,
                    MemoryEntry.effective_to_sort_order == entry.effective_to_sort_order,
                ).values(**changes)
            ),
        )
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="기억이 다른 요청에서 변경되었습니다. 새로고침 후 다시 검토하세요.")
        db.commit()
        db.refresh(entry)
    except SQLAlchemyError as exc:
        db.rollback()
        error_code = getattr(getattr(exc, "orig", None), "sqlite_errorcode", None)
        if error_code is not None and error_code & 0xFF == sqlite3.SQLITE_BUSY:
            raise HTTPException(status_code=409, detail="기억이 변경 중입니다. 새로고침 후 다시 검토하세요.") from exc
        logger.exception(
            "memory update database failure: project_id=%s memory_id=%s", pid, mid
        )
        raise HTTPException(status_code=500, detail="기억 수정 중 오류가 발생했습니다.") from exc
    source = db.get(Chapter, entry.chapter_id) if entry.chapter_id is not None else None
    return _to_out(entry, source)
