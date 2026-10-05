"""Provenance-aware long-memory selection for chapter context."""
from __future__ import annotations

from hashlib import sha256
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chapter, MemoryEntry
from app.services.chapter_order import chapter_position

MEMORY_KINDS = (
    "summary", "beat", "decision", "fact", "timeline", "relationship_note",
    "arc_summary", "volume_memory",
)
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


def arc_source_text(entries: list[MemoryEntry], chapters: dict[int, Chapter]) -> str:
    parts = []
    for entry in entries:
        chapter = chapters.get(entry.chapter_id) if entry.chapter_id is not None else None
        title = (chapter.title or "") if chapter is not None else ""
        parts.append(f"[{title or entry.chapter_id}] {entry.body}")
    return "\n\n".join(parts)


def volume_source_text(entries: list[MemoryEntry]) -> str:
    parts = []
    for index, entry in enumerate(entries):
        end = entry.effective_from_sort_order
        label = (f"{index + 1}번째 아크 요약 (sort ≤ {end:g})" if isinstance(end, (int, float))
                 else f"{index + 1}번째 아크 요약")
        parts.append(f"[{label}] {entry.body}")
    return "\n\n".join(parts)


class MemoryFreshness:
    """One batched provenance graph per request, including retired source rows."""

    def __init__(self, entries: list[MemoryEntry], chapters: list[Chapter]):
        self.entries = {entry.id: entry for entry in entries}
        self.chapters = {chapter.id: chapter for chapter in chapters}
        self._stale: dict[int, bool] = {}
        self._last_source: dict[int, tuple | None] = {}

    def last_source_position(self, entry: MemoryEntry) -> tuple | None:
        """Canonical end of a rollup's source graph, or its direct source."""
        if entry.id in self._last_source:
            return self._last_source[entry.id]
        self._last_source[entry.id] = None
        chapter = self.chapters.get(entry.chapter_id)
        positions = [chapter_position(chapter)] if chapter is not None else []
        field = {"arc_summary": "arc_source_entry_ids",
                 "volume_memory": "volume_source_entry_ids"}.get(entry.kind)
        provenance = entry.provenance_json or {}
        if field and isinstance(provenance, dict):
            ids = provenance.get(field)
            if isinstance(ids, list):
                for sid in ids:
                    child = self.entries.get(sid) if isinstance(sid, int) else None
                    position = self.last_source_position(child) if child is not None else None
                    if position is not None:
                        positions.append(position)
        result = max(positions) if positions else None
        self._last_source[entry.id] = result
        return result

    def is_stale(self, entry: MemoryEntry) -> bool:
        if entry.id in self._stale:
            return self._stale[entry.id]
        # Mark before traversal so malformed cycles fail closed.
        self._stale[entry.id] = True
        result = self._check(entry)
        self._stale[entry.id] = result
        return result

    def _check(self, entry: MemoryEntry) -> bool:
        source = self.chapters.get(entry.chapter_id) if entry.chapter_id is not None else None
        if is_stale(entry, source):
            return True
        rollup = {"arc_summary": ("arc_source_entry_ids", "summary"),
                  "volume_memory": ("volume_source_entry_ids", "arc_summary")}.get(entry.kind)
        if rollup is None:
            return False
        provenance = entry.provenance_json or {}
        if not isinstance(provenance, dict):
            return True
        field, source_kind = rollup
        if field not in provenance:
            # Manually authored project memories have no derived source graph.
            return provenance.get("generated_by") == "summary-worker"
        ids = provenance[field]
        if not isinstance(ids, list) or not ids or any(
            not isinstance(i, int) or isinstance(i, bool) or i < 1 for i in ids
        ) or len(ids) != len(set(ids)):
            return True
        sources = []
        for sid in ids:
            child = self.entries.get(sid)
            if (child is None or child.project_id != entry.project_id or child.kind != source_kind
                    or child.visibility != "approved" or self.is_stale(child)):
                return True
            sources.append(child)
        if provenance.get("generated_by") == "summary-worker":
            text = arc_source_text(sources, self.chapters) if entry.kind == "arc_summary" else volume_source_text(sources)
            if content_sha256(text) != entry.source_sha256:
                return True
        return False


