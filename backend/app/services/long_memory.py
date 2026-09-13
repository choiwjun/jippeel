"""Provenance-aware long-memory selection for chapter context."""
from __future__ import annotations

from hashlib import sha256
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chapter, MemoryEntry

MEMORY_KINDS = ("summary", "beat", "decision", "fact", "timeline", "relationship_note")
MEMORY_VISIBILITIES = ("draft", "approved", "retired")
_ALLOWED_VISIBILITY_TRANSITIONS = {
    ("draft", "approved"),
    ("draft", "retired"),
    ("approved", "retired"),
}


def content_sha256(text: str | None) -> str:
    return sha256((text or "").encode("utf-8")).hexdigest()


def _safe_sort_order(value: float | int | None, *, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def create_memory_entry(
    db: Session,
    *,
    project_id: int,
    chapter_id: int | None,
    source_revision: int | None,
    source_text: str | None,
    kind: str,
    body: str,
    visibility: str = "draft",
    effective_from_sort_order: float | None = None,
    effective_to_sort_order: float | None = None,
    provenance: dict | None = None,
) -> MemoryEntry:
    if kind not in MEMORY_KINDS:
        raise ValueError(f"unsupported memory kind: {kind}")
    if visibility not in MEMORY_VISIBILITIES:
        raise ValueError(f"unsupported memory visibility: {visibility}")
    if not body.strip():
        raise ValueError("memory body must not be empty")
    chapter = db.get(Chapter, chapter_id) if chapter_id is not None else None
    if chapter_id is not None and chapter is None:
        raise ValueError("source chapter not found")
    if chapter is not None and chapter.project_id != project_id:
        raise ValueError("source chapter belongs to another project")
    if source_revision is not None and chapter is None:
        raise ValueError("source_revision requires source chapter")
    for label, value in (
        ("effective_from_sort_order", effective_from_sort_order),
        ("effective_to_sort_order", effective_to_sort_order),
    ):
        if value is None:
            continue
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be a number") from exc
        if not math.isfinite(numeric_value):
            raise ValueError(f"{label} must be finite")
    if (effective_from_sort_order is not None and effective_to_sort_order is not None
            and effective_from_sort_order > effective_to_sort_order):
        raise ValueError("memory effective range is reversed")
    entry = MemoryEntry(
        project_id=project_id,
        chapter_id=chapter_id,
        source_revision=source_revision,
        source_sha256=content_sha256(source_text),
        kind=kind,
        body=body,
        visibility=visibility,
        effective_from_sort_order=effective_from_sort_order,
        effective_to_sort_order=effective_to_sort_order,
        provenance_json=dict(provenance or {}),
    )
    db.add(entry)
    db.flush()
    return entry


def validate_visibility_transition(current: str, requested: str) -> None:
    """Reject reactivation so provenance remains append-only and auditable."""
    if current == requested:
        return
    if (current, requested) not in _ALLOWED_VISIBILITY_TRANSITIONS:
        raise ValueError(f"invalid memory visibility transition: {current} -> {requested}")


def is_stale(entry: MemoryEntry, source_chapter: Chapter | None) -> bool:
    if entry.chapter_id is None:
        return False
    if source_chapter is None or source_chapter.project_id != entry.project_id:
        return True
    if entry.source_revision is not None and (source_chapter.revision or 0) != entry.source_revision:
        return True
    return entry.source_sha256 != content_sha256(source_chapter.content_md)


def select_context_memory(
    db: Session, project_id: int, target_chapter_id: int, include_draft: bool = False
) -> list[MemoryEntry]:
    target = db.get(Chapter, target_chapter_id)
    if target is None:
        raise ValueError("target chapter not found")
    if target.project_id != project_id:
        raise ValueError("target chapter belongs to another project")
    allowed = ("approved", "draft") if include_draft else ("approved",)
    rows = db.scalars(
        select(MemoryEntry)
        .where(MemoryEntry.project_id == project_id, MemoryEntry.visibility.in_(allowed))
        .order_by(MemoryEntry.kind, MemoryEntry.id)
    ).all()
    selected: list[tuple[tuple, MemoryEntry]] = []
    target_position = _safe_sort_order(target.sort_order)
    for entry in rows:
        source = db.get(Chapter, entry.chapter_id) if entry.chapter_id is not None else None
        if source is not None and _safe_sort_order(source.sort_order) > target_position:
            continue
        if is_stale(entry, source):
            continue
        if (entry.effective_from_sort_order is not None
                and target_position < entry.effective_from_sort_order):
            continue
        if (entry.effective_to_sort_order is not None
                and target_position > entry.effective_to_sort_order):
            continue
        source_position = (
            _safe_sort_order(source.sort_order, default=-math.inf)
            if source is not None
            else -math.inf
        )
        selected.append(((entry.kind, source_position, entry.id), entry))
    selected.sort(key=lambda item: item[0])
    return [entry for _key, entry in selected]


def format_context_memory(entries: list[MemoryEntry]) -> str:
    if not entries:
        return ""
    lines = ["[장편 기억 — 컨텍스트에 포함된 provenance 기억]"]
    lines.extend(f"- ({entry.kind}) [{entry.visibility}] {entry.body}" for entry in entries)
    return "\n".join(lines)
