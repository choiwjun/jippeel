"""Atomic chapter manuscript replacement service."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import desc, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Chapter, ChapterSnapshot
from app.services.wordcount import count_novelpia_chars

CONFLICT_MESSAGE = "원고가 다른 곳에서 먼저 저장되었습니다. 최신 원고를 확인한 뒤 다시 시도하세요."


@dataclass(slots=True)
class RevisionConflict(Exception):
    """Raised when a manuscript write uses a stale expected revision."""

    current_revision: int

    def detail(self) -> dict[str, int | str]:
        return {
            "code": "revision_conflict",
            "message": CONFLICT_MESSAGE,
            "current_revision": self.current_revision,
        }


class ChapterNotFound(Exception):
    """Raised when the target chapter does not exist."""


def replace_manuscript(
    db: Session,
    chapter_id: int,
    content_md: str,
    expected_revision: int,
    reason: str,
) -> Chapter:
    """Replace a chapter manuscript with optimistic revision protection.

    The caller owns commit/rollback. Successful content changes create a snapshot of
    the pre-change manuscript in the same transaction. Stale writes raise
    ``RevisionConflict`` without mutating the current transaction.
    """
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise ChapterNotFound()

    current_revision = int(chapter.revision or 0)
    if current_revision != expected_revision:
        raise RevisionConflict(current_revision=current_revision)

    current_content = chapter.content_md or ""
    if current_content == content_md:
        noop_stmt = (
            update(Chapter)
            .where(
                Chapter.id == chapter_id,
                Chapter.revision == expected_revision,
                Chapter.content_md == content_md,
            )
            .values(revision=expected_revision)
        )
        result = db.execute(noop_stmt)
        if result.rowcount != 1:
            latest = db.get(Chapter, chapter_id)
            raise RevisionConflict(current_revision=int(latest.revision if latest else current_revision))
        db.flush()
        db.refresh(chapter)
        return chapter

    stmt = (
        update(Chapter)
        .where(Chapter.id == chapter_id, Chapter.revision == expected_revision)
        .values(
            content_md=content_md,
            revision=expected_revision + 1,
            word_count_cache=count_novelpia_chars(content_md),
        )
    )
    result = db.execute(stmt)
    if result.rowcount != 1:
        latest = db.get(Chapter, chapter_id)
        raise RevisionConflict(current_revision=int(latest.revision if latest else current_revision))

    db.add(
        ChapterSnapshot(
            chapter_id=chapter_id,
            revision=expected_revision,
            content_md=current_content,
            reason=reason,
        )
    )
    try:
        db.flush()
    except IntegrityError as exc:
        text = str(exc.orig if getattr(exc, "orig", None) is not None else exc)
        if "chapter_snapshots" in text and "revision" in text:
            raise RevisionConflict(current_revision=expected_revision + 1) from exc
        raise
    db.refresh(chapter)
    return chapter


def list_snapshots(db: Session, chapter_id: int) -> list[ChapterSnapshot]:
    return list(
        db.scalars(
            select(ChapterSnapshot)
            .where(ChapterSnapshot.chapter_id == chapter_id)
            .order_by(desc(ChapterSnapshot.created_at), desc(ChapterSnapshot.id))
        ).all()
    )