def load_memory_freshness(db: Session, project_id: int) -> MemoryFreshness:
    # populate_existing also protects the post-provider check from identity-map staleness.
    entries = list(db.scalars(select(MemoryEntry).where(MemoryEntry.project_id == project_id)
                             .execution_options(populate_existing=True)).all())
    chapters = list(db.scalars(select(Chapter).where(Chapter.project_id == project_id)
                              .execution_options(populate_existing=True)).all())
    return MemoryFreshness(entries, chapters)


def select_context_memory(
    db: Session, project_id: int, target_chapter_id: int, include_draft: bool = False
) -> list[MemoryEntry]:
    target = db.get(Chapter, target_chapter_id)
    if target is None:
        raise ValueError("target chapter not found")
    if target.project_id != project_id:
        raise ValueError("target chapter belongs to another project")
    allowed = ("approved", "draft") if include_draft else ("approved",)
    freshness = load_memory_freshness(db, project_id)
    rows = sorted((entry for entry in freshness.entries.values() if entry.visibility in allowed),
                  key=lambda entry: (entry.kind, entry.id))
    selected: list[tuple[tuple, MemoryEntry]] = []
    target_position = _safe_sort_order(target.sort_order)
    for entry in rows:
        if freshness.is_stale(entry):
            continue
        source_position = freshness.last_source_position(entry)
        if source_position is not None and source_position > chapter_position(target):
            continue
        provenance = entry.provenance_json or {}
        derived_rollup = (entry.kind in ("arc_summary", "volume_memory")
                          and isinstance(provenance, dict)
                          and provenance.get("generated_by") == "summary-worker"
                          and source_position is not None)
        # Worker rollup bounds are legacy sort labels; their actual end comes
        # from the source graph. Explicit ranges on manual memories still apply.
        if (not derived_rollup and entry.effective_from_sort_order is not None
                and target_position < entry.effective_from_sort_order):
            continue
        if (entry.effective_to_sort_order is not None
                and target_position > entry.effective_to_sort_order):
            continue
        selected.append(((entry.kind, source_position or (-math.inf, -math.inf, -1), entry.id), entry))
    selected.sort(key=lambda item: item[0])

    # 커버리지 선택 — 승인된 상위 층(arc_summary/volume_memory)이 대표하는
    # 구간의 하위 요약은 제외한다. draft 상위 층은 아직 작가 승인 전이므로
    # 하위 요약을 덮지 않는다.
    covered: set[int] = set()
    by_id = {entry.id: entry for entry in rows}
    for _key, entry in selected:
        if entry.visibility != "approved":
            continue
        prov = entry.provenance_json or {}
        if not isinstance(prov, dict):
            continue
        if entry.kind == "arc_summary":
            covered.update(
                int(i) for i in (prov.get("arc_source_entry_ids") or [])
            )
        elif entry.kind == "volume_memory":
            for arc_id in prov.get("volume_source_entry_ids") or []:
                arc_id = int(arc_id)
                covered.add(arc_id)
                arc_entry = by_id.get(arc_id)
                arc_prov = (arc_entry.provenance_json or {}) if arc_entry else {}
                covered.update(
                    int(i) for i in (arc_prov.get("arc_source_entry_ids") or [])
                )
    if covered:
        selected = [item for item in selected if item[1].id not in covered]
    return [entry for _key, entry in selected]


def format_context_memory(entries: list[MemoryEntry]) -> str:
    if not entries:
        return ""
    lines = ["[장편 기억 — 컨텍스트에 포함된 provenance 기억]"]
    lines.extend(f"- ({entry.kind}) [{entry.visibility}] {entry.body}" for entry in entries)
    return "\n".join(lines)
