"""canon 충돌 검사 서비스 — 고도화 G-023.

회차 본문이 캐릭터 카드·세계관(로어)·미회수 복선과 모순되는 지점을
LLM 1콜(비스트리밍, JSON)로 탐지한다. 결과는 응답으로만 반환하며
원고·설정을 절대 자동 수정하지 않는다(작가 판단 대상).
"""
import hashlib
import json

import openai  # pyright: ignore[reportMissingImports]
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chapter, Character, Foreshadow, LoreEntry
from app.schemas import CanonCheckRequest
from app.services import ai_context, llm
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
    "- 미회수 복선: 아직 회수 전인 복선을 본문이 결론까지 풀어버리지 않는지\n"
    "작가가 이번 요청에서 회수/공개 허용한 복선 ID는 그 공개 자체만으로 미회수 복선 오류로 판정하지 않는다. "
    "그러나 다른 설정·관계·세계관 모순은 계속 지적한다."
)


def _build_context_blocks(db: Session, chapter: Chapter) -> tuple[list[str], dict]:
    """Compatibility wrapper for older direct tests.

    New callers should use build_messages(..., payload=...) so ownership and
    revision validation come from app.services.ai_context.
    """
    payload = CanonCheckRequest(chapter_id=chapter.id)
    bundle = ai_context.build_context_bundle(db, ai_context.request_from_canon(payload, chapter))
    return bundle.blocks, bundle.metadata


def build_messages(
    db: Session,
    chapter: Chapter,
    payload: CanonCheckRequest | None = None,
    bundle: ai_context.ContextBundle | None = None,
) -> tuple[list[dict], dict]:
    if payload is None:
        payload = CanonCheckRequest(chapter_id=chapter.id)
    if bundle is None:
        bundle = ai_context.build_context_bundle(db, ai_context.request_from_canon(payload, chapter))

    checked_input_body = chapter.content_md or ""
    context = dict(bundle.metadata)
    context["checked_input_revision"] = chapter.revision
    context["checked_input_hash"] = hashlib.sha256(checked_input_body.encode("utf-8")).hexdigest()

    user = "\n\n".join([ai_context.purpose_directive(bundle.episode_purpose), *bundle.blocks])
    user += ("\n\n위 회차 본문에서 설정 모순을 검사하라. 다음 JSON 형식으로 출력하라:\n"
             '{"issues": [{"quote": "본문 발췌(그대로)", "reason": "모순 이유", '
             '"severity": "warn|error|info"}]}')
    return [{"role": "system", "content": _SYSTEM_JSON},
            {"role": "user", "content": user}], context


def parse_issues(raw: str) -> list[dict]:
    data = _extract_json(raw)
    items = data.get("issues")
    if not isinstance(items, list):
        raise ValueError("canon issues must be a list")
    issues = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("canon issue must be an object")
        quote, reason = item.get("quote"), item.get("reason")
        if not isinstance(quote, str) or not isinstance(reason, str):
            raise ValueError("canon quote and reason must be strings")
        quote, reason = quote.strip(), reason.strip()
        if not quote or not reason:
            raise ValueError("canon quote and reason must not be empty")
        severity = item.get("severity")
        if severity not in ("info", "warn", "error"):
            severity = "warn"
        issues.append({"quote": quote[:500], "reason": reason[:500],
                       "severity": severity})
    return issues


async def run_canon_check(
    db: Session,
    chapter: Chapter,
    client,
    model: str,
    reasoning_effort: str | None,
    payload: CanonCheckRequest | None = None,
    bundle: ai_context.ContextBundle | None = None,
    messages_context: tuple[list[dict], dict] | None = None,
) -> tuple[list[dict], dict, str]:
    """검사 실행 — 결정적 사전검사 + LLM 1콜 + repair 1회.

    사용량 기록(G-060)용 프롬프트 문자량은 counts["prompt_chars"]로 반환한다.
    """
    if messages_context is None:
        messages, counts = build_messages(db, chapter, payload=payload, bundle=bundle)
    else:
        messages, counts = messages_context
    counts = dict(counts)
    counts["prompt_chars"] = sum(len(m["content"]) for m in messages)

    # 결정적 사전검사 — LLM 호출 전 명백한 위반을 먼저 수집
    # 계약/단위 테스트처럼 실제 ORM 엔티티가 아닌 호출에서는 사전검사를
    # 실행하지 않는다. 특히 Mock Session의 scalars()는 iterable 결과를
    # 보장하지 않으므로, LLM 호출에서 발생한 원래 예외를 가리지 않아야 한다.
    precheck_issues = (
        deterministic_precheck(
            db, chapter,
            approved_foreshadow_ids=payload.approved_foreshadow_ids if payload else None,
        )
        if type(chapter) is Chapter
        else []
    )

    raw = await llm.complete_chat(client, model, messages,
                                  reasoning_effort=reasoning_effort)
    try:
        llm_issues = parse_issues(raw)
    except (ValueError, json.JSONDecodeError):
        repaired = list(messages) + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "직전 응답의 JSON 문법 또는 요청된 구조가 유효하지 않았다. "
             "요청된 형식 그대로의 유효한 JSON만 다시 출력하라."},
        ]
        raw = await llm.complete_chat(client, model, repaired,
                                      reasoning_effort=reasoning_effort)
        llm_issues = parse_issues(raw)

    # 사전검사 + LLM 결과 병합 (중복 제거: 같은 quote+reason)
    seen = {(i["quote"], i["reason"]) for i in llm_issues}
    merged = llm_issues + [i for i in precheck_issues if (i["quote"], i["reason"]) not in seen]
    return merged, counts, model


