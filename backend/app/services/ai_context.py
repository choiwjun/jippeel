"""Shared AI context ownership and deterministic prompt assembly.

This module validates request identity before provider work. Routers should adapt
request schemas into ``ContextBundleRequest`` and then pass the immutable bundle
through LLM calls instead of rebuilding context after awaits.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chapter, Character, Foreshadow, LoreEntry, Project, Relationship, Scene, VolumeNote
from app.schemas import CanonCheckRequest, EpisodeBrief, GenerateRequest
from app.services import injection
from app.services.long_memory import format_context_memory, select_context_memory
from app.services.manuscripts import RevisionConflict

ContextTarget = Literal["generate", "canon"]
EpisodePurpose = Literal["serial", "volume_end", "series_finale"]


@dataclass(frozen=True)
class ContextBundleRequest:
    target: ContextTarget
    project_id: int | None
    chapter_id: int | None
    include_chapter_content: bool
    expected_revision: int | None
    scene_id: int | None
    character_ids: list[int]
    lore_ids: list[int]
    auto_lore: bool
    auto_lore_limit: int
    auto_lore_semantic: bool
    previous_chapter: bool
    auto_outline: bool
    auto_foreshadow: bool
    auto_foreshadow_limit: int
    style_profile: bool
    brief: EpisodeBrief | None
    prompt_text: str | None
    episode_purpose: EpisodePurpose
    approved_foreshadow_ids: list[int]
    include_relationships: bool
    include_memory: bool = True
    include_draft_memory: bool = False


@dataclass(frozen=True)
class ContextBundle:
    project_id: int | None
    chapter_id: int | None
    chapter_revision: int | None
    episode_purpose: EpisodePurpose
    blocks: list[str]
    style_profile_text: str | None
    metadata: dict
    source_text: str


PREVIOUS_GENERATE_TAIL_CHARS = 2_000
PREVIOUS_CANON_TAIL_CHARS = 1_000
VOLUME_FIELD_CHARS = 400
NEXT_CHAPTER_MEMO_CHARS = 600
FORESHADOW_CONTENT_CHARS = 400

def _revision_conflict(current_revision: int) -> HTTPException:
    return HTTPException(status_code=409, detail=RevisionConflict(current_revision).detail())


def _dedupe(ids: list[int]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _fail_mismatch(label: str) -> None:
    raise HTTPException(status_code=422, detail=f"{label} belongs to another project")


def _resolve_project(existing: int | None, candidate: int | None, label: str) -> int | None:
    if candidate is None:
        return existing
    if existing is not None and existing != candidate:
        _fail_mismatch(label)
    return candidate


def _chapter_position(chapter: Chapter | None) -> tuple[float, int] | None:
    if chapter is None:
        return None
    return (chapter.sort_order, chapter.id)


def _is_future_reference(current: Chapter | None, referenced: Chapter | None) -> bool:
    if current is None or referenced is None:
        return False
    return _chapter_position(referenced) > _chapter_position(current)


def _load_project(db: Session, project_id: int | None) -> Project | None:
    if project_id is None:
        return None
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _load_chapter(db: Session, chapter_id: int | None) -> Chapter | None:
    if chapter_id is None:
        return None
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="chapter not found")
    return chapter


def _load_scene(db: Session, scene_id: int | None) -> tuple[Scene | None, Chapter | None]:
    if scene_id is None:
        return None, None
    scene = db.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="scene not found")
    chapter = db.get(Chapter, scene.chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="scene chapter not found")
    return scene, chapter


def request_from_generate(payload: GenerateRequest) -> ContextBundleRequest:
    ctx = payload.context
    return ContextBundleRequest(
        target="generate",
        project_id=ctx.project_id,
        chapter_id=ctx.chapter_id,
        include_chapter_content=ctx.include_chapter_content,
        expected_revision=ctx.expected_revision,
        scene_id=ctx.scene_id,
        character_ids=list(ctx.character_ids or []),
        lore_ids=list(ctx.lore_ids or []),
        auto_lore=ctx.auto_lore,
        auto_lore_limit=ctx.auto_lore_limit,
        auto_lore_semantic=ctx.auto_lore_semantic,
        previous_chapter=ctx.previous_chapter,
        auto_outline=ctx.auto_outline,
        auto_foreshadow=ctx.auto_foreshadow,
        auto_foreshadow_limit=ctx.auto_foreshadow_limit,
        style_profile=ctx.style_profile,
        brief=ctx.brief,
        prompt_text=payload.prompt_override or "",
        episode_purpose=ctx.episode_purpose,
        approved_foreshadow_ids=list(ctx.approved_foreshadow_ids or []),
        include_relationships=ctx.include_relationships,
        include_memory=ctx.include_memory,
        include_draft_memory=ctx.include_draft_memory,
    )


def request_from_canon(payload: CanonCheckRequest, chapter: Chapter) -> ContextBundleRequest:
    return ContextBundleRequest(
        target="canon",
        project_id=chapter.project_id,
        chapter_id=chapter.id,
        include_chapter_content=True,
        expected_revision=payload.expected_revision,
        scene_id=None,
        character_ids=[],
        lore_ids=[],
        auto_lore=False,
        auto_lore_limit=0,
        auto_lore_semantic=False,
        previous_chapter=True,
        auto_outline=False,
        auto_foreshadow=True,
        auto_foreshadow_limit=50,
        style_profile=False,
        brief=None,
        prompt_text=None,
        episode_purpose=payload.episode_purpose,
        approved_foreshadow_ids=list(payload.approved_foreshadow_ids or []),
        include_relationships=payload.include_relationships,
    )


def purpose_directive(purpose: EpisodePurpose) -> str:
    if purpose == "volume_end":
        return (
            "[권말 목적]\n"
            "- 이 화는 권의 감정선·사건선을 닫는 회차다.\n"
            "- 다음 권 질문은 작가가 준 경우에만 남긴다.\n"
            "- 결말 의도가 있으면 억지 cliffhanger보다 closure를 우선한다."
        )
    if purpose == "series_finale":
        return (
            "[최종화 목적]\n"
            "- 이 화는 시리즈 핵심 갈등과 감정선을 닫는 회차다.\n"
            "- 작가가 명시하지 않은 새 sequel hook을 만들지 않는다.\n"
            "- 해결된 결말을 약점으로 보지 않는다. 완결용 별도 점수는 만들지 않는다."
        )
    return (
        "[연재화 목적]\n"
        "- 이 화는 다음 회차로 이어지는 연재화다.\n"
        "- next_hook이 있으면 그 방향으로 끝낸다.\n"
        "- 단, 모든 갈등을 일부러 미완으로 남기라는 뜻은 아니다."
    )


def _format_brief_block(brief: EpisodeBrief) -> str:
    lines = ["[이번 화 브리프 — 생성 계약]"]
    lines.append(f"감정 목표: {brief.emotion_goal}")
    lines.append("핵심 사건:")
    lines.extend(f"- {event}" for event in brief.core_events)
    lines.append("인물 선택:")
    lines.extend(f"- {choice}" for choice in brief.character_choices)
    lines.append(f"대가(치르는 것): {brief.cost}")
    lines.append("금지사항:")
    lines.extend(f"- {item}" for item in brief.prohibitions)
    if brief.next_hook:
        lines.append(f"다음 화 훅: {brief.next_hook}")
    if brief.ending_intent:
        lines.append(f"결말 의도: {brief.ending_intent}")
    if brief.scene_type:
        lines.append(f"장면 유형: {brief.scene_type}")
    if brief.target_chars_novelpia is not None:
        lines.append(f"목표 글자 수(노벨피아): {brief.target_chars_novelpia}")
    lines.append("→ 위 브리프에 없는 독립 사건을 새로 만들지 마라.")
    return "\n".join(lines)


def _ordered_characters(db: Session, ids: list[int], project_id: int | None) -> tuple[list[Character], int | None]:
    ordered_ids = _dedupe(ids)
    if not ordered_ids:
        return [], project_id
    rows = db.scalars(select(Character).where(Character.id.in_(ordered_ids))).all()
    by_id = {row.id: row for row in rows}
    missing = [item for item in ordered_ids if item not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail="character not found")
    ordered = [by_id[item] for item in ordered_ids]
    resolved = project_id
    for row in ordered:
        resolved = _resolve_project(resolved, row.project_id, "character")
    return ordered, resolved


def _ordered_lore(db: Session, ids: list[int], project_id: int | None) -> tuple[list[LoreEntry], int | None]:
    ordered_ids = _dedupe(ids)
    if not ordered_ids:
        return [], project_id
    rows = db.scalars(select(LoreEntry).where(LoreEntry.id.in_(ordered_ids))).all()
    by_id = {row.id: row for row in rows}
    missing = [item for item in ordered_ids if item not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail="lore not found")
    ordered = [by_id[item] for item in ordered_ids]
    resolved = project_id
    for row in ordered:
        resolved = _resolve_project(resolved, row.project_id, "lore")
    return ordered, resolved


def _ordered_foreshadows(
    db: Session,
    ids: list[int],
    project_id: int | None,
) -> tuple[list[Foreshadow], int | None]:
    ordered_ids = _dedupe(ids)
    if not ordered_ids:
        return [], project_id
    rows = db.scalars(select(Foreshadow).where(Foreshadow.id.in_(ordered_ids))).all()
    by_id = {row.id: row for row in rows}
    missing = [item for item in ordered_ids if item not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail="foreshadow not found")
    ordered = [by_id[item] for item in ordered_ids]
    resolved = project_id
    for row in ordered:
        resolved = _resolve_project(resolved, row.project_id, "foreshadow")
    return ordered, resolved


def _validate_foreshadow_references(
    db: Session,
    rows: list[Foreshadow],
    project_id: int | None,
    current_chapter: Chapter | None,
) -> list[int]:
    future_ids: list[int] = []
    for row in rows:
        for attr in ("planted_chapter_id", "resolved_chapter_id"):
            ref_id = getattr(row, attr, None)
            if ref_id is None:
                continue
            ref = db.get(Chapter, ref_id)
            if ref is None:
                raise HTTPException(status_code=404, detail="foreshadow referenced chapter not found")
            if ref.project_id != row.project_id:
                raise HTTPException(status_code=422, detail="foreshadow referenced chapter belongs to another project")
            if project_id is not None and ref.project_id != project_id:
                raise HTTPException(status_code=422, detail="foreshadow referenced chapter belongs to another project")
            if _is_future_reference(current_chapter, ref) and row.id not in future_ids:
                future_ids.append(row.id)
    return future_ids


def _foreshadow_position_key(db: Session, row: Foreshadow) -> tuple[float, int, int]:
    ref = db.get(Chapter, row.planted_chapter_id) if row.planted_chapter_id else None
    if ref is None and row.resolved_chapter_id:
        ref = db.get(Chapter, row.resolved_chapter_id)
    if ref is None:
        return (float("inf"), row.id, row.id)
    return (ref.sort_order, ref.id, row.id)


def _future_reference_attrs(db: Session, row: Foreshadow, current_chapter: Chapter | None) -> set[str]:
    attrs: set[str] = set()
    if current_chapter is None:
        return attrs
    for attr, label in (("planted_chapter_id", "planted"), ("resolved_chapter_id", "resolved")):
        ref_id = getattr(row, attr, None)
        if ref_id is None:
            continue
        ref = db.get(Chapter, ref_id)
        if ref is not None and _is_future_reference(current_chapter, ref):
            attrs.add(label)
    return attrs


def _chapter_ref_label(db: Session, chapter_id: int | None) -> str:
    if chapter_id is None:
        return "unknown/current record"
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        return "unknown/current record"
    return f"{chapter.title}(현재 기록)"


def _format_foreshadow_block(db: Session, row: Foreshadow, approved: bool, future_attrs: set[str]) -> str:
    content = (row.content or "").strip()
    future_planted = "planted" in future_attrs
    future_resolved = "resolved" in future_attrs
    if approved:
        block = f"[이번 요청에서 회수/공개 허용된 복선: {row.title}]"
    elif future_planted:
        block = f"[미래 계획 복선: {row.title} — 현재 사실 아님]"
    elif row.audience_knows:
        block = f"[독자가 이미 알게 된 복선 정보: {row.title}]"
    else:
        block = f"[미회수 복선: {row.title}]"
    details = [f"상태: {row.status}. 독자 인지: {str(bool(row.audience_knows)).lower()}. 기록: 현재 기록."]
    if not future_planted:
        details.append(f"설치 회차: {_chapter_ref_label(db, row.planted_chapter_id)}.")
    if content:
        details.append(content[:FORESHADOW_CONTENT_CHARS])
    if approved:
        details.append("→ 이번 원고에서 자연스럽게 공개하거나 회수할 수 있다. 단, 원고 밖 상태값은 자동 변경하지 마라.")
        if future_planted:
            details.append("→ 이 승인된 미래 설치 계획은 작가 허용 범위에서 사용할 수 있지만, 기존 현재 사실로 단정하지 마라.")
    elif future_planted:
        details.append("→ 참조 설치 회차가 현재 회차보다 뒤에 있다. 이 정보는 작가 계획일 수 있으나 현재 인물 지식·세계 사실로 단정하지 마라.")
    elif row.audience_knows:
        details.append("→ 이미 공개된 정보는 현재 사실로 참고할 수 있다. 새로운 회수·반전은 작가 승인 없이 만들지 마라.")
    else:
        details.append("→ 이 복선은 현재 기록이다. 작가 승인 없이 결론·정체·회수를 공개하지 마라. 결론을 미리 풀지 마라.")
    if future_resolved and not future_planted:
        details.append("→ 미래 회수 계획은 현재 사실이나 현재 인물 지식으로 단정하지 마라.")
    return block + "\n" + "\n".join(details)


def _canon_foreshadow_line(db: Session, row: Foreshadow, future_attrs: set[str]) -> str:
    content = (row.content or "").strip()[:FORESHADOW_CONTENT_CHARS]
    line = f"- {row.title}"
    if content:
        line += f": {content}"
    line += f" (설치 회차: {_chapter_ref_label(db, row.planted_chapter_id)})"
    if "resolved" in future_attrs and "planted" not in future_attrs:
        line += "\n  → 미래 회수 계획은 현재 사실이나 현재 인물 지식으로 단정하지 마라."
    return line


def _relationship_text(rel: Relationship, from_ch: Character, to_ch: Character) -> str:
    label = (rel.label or "관계").strip()
    note = (rel.note or "").strip()
    line = f"- {from_ch.name} ↔ {to_ch.name}: {label} 관계."
    if note:
        line += f" {note}"
    return line


def _generation_relationships(
    db: Session,
    selected: list[Character],
    project_id: int | None,
) -> tuple[list[str], list[int]]:
    if len(selected) < 2:
        return [], []
    selected_ids = {row.id for row in selected}
    rows = db.scalars(select(Relationship).order_by(Relationship.id.asc())).all()
    lines: list[str] = []
    rel_ids: list[int] = []
    for rel in rows:
        if rel.from_character_id not in selected_ids or rel.to_character_id not in selected_ids:
            continue
        from_ch = db.get(Character, rel.from_character_id)
        to_ch = db.get(Character, rel.to_character_id)
        if from_ch is None or to_ch is None:
            raise HTTPException(status_code=422, detail="relationship endpoint missing")
        if project_id is not None and (from_ch.project_id != project_id or to_ch.project_id != project_id):
            raise HTTPException(status_code=422, detail="relationship endpoint belongs to another project")
        lines.append(_relationship_text(rel, from_ch, to_ch))
        rel_ids.append(rel.id)
    return lines, rel_ids


def _canon_relationships(db: Session, project_id: int | None) -> tuple[list[str], list[int]]:
    if project_id is None:
        return [], []
    rows = db.scalars(select(Relationship).order_by(Relationship.id.asc())).all()
    lines: list[str] = []
    rel_ids: list[int] = []
    for rel in rows:
        from_ch = db.get(Character, rel.from_character_id)
        to_ch = db.get(Character, rel.to_character_id)
        if from_ch is None or to_ch is None:
            if (from_ch is not None and from_ch.project_id == project_id) or (to_ch is not None and to_ch.project_id == project_id):
                raise HTTPException(status_code=422, detail="relationship endpoint missing")
            continue
        from_same = from_ch.project_id == project_id
        to_same = to_ch.project_id == project_id
        if from_same != to_same:
            raise HTTPException(status_code=422, detail="relationship endpoint belongs to another project")
        if not from_same:
            continue
        lines.append(_relationship_text(rel, from_ch, to_ch))
        rel_ids.append(rel.id)
    return lines, rel_ids


def build_context_bundle(db: Session, request: ContextBundleRequest) -> ContextBundle:
    if request.expected_revision is not None and request.chapter_id is None:
        raise HTTPException(status_code=422, detail="expected_revision requires chapter_id")

    chapter = _load_chapter(db, request.chapter_id)
    scene, scene_chapter = _load_scene(db, request.scene_id)
    if chapter is not None and scene_chapter is not None and scene_chapter.id != chapter.id:
        raise HTTPException(status_code=422, detail="scene belongs to another chapter")

    project_id = request.project_id
    if chapter is not None:
        project_id = _resolve_project(project_id, chapter.project_id, "chapter")
    if scene_chapter is not None:
        project_id = _resolve_project(project_id, scene_chapter.project_id, "scene")

    selected_chars, project_id = _ordered_characters(db, request.character_ids, project_id)
    selected_lore, project_id = _ordered_lore(db, request.lore_ids, project_id)
    approved_rows, project_id = _ordered_foreshadows(db, request.approved_foreshadow_ids, project_id)

    project = _load_project(db, project_id)

    if chapter is not None and request.expected_revision is not None and chapter.revision != request.expected_revision:
        raise _revision_conflict(chapter.revision)

    blocks: list[str] = []
    source_parts: list[str] = []
    injected_lore: list[dict] = []
    included_foreshadows: list[dict] = []
    outline_info: dict = {}
    unknown_labels: list[str] = []
    included_memory_entries = []

    if request.brief is not None:
        blocks.append(_format_brief_block(request.brief))

    if request.target == "canon" and chapter is not None:
        blocks.append(f"[검수 대상 회차: {chapter.title}]\n{chapter.content_md}")
        source_parts.append(chapter.content_md or "")
    else:
        if scene is not None:
            if request.include_chapter_content:
                blocks.append(f"[현재 장면: {scene.title or '무제'} — 이 장면 안에서만 집필]\n{scene.content_md}")
            source_parts.append(scene.content_md or "")
        if chapter is not None:
            if request.include_chapter_content:
                blocks.append(f"[현재 회차: {chapter.title}]\n{chapter.content_md}")
            source_parts.append(chapter.content_md or "")

    if chapter is not None:
        chapter_memo = (chapter.memo or "").strip()
        if chapter_memo and request.auto_lore:
            source_parts.append(chapter_memo)
        if chapter_memo and request.auto_outline:
            blocks.append(f"[이번 회차 목표(목차) — 이 화에서 반드시 다뤄야 할 내용]\n{chapter_memo}")
            outline_info["current"] = True
        if request.auto_outline and chapter.volume is not None:
            vnote = db.scalars(
                select(VolumeNote).where(
                    VolumeNote.project_id == chapter.project_id,
                    VolumeNote.volume == chapter.volume,
                )
            ).first()
            if vnote is not None:
                parts = [f"[{chapter.volume}권 개요 — 권 전체 방향, 이 화가 어긋나지 않게]"]
                for field in ("overview", "emotion_curve", "climax_note"):
                    value = getattr(vnote, field, None)
                    if value and value.strip():
                        parts.append(value.strip()[:VOLUME_FIELD_CHARS])
                blocks.append("\n".join(parts))
                outline_info["volume_note"] = vnote.volume
        if request.previous_chapter:
            prev = db.scalars(
                select(Chapter).where(
                    Chapter.project_id == chapter.project_id,
                    Chapter.sort_order < chapter.sort_order,
                ).order_by(Chapter.sort_order.desc(), Chapter.id.desc())
            ).first()
            if prev and (prev.content_md or "").strip():
                cap = PREVIOUS_CANON_TAIL_CHARS if request.target == "canon" else PREVIOUS_GENERATE_TAIL_CHARS
                suffix = " — 시간축·위치 연속성 기준" if request.target == "canon" else ""
                blocks.append(f"[직전 회차: {prev.title} 끝부분{suffix}]\n…{prev.content_md[-cap:]}")
        if request.auto_outline:
            nxt = db.scalars(
                select(Chapter).where(
                    Chapter.project_id == chapter.project_id,
                    Chapter.sort_order > chapter.sort_order,
                ).order_by(Chapter.sort_order.asc(), Chapter.id.asc())
            ).first()
            if nxt is not None:
                direction = (nxt.memo or "").strip()
                block = f"[다음 회차 예고: {nxt.title}]"
                if direction:
                    block += f"\n{direction[:NEXT_CHAPTER_MEMO_CHARS]}"
                blocks.append(block)
                outline_info["next_chapter_id"] = nxt.id
                outline_info["next_title"] = nxt.title

    if request.target == "canon" and project_id is not None:
        canon_chars = db.scalars(
            select(Character).where(Character.project_id == project_id).order_by(Character.id.asc())
        ).all()
        canon_lore = db.scalars(
            select(LoreEntry).where(LoreEntry.project_id == project_id).order_by(LoreEntry.id.asc())
        ).all()
        if canon_chars:
            parts = []
            for ch in canon_chars:
                fields = [f"이름: {ch.name}"]
                for field in ("role", "appearance", "personality", "speech_style", "background"):
                    value = getattr(ch, field, None)
                    if value:
                        fields.append(f"{field}: {value}")
                parts.append("\n".join(fields))
            blocks.append("[캐릭터 설정 — 본문의 인물 묘사·말투가 이와 모순되면 지적]\n" + "\n---\n".join(parts))
        if canon_lore:
            parts = [f"{entry.title}: {entry.content or ''}" for entry in canon_lore if entry.content]
            if parts:
                blocks.append("[세계관 설정 — 본문이 이와 모순되면 지적]\n" + "\n".join(parts))
        selected_chars_for_metadata = canon_chars
        selected_lore_for_metadata = canon_lore
    else:
        for ch in selected_chars:
            parts = [f"[캐릭터: {ch.name}]"]
            for field in ("role", "appearance", "personality", "speech_style", "background"):
                value = getattr(ch, field, None)
                if value:
                    parts.append(f"{field}: {value}")
            blocks.append("\n".join(parts))
        for entry in selected_lore:
            blocks.append(f"[세계관: {entry.title}]\n{entry.content or ''}")
        selected_chars_for_metadata = selected_chars
        selected_lore_for_metadata = selected_lore

    if request.include_memory and project_id is not None and chapter is not None:
        included_memory_entries = select_context_memory(
            db, project_id=project_id, target_chapter_id=chapter.id,
            include_draft=request.include_draft_memory,
        )
        memory_block = format_context_memory(included_memory_entries)
        if memory_block:
            blocks.append(memory_block)

    if request.auto_lore and project_id is not None:
        if request.prompt_text:
            source_parts.append(request.prompt_text)
        selector = injection.select_lore_for_text_hybrid if request.auto_lore_semantic else injection.select_lore_for_text
        selected = selector(db, project_id, "\n".join(source_parts), limit=request.auto_lore_limit)
        explicit_ids = {entry.id for entry in selected_lore}
        for entry in selected:
            if entry.id in explicit_ids:
                continue
            blocks.append(f"[세계관(자동): {entry.title}]\n{entry.content or ''}")
            injected_lore.append({"id": entry.id, "title": entry.title})

    included_foreshadow_rows: list[Foreshadow] = []
    if request.target == "canon" and project_id is not None:
        included_foreshadow_rows = db.scalars(
            select(Foreshadow).where(
                Foreshadow.project_id == project_id,
                Foreshadow.status.in_(("설치", "보류")),
            )
        ).all()
        included_foreshadow_rows.sort(key=lambda row: _foreshadow_position_key(db, row))
    elif request.auto_foreshadow and project_id is not None:
        rows = db.scalars(
            select(Foreshadow).where(
                Foreshadow.project_id == project_id,
                Foreshadow.status == "설치",
            )
        ).all()
        rows.sort(key=lambda row: _foreshadow_position_key(db, row))
        included_foreshadow_rows = rows[:request.auto_foreshadow_limit]

    validation_by_id = {row.id: row for row in included_foreshadow_rows}
    for row in approved_rows:
        validation_by_id.setdefault(row.id, row)
    validation_foreshadows = list(validation_by_id.values())
    future_ids = _validate_foreshadow_references(db, validation_foreshadows, project_id, chapter)
    if validation_foreshadows:
        unknown_labels.append("foreshadow_history_is_current_record_only")
    approved_ids = [row.id for row in approved_rows]

    approved_set = set(approved_ids)
    if request.target == "canon" and validation_foreshadows:
        approved_for_render = [row for row in approved_rows]
        unapproved_rows = [row for row in included_foreshadow_rows if row.id not in approved_set]
        if approved_for_render:
            parts = [
                _format_foreshadow_block(
                    db, row, approved=True, future_attrs=_future_reference_attrs(db, row, chapter)
                )
                for row in approved_for_render
            ]
            blocks.append("\n\n".join(parts))

        attrs_by_id = {row.id: _future_reference_attrs(db, row, chapter) for row in unapproved_rows}
        future_plants = [row for row in unapproved_rows if "planted" in attrs_by_id[row.id]]
        current_rows = [row for row in unapproved_rows if "planted" not in attrs_by_id[row.id]]
        if future_plants:
            parts = [
                _format_foreshadow_block(
                    db, row, approved=False, future_attrs=attrs_by_id[row.id]
                )
                for row in future_plants
            ]
            blocks.append("\n\n".join(parts))

        unknown = [row for row in current_rows if not row.audience_knows]
        known = [row for row in current_rows if row.audience_knows]
        if unknown:
            parts = [_canon_foreshadow_line(db, row, attrs_by_id[row.id]) for row in unknown]
            blocks.append(
                "[미회수 복선 — 현재 기록. 작가 승인 없는 새 회수·정체 공개는 지적]\n"
                + "\n".join(parts)
            )
        if known:
            parts = [_canon_foreshadow_line(db, row, attrs_by_id[row.id]) for row in known]
            blocks.append(
                "[독자가 이미 알게 된 사실 — 현재 공개 정보. 처음 밝히는 것처럼 쓰면 지적(인지 중복)]\n"
                + "\n".join(parts)
            )
        rendered = approved_for_render + unapproved_rows
        included_foreshadows = [{"id": row.id, "title": row.title} for row in rendered]
    elif request.target == "generate":
        rendered_ids: set[int] = set()
        render_rows = list(approved_rows) + [row for row in included_foreshadow_rows if row.id not in approved_set]
        for row in render_rows:
            if row.id in rendered_ids:
                continue
            rendered_ids.add(row.id)
            blocks.append(
                _format_foreshadow_block(
                    db, row, approved=row.id in approved_set, future_attrs=_future_reference_attrs(db, row, chapter)
                )
            )
            included_foreshadows.append({"id": row.id, "title": row.title})

    included_relationship_ids: list[int] = []
    if request.include_relationships:
        if request.target == "canon":
            rel_lines, included_relationship_ids = _canon_relationships(db, project_id)
        else:
            rel_lines, included_relationship_ids = _generation_relationships(db, selected_chars, project_id)
        if rel_lines:
            blocks.append("[인물 관계 — 관계가 본문 행동·호칭·거리감과 모순되면 지적]\n" + "\n".join(rel_lines))

    style_profile_text: str | None = None
    if request.style_profile and project is not None and (project.style_profile or "").strip():
        style_profile_text = project.style_profile.strip()

    characters_count = 0
    lore_count = 0
    foreshadows_count = 0
    audience_known_count = 0
    if request.target == "canon":
        characters_count = len(selected_chars_for_metadata)
        lore_count = len(selected_lore_for_metadata)
        foreshadows_count = len([row for row in included_foreshadow_rows if not row.audience_knows])
        audience_known_count = len([row for row in included_foreshadow_rows if row.audience_knows])

    metadata = {
        "project_id": project_id,
        "chapter_id": chapter.id if chapter is not None else None,
        "chapter_revision": chapter.revision if chapter is not None else None,
        "include_chapter_content": request.include_chapter_content,
        "episode_purpose": request.episode_purpose,
        "included_character_ids": [row.id for row in selected_chars_for_metadata],
        "included_lore_ids": [row.id for row in selected_lore_for_metadata],
        "injected_lore": injected_lore,
        "included_relationship_ids": included_relationship_ids,
        "included_foreshadow_ids": [row["id"] for row in included_foreshadows],
        "approved_foreshadow_ids": approved_ids,
        "future_reference_foreshadow_ids": sorted(future_ids),
        "included_memory_entry_ids": [entry.id for entry in included_memory_entries],
        "include_memory": request.include_memory,
        "include_draft_memory": request.include_draft_memory,
        "outline": outline_info,
        "unknown_labels": unknown_labels,
        # Legacy canon count keys. Generation keeps them zero for JSON shape stability.
        "characters": characters_count,
        "lore": lore_count,
        "foreshadows": foreshadows_count,
        "audience_known": audience_known_count,
    }

    return ContextBundle(
        project_id=project_id,
        chapter_id=chapter.id if chapter is not None else None,
        chapter_revision=chapter.revision if chapter is not None else None,
        episode_purpose=request.episode_purpose,
        blocks=blocks,
        style_profile_text=style_profile_text,
        metadata=metadata,
        source_text="\n".join(part for part in source_parts if part),
    )
