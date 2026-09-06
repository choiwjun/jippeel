"""canon 충돌 검사 서비스 — 고도화 G-023.

회차 본문이 캐릭터 카드·세계관(로어)·미회수 복선과 모순되는 지점을
LLM 1콜(비스트리밍, JSON)로 탐지한다. 결과는 응답으로만 반환하며
원고·설정을 절대 자동 수정하지 않는다(작가 판단 대상).
"""
import json

import openai
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chapter, Character, Foreshadow, LoreEntry
from app.services import llm
from app.services.bootstrap import _extract_json  # JSON 추출 계약 공유

_SYSTEM_JSON = (
    "너는 웹소설 연속성 검수 편집장이다. 주어진 회차 본문이 캐릭터 설정, "
    "세계관 설정, 복선과 모순되는 지점을 찾아낸다. 반드시 단일 유효한 JSON 객체만 "
    "출력하고 코드펜스·주석·설명은 절대 출력하지 않는다. 모순이 없으면 빈 배열을 "
    "반환한다. 실제 모순만 판정하고, 문체·호불호는 판정 대상이 아니다.\n"
    "특히 아래를 검사한다:\n"
    "- 시간축: 회차 사이 흐른 시간이 본문 묘사(계절·부상 상태·배고픔·조명 등)와 모순되는지\n"
    "- 위치: 캐릭터가 직전 회차 끝에 있던 장소에서 이동 불가능한 장면 전환이 없는지\n"
    "- 독자 인지: 독자가 아직 모른다고 표시된 사실을 본문이 미리 노출하지 않는지\n"
    "- 미회수 복선: 아직 회수 전인 복선을 본문이 결론까지 풀어버리지 않는지"
)


def _build_context_blocks(db: Session, chapter: Chapter) -> tuple[list[str], dict]:
    """회차 본문 + 직전 회차 끝부분 + 캐릭터 카드 + 로어 + 복선(독자 인지 포함) 블록."""
    blocks: list[str] = [f"[검수 대상 회차: {chapter.title}]\n{chapter.content_md}"]
    project_id = chapter.project_id

    prev = db.scalars(
        select(Chapter).where(
            Chapter.project_id == project_id,
            Chapter.sort_order < chapter.sort_order,
        ).order_by(Chapter.sort_order.desc())
    ).first()
    if prev and (prev.content_md or "").strip():
        blocks.append(
            f"[직전 회차: {prev.title} 끝부분 — 시간축·위치 연속성 기준]\n"
            f"…{prev.content_md[-1_000:]}")

    chars = db.scalars(
        select(Character).where(Character.project_id == project_id)).all()
    if chars:
        parts = []
        for ch in chars:
            fields = [f"이름: {ch.name}"]
            for f in ("role", "appearance", "personality", "speech_style", "background"):
                value = getattr(ch, f, None)
                if value:
                    fields.append(f"{f}: {value}")
            parts.append("\n".join(fields))
        blocks.append("[캐릭터 설정 — 본문의 인물 묘사·말투가 이와 모순되면 지적]\n"
                      + "\n---\n".join(parts))

    lore = db.scalars(
        select(LoreEntry).where(LoreEntry.project_id == project_id)).all()
    if lore:
        parts = [f"{e.title}: {e.content or ''}" for e in lore if e.content]
        blocks.append("[세계관 설정 — 본문이 이와 모순되면 지적]\n" + "\n".join(parts))

    foreshadows = db.scalars(
        select(Foreshadow).where(
            Foreshadow.project_id == project_id,
            Foreshadow.status.in_(("설치", "보류")))).all()
    known = [f for f in foreshadows if f.audience_knows]
    unknown = [f for f in foreshadows if not f.audience_knows]
    if unknown:
        parts = [f"{f.title}: {f.content or ''}" for f in unknown]
        blocks.append("[미회수 복선 — 아직 회수 전이므로 본문이 미리 결론을 풀어버리면 지적]\n"
                      + "\n".join(parts))
    if known:
        parts = [f"{f.title}: {f.content or ''}" for f in known]
        blocks.append("[독자가 이미 알게 된 사실 — 본문이 이를 마치 처음 밝히는 것처럼 "
                      "쓰면 지적(인지 중복)]\n" + "\n".join(parts))

    return blocks, {"characters": len(chars), "lore": len(lore),
                    "foreshadows": len(unknown), "audience_known": len(known)}


def build_messages(db: Session, chapter: Chapter) -> tuple[list[dict], dict]:
    blocks, counts = _build_context_blocks(db, chapter)
    user = "\n\n".join(blocks)
    user += ("\n\n위 회차 본문에서 설정 모순을 검사하라. 다음 JSON 형식으로 출력하라:\n"
             '{"issues": [{"quote": "본문 발췌(그대로)", "reason": "모순 이유", '
             '"severity": "warn|error|info"}]}')
    return [{"role": "system", "content": _SYSTEM_JSON},
            {"role": "user", "content": user}], counts


def parse_issues(raw: str) -> list[dict]:
    data = _extract_json(raw)
    issues = []
    for item in data.get("issues", []):
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not quote or not reason:
            continue
        severity = str(item.get("severity") or "warn")
        if severity not in ("info", "warn", "error"):
            severity = "warn"
        issues.append({"quote": quote[:500], "reason": reason[:500],
                       "severity": severity})
    return issues


async def run_canon_check(db: Session, chapter: Chapter, client, model: str,
                          temperature: float | None,
                          reasoning_effort: str | None) -> tuple[list[dict], dict, str]:
    """검사 실행 — 1회 실패 시 repair prompt 1회 재시도 후 예외 전파.

    사용량 기록(G-060)용으로 마지막 프롬프트 문자량을 모듈 변수에 남긴다.
    """
    global last_prompt_chars
    messages, counts = build_messages(db, chapter)
    last_prompt_chars = sum(len(m["content"]) for m in messages)
    raw = await llm.complete_chat(client, model, messages, temperature=temperature,
                                  reasoning_effort=reasoning_effort)
    try:
        return parse_issues(raw), counts, model
    except (ValueError, json.JSONDecodeError):
        repaired = list(messages) + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "직전 응답은 유효한 JSON이 아니었다. "
             "요청된 형식 그대로의 유효한 JSON만 다시 출력하라."},
        ]
        raw = await llm.complete_chat(client, model, repaired, temperature=temperature,
                                      reasoning_effort=reasoning_effort)
        return parse_issues(raw), counts, model


last_prompt_chars = 0


def friendly_api_error(exc: openai.APIError) -> str:
    from app.routers.ai_panel import _friendly_api_error
    return _friendly_api_error(exc)