def deterministic_precheck(
    db: Session,
    chapter: Chapter,
    approved_foreshadow_ids: list[int] | None = None,
) -> list[dict]:
    """LLM 호출 전 결정적 규칙 검사 — 승인된 canon 대비 명백한 위반을 탐지한다.

    LLM이 놓칠 수 있는 기계적 검사를 먼저 수행한다. 발견된 issue는
    LLM 결과와 병합되어 작가에게 전달된다.
    """
    issues: list[dict] = []
    body = chapter.content_md or ""
    if not body.strip():
        return issues

    pid = chapter.project_id
    approved_ids = set(approved_foreshadow_ids or [])

    # 1. 퇴장·사망 인물이 본문에 등장하는지
    departed = db.scalars(
        select(Character).where(
            Character.project_id == pid,
            Character.lifecycle_status.in_(["departed", "deceased"]),
        )
    ).all()
    for ch in departed:
        # lifecycle가 지정된 회차 이후에만 현재 시점의 등장 위반으로 판정한다.
        lifecycle_chapter = (
            db.get(Chapter, ch.lifecycle_chapter_id)
            if ch.lifecycle_chapter_id is not None else None
        )
        # lifecycle 회차 본문에는 퇴장 장면 자체가 포함될 수 있으므로,
        # 그 회차까지는 등장 위반으로 보지 않고 다음 회차부터 검사한다.
        if lifecycle_chapter is not None and chapter.sort_order <= lifecycle_chapter.sort_order:
            continue
        names = [ch.name] + (ch.aliases or [])
        for name in names:
            if name and name in body:
                status_label = "사망" if ch.lifecycle_status == "deceased" else "퇴장"
                issues.append({
                    "quote": name,
                    "reason": f"{status_label} 인물 '{ch.name}'이(가) 본문에 등장합니다",
                    "severity": "error",
                })
                break

    # 2. 미회수 복선의 결론적 표현 감지
    open_foreshadows = db.scalars(
        select(Foreshadow).where(
            Foreshadow.project_id == pid,
            Foreshadow.status == "설치",
        )
    ).all()
    for fs in open_foreshadows:
        if fs.id in approved_ids:
            continue  # 작가가 공개 허용한 복선은 제외
        title = (fs.title or "").strip()
        if not title:
            continue
        # 복선 제목이 본문에 직접 언급되고, 해결·진상 표현이 근처에 있으면 경고
        if title in body:
            resolve_markers = ["밝혀", "진실", "정체", "실은", "사실은", "알게 되", "깨달"]
            for marker in resolve_markers:
                if marker in body:
                    issues.append({
                        "quote": title,
                        "reason": f"미회수 복선 '{title}'이(가) 본문에서 해결 방향으로 언급됩니다",
                        "severity": "warn",
                    })
                    break

    # 3. 독자 미인지 사실 노출 감지
    from app.models import KnowledgeState
    reader_unaware = db.scalars(
        select(KnowledgeState).where(
            KnowledgeState.project_id == pid,
            KnowledgeState.subject_type == "reader",
            KnowledgeState.status == "unaware",
            KnowledgeState.visibility == "approved",
        )
    ).all()
    for ks in reader_unaware:
        if ks.target_kind == "fact":
            from app.models import MemoryEntry
            fact = db.get(MemoryEntry, ks.target_id)
            if fact and fact.body:
                # 사실의 핵심 키워드가 본문에 있으면 경고
                keywords = [w for w in fact.body.split() if len(w) >= 2][:5]
                for kw in keywords:
                    if kw in body:
                        issues.append({
                            "quote": kw,
                            "reason": f"독자가 아직 모르는 사실(#{ks.target_id})의 키워드가 본문에 노출됩니다",
                            "severity": "warn",
                        })
                        break

    return issues


def friendly_api_error(exc: openai.APIError) -> str:
    from app.routers.ai_panel import _friendly_api_error
    return _friendly_api_error(exc)
