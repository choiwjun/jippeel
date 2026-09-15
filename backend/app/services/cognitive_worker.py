"""인지·사건 파생 worker — D02 P2.

회차 본문에서 사건(event_impacts)과 인지 상태(knowledge_states) 후보를
추출해 draft로만 append한다. provider는 주입된 callable — 테스트는 fake
provider만 사용하고, 실제 호출·비용은 승인 게이트 대상이다.

결정:
- 파생 결과는 visibility='draft'로만 생성 — 자동 승인 없음.
- 동일 (chapter_id, source_sha256, kind) 조합은 idempotency로 재사용.
- 회차 원문이 바뀌면 source_sha256이 달라져 stale로 간주한다.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from typing import Any, Callable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Chapter,
    Character,
    EventImpact,
    Foreshadow,
    KnowledgeState,
    MemoryEntry,
)

CognitiveProvider = Callable[[str, str], str]
"""provider(system_prompt, user_prompt) -> JSON string"""


def make_gpt_cognitive_provider(
    *,
    client_factory: Callable[[], Any] | None = None,
) -> CognitiveProvider:
    """고정 GPT OAuth bridge를 CognitiveProvider 동기 callable로 감싼다.

    실제 호출은 endpoint 실행 시에만 일어난다. 테스트는 client_factory로
    fake transport를 주입해 네트워크를 사용하지 않는다.
    """
    def provider(system: str, user: str) -> str:
        from app.services import gpt_oauth, llm

        resolved = gpt_oauth.get_provider()
        client = client_factory() if client_factory is not None else llm.make_client(resolved.base_url, None)
        try:
            return asyncio.run(llm.complete_chat(
                client,
                resolved.default_model,
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                reasoning_effort=resolved.reasoning_effort,
            ))
        finally:
            close = getattr(client, "close", None)
            if close is not None:
                result = close()
                if inspect.isawaitable(result):
                    asyncio.run(result)

    return provider

COGNITIVE_PROMPT_VERSION = "cognitive-v1"
MAX_SOURCE_CHARS = 60_000

_SYSTEM_PROMPT = (
    "당신은 한국 웹소설 회차를 분석해 사건·인지 상태 후보를 JSON으로 추출하는 도구입니다. "
    "본문에 실제로 있는 사실만 추출하고 창작하지 마세요. "
    "출력은 반드시 아래 스키마의 JSON 하나만 반환하세요.\n\n"
    "{\n"
    '  "events": [\n'
    "    {\n"
    '      "label": "사건 이름",\n'
    '      "character_deltas": [{"character_name": "이름", "delta": "변화", "note": "메모"}],\n'
    '      "relationship_deltas": [{"pair": ["이름A","이름B"], "from": "이전", "to": "이후", "note": "메모"}],\n'
    '      "foreshadow_deltas": [{"foreshadow_title": "제목", "진전": "진행|회수|실패"}],\n'
    '      "state_after": "사건 직후 상황 요약"\n'
    "    }\n"
    "  ],\n"
    '  "knowledge": [\n'
    "    {\n"
    '      "subject_type": "reader|character",\n'
    '      "character_name": "인물명 (subject_type=character일 때만)",\n'
    '      "target_kind": "fact|foreshadow",\n'
    '      "target_hint": "대상을 식별할 힌트 (제목 또는 본문 일부)",\n'
    '      "status": "aware|unaware|false_belief|forgotten"\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "subject_type=author는 항상 aware이므로 추출하지 마세요. "
    "events가 없으면 빈 배열, knowledge가 없으면 빈 배열을 반환하세요."
)


def _content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chapter_source_text(chapter: Chapter) -> str:
    return chapter.content_md or ""


def _build_user_prompt(chapter: Chapter, characters: list[Character], foreshadows: list[Foreshadow]) -> str:
    char_names = ", ".join(c.name for c in characters[:30]) or "(없음)"
    foreshadow_titles = ", ".join(f.title for f in foreshadows[:20]) or "(없음)"
    return (
        f"회차 제목: {chapter.title}\n"
        f"회차 ID: {chapter.id}\n"
        f"등장인물 목록: {char_names}\n"
        f"미회수 복선 목록: {foreshadow_titles}\n\n"
        f"본문:\n{_chapter_source_text(chapter)[:MAX_SOURCE_CHARS]}"
    )


class CognitiveProviderResponseError(ValueError):
    """provider가 인지 파생 JSON 계약을 지키지 않은 경우."""


def _parse_json_response(raw: str) -> dict:
    """provider 응답을 검증하고 파싱한다. 잘못된 응답은 성공으로 삼지 않는다."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # 첫 줄(```json 등)과 마지막 줄(```) 제거
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CognitiveProviderResponseError("cognitive provider returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise CognitiveProviderResponseError("cognitive provider response must be an object")
    for key in ("events", "knowledge"):
        if not isinstance(data.get(key), list):
            raise CognitiveProviderResponseError(f"cognitive provider field {key} must be a list")
    return data


def _resolve_character_id(db: Session, project_id: int, name: str | None) -> int | None:
    if not name:
        return None
    row = db.scalar(
        select(Character).where(
            Character.project_id == project_id,
            Character.name == name.strip(),
        )
    )
    return row.id if row else None


def _resolve_foreshadow_id(db: Session, project_id: int, title: str | None) -> int | None:
    if not title:
        return None
    row = db.scalar(
        select(Foreshadow).where(
            Foreshadow.project_id == project_id,
            Foreshadow.title == title.strip(),
        )
    )
    return row.id if row else None


def _resolve_fact_id(db: Session, project_id: int, hint: str | None) -> int | None:
    """target_hint로 memory_entries fact를 찾는다. 정확 일치 → 부분 일치 순."""
    if not hint:
        return None
    hint = hint.strip()
    # 제목·본문 일치
    row = db.scalar(
        select(MemoryEntry).where(
            MemoryEntry.project_id == project_id,
            MemoryEntry.kind == "fact",
            MemoryEntry.body == hint,
        )
    )
    if row:
        return row.id
    # 부분 일치 (최대 500행)
    rows = db.scalars(
        select(MemoryEntry).where(
            MemoryEntry.project_id == project_id,
            MemoryEntry.kind == "fact",
        ).limit(500)
    ).all()
    for r in rows:
        if hint in r.body or r.body in hint:
            return r.id
    return None


def extract_cognitive_candidates(
    db: Session,
    *,
    project_id: int,
    chapter_id: int,
    provider: CognitiveProvider,
    generated_by: str = "cognitive_worker",
) -> dict:
    """회차에서 사건·인지 후보를 추출해 draft로 저장한다.

    Returns:
        {"events_created": int, "knowledge_created": int, "skipped": bool}
    """
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or chapter.project_id != project_id:
        raise ValueError("chapter not found in project")

    source_text = _chapter_source_text(chapter)
    if not source_text.strip():
        return {"events_created": 0, "knowledge_created": 0, "skipped": True}

    source_sha = _content_sha256(source_text)

    # 이미 동일 source_sha로 파생된 행이 있으면 건너뛴다 (idempotent).
    existing_event = db.scalar(
        select(EventImpact).where(
            EventImpact.chapter_id == chapter_id,
            EventImpact.source_sha256 == source_sha,
            EventImpact.generated_by == generated_by,
        )
    )
    existing_knowledge = db.scalar(
        select(KnowledgeState).where(
            KnowledgeState.revealed_chapter_id == chapter_id,
            KnowledgeState.source_sha256 == source_sha,
            KnowledgeState.generated_by == generated_by,
        )
    )
    if existing_event is not None and existing_knowledge is not None:
        return {"events_created": 0, "knowledge_created": 0, "skipped": True}

    characters = list(db.scalars(
        select(Character).where(Character.project_id == project_id)
    ).all())
    foreshadows = list(db.scalars(
        select(Foreshadow).where(
            Foreshadow.project_id == project_id,
            Foreshadow.status == "설치",
        )
    ).all())

    user_prompt = _build_user_prompt(chapter, characters, foreshadows)
    raw = provider(_SYSTEM_PROMPT, user_prompt)
    data = _parse_json_response(raw)

    events_created = 0
    knowledge_created = 0

    # ---- events → event_impacts (draft) ----
    if existing_event is None:
        for ev in data.get("events", []):
            if not isinstance(ev, dict):
                continue
            label = str(ev.get("label", "")).strip()
            if not label:
                continue
            character_deltas = ev.get("character_deltas", [])
            relationship_deltas = ev.get("relationship_deltas", [])
            foreshadow_deltas = ev.get("foreshadow_deltas", [])
            if not all(isinstance(items, list) and all(isinstance(item, dict) for item in items)
                       for items in (character_deltas, relationship_deltas, foreshadow_deltas)):
                continue
            character_ids = {
                item.get("character_id") for item in character_deltas
                if item.get("character_id") is not None
            }
            foreshadow_ids = {
                item.get("foreshadow_id") for item in foreshadow_deltas
                if item.get("foreshadow_id") is not None
            }
            if (any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in character_ids)
                    or any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in foreshadow_ids)):
                continue
            valid_characters = set(db.scalars(select(Character.id).where(
                Character.project_id == project_id, Character.id.in_(character_ids)
            )).all()) if character_ids else set()
            valid_foreshadows = set(db.scalars(select(Foreshadow.id).where(
                Foreshadow.project_id == project_id, Foreshadow.id.in_(foreshadow_ids)
            )).all()) if foreshadow_ids else set()
            if valid_characters != character_ids or valid_foreshadows != foreshadow_ids:
                continue
            row = EventImpact(
                project_id=project_id,
                chapter_id=chapter_id,
                label=label,
                character_deltas_json=character_deltas,
                relationship_deltas_json=relationship_deltas,
                foreshadow_deltas_json=foreshadow_deltas,
                state_after=ev.get("state_after"),
                visibility="draft",
                source_sha256=source_sha,
                generated_by=generated_by,
                provenance_json={"prompt_version": COGNITIVE_PROMPT_VERSION},
            )
            db.add(row)
            events_created += 1

    # ---- knowledge → knowledge_states (draft) ----
    if existing_knowledge is None:
        for kn in data.get("knowledge", []):
            if not isinstance(kn, dict):
                continue
            subject_type = kn.get("subject_type", "")
            if subject_type not in ("reader", "character"):
                continue
            status = kn.get("status", "")
            if status not in ("unaware", "aware", "false_belief", "forgotten"):
                continue
            target_kind = kn.get("target_kind", "")
            if target_kind not in ("fact", "foreshadow"):
                continue

            character_id = None
            if subject_type == "character":
                character_id = _resolve_character_id(
                    db, project_id, kn.get("character_name")
                )
                if character_id is None:
                    continue  # 인물 미해결 → 건너뜀

            target_id = None
            hint = kn.get("target_hint")
            if target_kind == "foreshadow":
                target_id = _resolve_foreshadow_id(db, project_id, hint)
            elif target_kind == "fact":
                target_id = _resolve_fact_id(db, project_id, hint)
            if target_id is None:
                continue  # 대상 미해결 → 건너뜀

            row = KnowledgeState(
                project_id=project_id,
                subject_type=subject_type,
                character_id=character_id,
                target_kind=target_kind,
                target_id=target_id,
                status=status,
                revealed_chapter_id=chapter_id,
                effective_from_sort_order=chapter.sort_order,
                visibility="draft",
                source_sha256=source_sha,
                generated_by=generated_by,
                provenance_json={"prompt_version": COGNITIVE_PROMPT_VERSION},
            )
            db.add(row)
            knowledge_created += 1

    db.commit()
    return {
        "events_created": events_created,
        "knowledge_created": knowledge_created,
        "skipped": False,
    }


def plan_cognitive_jobs(
    db: Session,
    *,
    project_id: int,
    chapter_ids: Sequence[int] | None = None,
) -> list[Chapter]:
    """본문이 있는 회차를 파생 대상으로 고른다."""
    stmt = select(Chapter).where(
        Chapter.project_id == project_id,
        Chapter.content_md.isnot(None),
        Chapter.content_md != "",
    )
    if chapter_ids is not None:
        stmt = stmt.where(Chapter.id.in_(chapter_ids))
    stmt = stmt.order_by(Chapter.sort_order)
    return list(db.scalars(stmt).all())
