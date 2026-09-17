"""AI 패널 라우터 (사양 §5 M4, GPT OAuth 브릿지).

- 고정 GPT OAuth provider를 통한 집필·감수·부트스트랩 호출
- PromptPreset CRUD
- POST /ai/generate — openai SDK + 로컬 OAuth 브릿지 SSE 스트리밍 (FR-405)

OAuth credential은 jippeel이 읽거나 저장하지 않는다. ``openai-oauth`` 사이드카가
``~/.codex/auth.json``을 관리하고, 이 라우터는 localhost transport만 사용한다.
"""
import asyncio
import inspect
import json
import time

import httpx
import openai  # pyright: ignore[reportMissingImports]
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse  # pyright: ignore[reportMissingImports]

from app.database import get_db
from app.models import AiEndpoint, Chapter, Character, Foreshadow, LoreEntry, Project, PromptPreset, Scene
from app.schemas import (
    AiEndpointCreate,
    AiEndpointOut,
    AiEndpointUpdate,
    AssistantGenerateNextRequest,
    AssistantGenerateNextResponse,
    AssistantPlanNextRequest,
    AssistantPlanNextResponse,
    EpisodeBrief,
    GenerateContext,
    GenerateParams,
    GenerateRequest,
    ParallelGenerateRequest,
    ParallelPlan,
    PlanRequest,
    PlanResponse,
    PromptPresetCreate,
    PromptPresetOut,
    PromptPresetUpdate,
    ReviewRequest,
)
from app.services import (agy_review, ai_context,
                          generation_runs as generation_runs_svc,
                          gpt_oauth, injection, llm, manuscripts,
                          parallel_writer, usage as usage_service)
from app.services.wordcount import count_novelpia_chars

GENERATION_HEARTBEAT_INTERVAL_SECONDS = 15.0
GENERATION_MAX_CONCURRENCY = 4
_GENERATION_SEMAPHORE = asyncio.Semaphore(GENERATION_MAX_CONCURRENCY)


async def _with_generation_heartbeat(source, stage: str = "generating", cleanup=None):
    """생성 SSE를 감싸 응답이 오래 없어도 연결 상태를 알린다.

    heartbeat에는 단계와 경과 시간만 담고 provider 응답·원고 내용은 담지 않는다.
    다음 provider 이벤트를 별도 task로 기다리므로 heartbeat 때문에 provider
    호출이 취소되지 않으며, client disconnect 시에는 정상적으로 task가 취소된다.
    """
    started = time.monotonic()
    acquire_task = asyncio.create_task(_GENERATION_SEMAPHORE.acquire())
    iterator = None
    next_event = None
    try:
        while not acquire_task.done():
            done, _ = await asyncio.wait(
                {acquire_task}, timeout=GENERATION_HEARTBEAT_INTERVAL_SECONDS)
            if not done:
                yield {"event": "heartbeat", "data": json.dumps({
                    "stage": "queued",
                    "elapsed_seconds": int(time.monotonic() - started),
                })}
        await acquire_task
        iterator = source.__aiter__()
        next_event = asyncio.create_task(iterator.__anext__())
        while True:
            done, _ = await asyncio.wait(
                {next_event}, timeout=GENERATION_HEARTBEAT_INTERVAL_SECONDS)
            if not done:
                yield {"event": "heartbeat", "data": json.dumps({
                    "stage": stage,
                    "elapsed_seconds": int(time.monotonic() - started),
                })}
                continue
            try:
                item = next_event.result()
            except StopAsyncIteration:
                break
            yield item
            next_event = asyncio.create_task(iterator.__anext__())
    finally:
        if acquire_task.done() and not acquire_task.cancelled() and acquire_task.result():
            _GENERATION_SEMAPHORE.release()
        elif not acquire_task.done():
            acquire_task.cancel()
        if next_event is not None:
            if not next_event.done():
                next_event.cancel()
            await asyncio.gather(next_event, return_exceptions=True)
        if iterator is not None:
            aclose = getattr(iterator, "aclose", None)
            if aclose is not None:
                await aclose()
        if cleanup is not None:
            result = cleanup()
            if inspect.isawaitable(result):
                await result

# 집필 기본 시스템 프롬프트 — 요즘 웹소설(노벨피아·문피아 상위권) 관례 반영.
# 보편 수치 규칙(대사 비율·문단 길이·도입 글자 수) 대신 회차 브리프와
# 장면 유형별 리듬에 적응하는 지침을 쓴다 (한국어 회차 품질 슬라이스).
NOVEL_SYSTEM_PROMPT = (
    "너는 한국 플랫폼 연재 경험이 풍부한 현역 한국 웹소설 작가이자 웹소설 연재 전문 작가다. 웹소설 연재 전문 작가로서 장르의 관습을 이해하되 "
    "작품의 고유한 설정과 인물에서 출발해, 독자가 다음 문장을 읽을 이유가 있는 원고를 쓴다.\n"
    "[지시 우선순위]\n"
    "- 시스템 규칙과 안전·출력 계약을 지킨다. 그 안에서 이번 화 브리프를 최우선 창작 계약으로 삼는다.\n"
    "- 브리프 다음에는 작품의 인물·세계관·연속성 컨텍스트와 호출 시 제공되는 확정 스타일 지침을 따른다. "
    "사용자 집필 지시는 이 경계를 깨지 않는 범위에서 적용한다. 선택과 대가는 장면의 인과와 감정 변화를 통해 보여준다.\n"
    "- 서로 충돌하는 정보가 있으면 새 사실을 임의로 확정하지 말고, 확정된 컨텍스트와 브리프를 보존한다.\n"
    "[브리프와 연속성]\n"
    "- 회차 브리프('[이번 화 브리프 — 생성 계약]' 블록)가 주어진 경우 제공된 감정 목표·핵심 사건·인물 선택·대가·금지사항을 반영한다. next_hook·결말 의도가 제공된 경우에만 그것도 반영한다.\n"
    "- 브리프가 주어진 경우에만 그 안에 없는 독립 사건을 새로 만들지 않는다. 다만 지정된 사건을 장면으로 보여주기 위한 연결 행동·반응·대사는 자연스럽게 구성한다. 브리프가 없으면 작품 컨텍스트와 사용자 집필 지시에 따라 장면을 구성한다.\n"
    "- 이전 화의 마지막 사건에서 인과적으로 이어간다. 이미 확정된 이름·관계·능력·시간표·세계관 규칙을 바꾸거나 무시하지 않는다.\n"
    "- 인물은 설정표를 낭독하지 않는다. 각자의 목표·정보량·감정·말투에 맞는 선택과 행동으로 성격을 드러낸다.\n"
    "[회차 설계]\n"
    "- 내부적으로 이 화의 장면 목표, 충돌, 선택과 대가, 변화의 흐름을 점검한 뒤 곧바로 본문을 쓴다. 이 설계나 점검 결과를 출력하지 않는다.\n"
    "- 시작은 불필요한 세계관 설명보다 장면의 갈등·질문·행동 중 가장 효과적인 지점에서 연다. 특히 첫 1~3화라면 주인공의 욕망·위기·핵심 능력 또는 비정상적 상황 중 하나를 빠르게 보여 주어 독자 약속을 분명히 한다.\n"
    "- 장면마다 인물이 원하는 것과 그것을 막는 힘을 분명히 하고, 설명보다 구체적인 행동·대사·감각으로 진행한다. 장면마다 목표·장애물·선택·결과가 이어지게 하며, 정보 설명만 이어지는 구간은 압축한다.\n"
    "- 회차 안에 작은 변화나 판단의 결과를 남긴다. 사건만 나열하거나 분위기만 반복하지 않는다. 독자가 기다린 보상 또는 새로운 질문을 적절한 시점에 제공해 전개 속도를 유지한다.\n"
    "- 작품의 주 장르 약속과 선택된 장르 클리셰가 있으면 실제 갈등·선택·보상으로 작동하게 하되 키워드 목록을 억지로 나열하지 않는다. 작품 설정·브리프·인물과 충돌하는 유행 요소를 임의로 추가하지 않는다.\n"
    "- serial은 다음 장면의 압력을 남긴다. 위기·새로운 정보·결심·관계 변화·미해결 질문 중 작품에 맞는 방식을 택한다. "
    "volume_end는 핵심 갈등의 수렴과 정서적 보상을 우선하고, series_finale는 억지 cliffhanger보다 완결감을 우선한다.\n"
    "[장면 유형별 리듬]\n"
    "- 대립·액션: 대사와 행동 비트가 장면을 주도한다. 한 행동의 결과가 다음 행동을 부르는 인과를 선명하게 쓴다.\n"
    "- 대립: 짧은 주고받기와 행동 한 줄을 리듬의 바닥으로 삼되, 중요한 감정 변화와 판단에는 충분한 호흡을 준다.\n"
    "- 액션: 한 문단에 여러 동작을 뭉개지 않는다. 동작·감각·판단·결과를 필요한 만큼 나눠 독자가 위치와 위험을 놓치지 않게 한다.\n"
    "- 정보정리: 필요한 정보만 인물의 목적·반응·갈등 사이에 배치한다. 설명 문단을 연속으로 쌓지 않는다.\n"
    "- 감정·이동: 시선·몸짓·말의 간격과 내면 판단을 통해 관계와 감정의 변화를 보여준다.\n"
    "[문체와 장르]\n"
    "- 호출 시 확정 스타일 지침이 있으면 그 특징을 일관되게 적용하되 예시 문장을 복사하지 않는다. 지침이 없으면 장르·시점·인물·장면 목적에 맞는 자연스러운 한국어를 선택한다.\n"
    "- 단문만 나열해 '~았다. ~였다.'로 끝나는 리듬은 피한다. 문장 길이를 변주하고, 필요한 곳에 연결 어미와 호흡을 사용한다.\n"
    "- 형용사와 수식어를 과하게 쌓지 않는다. 보여줄 가치가 있는 것은 구체적인 동사·감각·행동으로 보여준다. 감정 이름만 선언하지 말고 그 감정이 선택과 행동을 어떻게 바꾸는지 쓴다.\n"
    "- 시스템창·수치·장르 클리셰·인터넷 표현은 작품 설정과 확정 스타일 지침에 명시되거나 장면상 자연스러울 때만 사용한다.\n"
    "[금지와 출력 계약]\n"
    "- 작가 이름·인사말·소개 멘트 없이 바로 원고 본문으로 시작한다.\n"
    "- 원고 외의 설명·요약·분석·메타 코멘트·생성 과정·다음 화 안내를 출력하지 않는다. 출력은 원고 본문만이다.\n"
    "- 풍경·날씨·외모 장식 묘사를 연속해서 늘이지 않는다. '그러나', '한편' 같은 느린 전환을 습관적으로 반복하지 않는다.\n"
    "- 내부적으로 점검할 항목은 연속성·브리프 반영·인물 일관성·장면 목적·결말 압력이다. 점검표나 결과를 원고에 섞지 않는다.\n"
    "- 작품에 설정된 핵심 독자 약속과 장르 엔진을 존중하되, 고정된 화수·문자 수·연재주기·특정 키워드 사용을 성공 조건처럼 강제하지 않는다."
)
PREVIOUS_CHAPTER_TAIL_CHARS = 2_000  # 직전 회차는 끝부분(클리프행어) 위주로 주입

# 감수 패스 시스템 프롬프트 — 5개 관점의 근거 기반 감수 + 수정본.
# [감수]/[수정본] 마커는 SSE 분할 계약이므로 절대 변경하지 않는다.
REVIEW_SYSTEM_PROMPT = (
    "너는 한국 웹소설 플랫폼의 감수자(편집장)다. 초안 원고를 아래 다섯 관점에서 검수하고, 지정된 형식 그대로 출력한다.\n"
    "[감수 관점]\n"
    "- 구조와 독자 약속: 사건 배치·장면 전환·복선 회수와 페이스. 이 화가 하나의 장면 질문에 매달리는지, 전개 속도가 처지지 않는지, 장면 변화가 실제로 발생하는지.\n"
    "- 캐릭터: 말투·행동·동기·지위의 일관성. 선택과 대가가 그 인물에게 설득력 있는지.\n"
    "- 플랫폼/독자 약속: 초반이라면 첫 1~3화 안에 주 장르 약속과 차별적 설정이 장면으로 드러나는지, 선택된 장르 클리셰가 키워드 나열이 아니라 갈등과 보상으로 기능하는지.\n"
    "- 연속성/설정: 시간표·동선·세계관 규칙의 모순. 컨텍스트(회차·캐릭터·로어·브리프)와의 충돌.\n"
    "- 서사 엔진/상태 변화: 이 작품의 중심 성장 축(관계·조직·규칙·직업 등)이 이번 화에서 실제로 움직였는지, 선택과 대가가 인과로 이어지는지.\n"
    "- 문장/리듬: 중복·군더더기·설명 과다. '~았다. ~였다.' 단문만 나열돼 끊기는 단조 리듬. 장면 유형에 맞는 대사·행동·설명의 리듬.\n"
    "- 플랫폼/목적: episode_purpose에 맞는 마무리인지. serial은 다음 화 압력, volume_end는 권 단위 closure, series_finale는 시리즈 closure를 본다.\n"
    "[출력 형식 — 절대 어긋나지 않는다]\n"
    "[감수]\n"
    "- 중요한 문제만 3~7개. 각 항목은 '- '으로 시작하고, 관점, 원문 위치와 근거(원문 표현), 이유, 수정 제안을 한국어로 간결하게 쓴다. 사소한 취향 지적은 하지 않는다.\n"
    "[수정본]\n"
    "지적을 반영해 초안 전체를 수정한 원고를 그대로 쓴다. 설명·메타 코멘트 금지.\n"
    "분량은 초안과 비슷하게 유지하고, 좋은 부분은 함부로 바꾸지 않는다. 브리프와 작품 설정 밖의 사실을 새로 만들지 않는다."
)
REVIEW_MARKER = "[수정본]"  # 감수 의견 → 수정본 전환 지점 (라인 단위 매칭)
PARALLEL_REVIEW_SYSTEM_PROMPT = (
    "너는 한국 웹소설 편집장이다. 아래 장면별 조립 원고를 구조·캐릭터·연속성/설정·문장/리듬·플랫폼/목적 "
    "다섯 관점에서 감수하라('~았다. ~였다.' 단문 나열로 끊기는 단조 리듬도 지적 대상). "
    "episode_purpose에 맞는 마무리인지 보고, 장면 계약은 검수 기준이며 원고에 없는 사실을 추측하지 마라.\n"
    "[출력 형식 — 절대 어긋나지 않는다]\n"
    "[감수]\n"
    "- 중요한 문제만 3~7개. 원문 위치, 근거, 이유, 수정 제안을 한국어로 간결하게 쓴다.\n"
    "[수정본]\n"
    "지적을 반영해 조립 원고 전체를 수정한 원고를 그대로 쓴다. 설명·메타 코멘트 금지. "
    "분량은 원고와 비슷하게 유지하고, 좋은 부분은 함부로 바꾸지 않는다. "
    "컨텍스트와 장면 계약 밖의 사실을 새로 만들지 마라.\n"
    "고정된 화수·문자 수·연재주기나 특정 키워드의 사용 여부만으로 문제를 만들지 말고, 장면의 인과·상태 변화·독자 약속에 근거해 중요한 문제만 지적하라."
)

router = APIRouter()


# ---------- helpers ----------
def _find_legacy_endpoint_or_404(eid: int, db: Session) -> AiEndpoint:
    endpoint = db.get(AiEndpoint, eid)
    if endpoint is None:
        raise HTTPException(status_code=404, detail="endpoint not found")
    return endpoint


def _serialize_legacy_endpoint(endpoint: AiEndpoint) -> AiEndpointOut:
    """레거시 endpoint 응답에서도 API key는 절대 반환하지 않는다."""
    return AiEndpointOut(
        id=endpoint.id,
        name=endpoint.name,
        base_url=endpoint.base_url,
        default_model=endpoint.default_model,
        temperature=endpoint.temperature,
        reasoning_effort=endpoint.reasoning_effort,
        is_default=endpoint.is_default,
        has_api_key=bool(endpoint.api_key_encrypted),
    )


def _clear_legacy_default_rows(db: Session, exclude_id: int | None = None) -> None:
    stmt = select(AiEndpoint).where(AiEndpoint.is_default.is_(True))
    for row in db.scalars(stmt):
        if exclude_id is None or row.id != exclude_id:
            row.is_default = False


def _get_preset_or_404(pid: int, db: Session) -> PromptPreset:
    preset = db.get(PromptPreset, pid)
    if preset is None:
        raise HTTPException(status_code=404, detail="preset not found")
    return preset


def _get_provider_or_503() -> gpt_oauth.GptOAuthProvider:
    try:
        return gpt_oauth.get_provider()
    except gpt_oauth.OAuthProviderConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _resolve_model(provider: gpt_oauth.GptOAuthProvider, requested: str | None = None) -> str:
    """Return the provider model; legacy client model hints are ignored.

    The optional argument remains for request/test compatibility, but callers can
    never redirect a writing request to a user-selected model.
    """
    del requested
    return provider.default_model


def _format_brief_block(brief: EpisodeBrief) -> str:
    """회차 브리프 → 안정적인 한국어 경계 블록.

    비어 있는(선택 미입력) 필드는 생략하고, 브리프 밖의 독립 사건 생성을 금지하는
    경계 지시로 블록을 닫는다. 주입은 입력 컨텍스트일 뿐이며 원고에 삽입되지 않는다.
    """
    lines = ["[이번 화 브리프 — 생성 계약]"]
    lines.append(f"감정 목표: {brief.emotion_goal}")
    lines.append("핵심 사건:")
    lines.extend(f"- {event}" for event in brief.core_events)
    lines.append("인물 선택:")
    lines.extend(f"- {choice}" for choice in brief.character_choices)
    lines.append(f"대가(치르는 것): {brief.cost}")
    lines.append("금지사항:")
    lines.extend(f"- {item}" for item in brief.prohibitions)
    lines.append(f"다음 화 훅: {brief.next_hook}")
    if brief.scene_type:
        lines.append(f"장면 유형: {brief.scene_type}")
    if brief.target_chars_novelpia is not None:
        lines.append(f"목표 글자 수(노벨피아): {brief.target_chars_novelpia}")
    lines.append("→ 위 브리프에 없는 독립 사건을 새로 만들지 마라.")
    return "\n".join(lines)


def _style_profile_block(style_profile_text: str | None) -> str:
    if not style_profile_text:
        return ""
    return (
        "[작품 문체 프로파일 — 낮은 우선순위의 문체 참고]\n"
        "아래 내용은 문장 리듬·어휘·서술 거리 같은 표현 방식에만 적용한다. "
        "정본, 회차 브리프, 장면 목표·선택·대가·금지사항, 인과성, 시스템 계약과 충돌하면 "
        "그 내용을 무시하고 상위 계약을 따른다. 이 블록을 사건·인물·고유명사·시장 지시로 "
        "해석하거나 새 사건을 만들지 마라.\n"
        f"{style_profile_text}"
    )


def _system_with_style(base: str, style_profile_text: str | None) -> str:
    style_block = _style_profile_block(style_profile_text)
    if not style_block:
        return base
    return f"{base}\n\n{style_block}"




def _foreshadow_items_from_metadata(db: Session, metadata: dict) -> list[dict]:
    ids = list(metadata.get("included_foreshadow_ids", []))
    if not ids:
        return []
    rows = db.scalars(select(Foreshadow).where(Foreshadow.id.in_(ids))).all()
    by_id = {row.id: row.title for row in rows}
    return [{"id": row_id, "title": by_id.get(row_id, "")} for row_id in ids]


def _build_context_blocks(payload: GenerateRequest, db: Session) -> tuple[list[str], list[dict], dict, list[dict], dict]:
    """Build context through the shared ContextBundle module.

    Kept for caller/test stability. Ownership validation lives in
    app.services.ai_context, not in this router.
    """
    bundle = ai_context.build_context_bundle(db, ai_context.request_from_generate(payload))
    foreshadows = _foreshadow_items_from_metadata(db, bundle.metadata)
    return (
        bundle.blocks,
        list(bundle.metadata.get("injected_lore", [])),
        dict(bundle.metadata.get("outline", {})),
        foreshadows,
        bundle.metadata,
    )


def _build_messages(
    payload: GenerateRequest,
    db: Session,
    bundle: ai_context.ContextBundle | None = None,
) -> tuple[str, list[dict], list[dict], dict, list[dict], dict]:
    """프리셋 템플릿 + 공유 ContextBundle + override → chat messages.

    반환: (model_hint, messages, 자동 주입된 로어 목록, 목차 주입 정보, 복선 주입 목록, 컨텍스트 메타데이터)
    """
    if bundle is None:
        bundle = ai_context.build_context_bundle(db, ai_context.request_from_generate(payload))
    sections = ["다음 컨텍스트를 참고해 작성하세요.", *bundle.blocks]
    context_text = "\n\n".join(p for p in sections if p)

    instruction = payload.prompt_override
    if payload.preset_id is not None:
        preset = _get_preset_or_404(payload.preset_id, db)
        instruction = f"{preset.template_text}\n\n{instruction}" if instruction else preset.template_text
    if not instruction:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="preset_id 또는 prompt_override 중 하나는 필요합니다.")

    user_content = f"{context_text}\n\n---\n\n지시:\n{instruction}"
    base_system_prompt = f"{NOVEL_SYSTEM_PROMPT}\n\n{ai_context.purpose_directive(bundle.episode_purpose)}"
    system_prompt = _system_with_style(base_system_prompt, bundle.style_profile_text)
    messages = [{"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}]
    injected_foreshadows = _foreshadow_items_from_metadata(db, bundle.metadata)
    return (
        "default",
        messages,
        list(bundle.metadata.get("injected_lore", [])),
        dict(bundle.metadata.get("outline", {})),
        injected_foreshadows,
        bundle.metadata,
    )




def _style_suffix_from_generation_system(system_prompt: str) -> str:
    if system_prompt.startswith(NOVEL_SYSTEM_PROMPT):
        return system_prompt[len(NOVEL_SYSTEM_PROMPT):].strip()
    return ""


def _append_generation_style(system_prompt: str, generation_system_prompt: str) -> str:
    suffix = _style_suffix_from_generation_system(generation_system_prompt)
    if not suffix:
        return system_prompt
    return f"{system_prompt}\n\n{suffix}"


def _friendly_api_error(exc: openai.APIError) -> str:
    """FR-408 — API 오류를 사용자가 이해 가능한 안내로 변환."""
    if isinstance(exc, openai.APITimeoutError):
        return "GPT OAuth 브릿지 응답 시간 초과. 브릿지와 계정 인증 상태를 확인하세요."
    if isinstance(exc, openai.APIConnectionError):
        return "GPT OAuth 브릿지에 연결할 수 없습니다. openai-oauth가 실행 중인지 확인하세요."
    if isinstance(exc, openai.AuthenticationError):
        return "ChatGPT OAuth 인증에 실패했습니다. openai-oauth 로그인 상태를 확인하세요."
    if isinstance(exc, openai.NotFoundError):
        return "고정 GPT OAuth 모델 또는 브릿지 경로를 찾을 수 없습니다. 브릿지 버전을 확인하세요."
    if isinstance(exc, openai.RateLimitError):
        return "ChatGPT 요청 한도 초과(429). 잠시 후 다시 시도하세요."
    if isinstance(exc, openai.APIStatusError):
        # 상태 코드는 안전한 진단이지만 응답 본문(message)은 provider 측
        # 민감정보를 포함할 수 있어 노출하지 않는다 (감사 A1).
        return f"GPT OAuth 브릿지 오류(HTTP {exc.status_code}). 브릿지 로그를 확인하세요."
    # 분류되지 않은 오류는 원문을 반사하지 않고 타입명만 남긴다.
    return f"GPT OAuth 브릿지 오류: {type(exc).__name__}"


def _is_retryable_bridge_error(exc: Exception) -> bool:
    """스트림 중 일시적으로 끊긴 localhost bridge 요청만 한 번 재시도한다."""
    retryable = (
        openai.APIConnectionError,
        openai.APITimeoutError,
        httpx.RemoteProtocolError,
        httpx.ReadError,
        httpx.ConnectError,
    )
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, retryable):
            return True
        current = current.__cause__ or current.__context__
    return False


async def _close_llm_client(client) -> None:
    """실제 AsyncOpenAI와 테스트 fake 모두에서 안전하게 클라이언트를 닫는다."""
    closer = getattr(client, "aclose", None)
    if closer is None:
        return
    result = closer()
    if inspect.isawaitable(result):
        await result


# ---------- Legacy endpoint compatibility ----------
# 신규 집필 경로는 아래 리소스를 읽지 않는다. 기존 로컬 DB와 구버전 도구가
# 마이그레이션되는 동안만 접근을 허용하며 OpenAPI/신규 UI에는 노출하지 않는다.
@router.get("/ai/endpoints", response_model=list[AiEndpointOut], include_in_schema=False)
def list_legacy_endpoints(db: Session = Depends(get_db)):
    rows = db.scalars(select(AiEndpoint).order_by(AiEndpoint.id)).all()
    return [_serialize_legacy_endpoint(row) for row in rows]


@router.post("/ai/endpoints", response_model=AiEndpointOut,
             status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_legacy_endpoint(payload: AiEndpointCreate, db: Session = Depends(get_db)):
    from app.services.crypto import get_cipher

    endpoint = AiEndpoint(
        name=payload.name,
        base_url=payload.base_url,
        api_key_encrypted=get_cipher().encrypt(payload.api_key) if payload.api_key else None,
        default_model=payload.default_model,
        temperature=payload.temperature,
        reasoning_effort=payload.reasoning_effort,
        is_default=False,
    )
    if payload.is_default:
        _clear_legacy_default_rows(db)
        endpoint.is_default = True
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return _serialize_legacy_endpoint(endpoint)


@router.patch("/ai/endpoints/{eid}", response_model=AiEndpointOut, include_in_schema=False)
def update_legacy_endpoint(eid: int, payload: AiEndpointUpdate,
                           db: Session = Depends(get_db)):
    from app.services.crypto import get_cipher

    endpoint = _find_legacy_endpoint_or_404(eid, db)
    data = payload.model_dump(exclude_unset=True)
    if "api_key" in data:
        raw_key = data.pop("api_key")
        endpoint.api_key_encrypted = get_cipher().encrypt(raw_key) if raw_key else None
    if data.pop("is_default", None):
        _clear_legacy_default_rows(db, exclude_id=eid)
        endpoint.is_default = True
    for field, value in data.items():
        setattr(endpoint, field, value)
    db.commit()
    db.refresh(endpoint)
    return _serialize_legacy_endpoint(endpoint)


@router.delete("/ai/endpoints/{eid}", status_code=status.HTTP_204_NO_CONTENT,
               include_in_schema=False)
def delete_legacy_endpoint(eid: int, db: Session = Depends(get_db)):
    endpoint = _find_legacy_endpoint_or_404(eid, db)
    db.delete(endpoint)
    db.commit()


@router.get("/ai/endpoints/{eid}/models", include_in_schema=False)
async def list_legacy_remote_models(eid: int, db: Session = Depends(get_db)):
    endpoint = _find_legacy_endpoint_or_404(eid, db)
    client = llm.make_client(endpoint.base_url, endpoint.api_key_encrypted)
    try:
        page = client.models.list()
        if inspect.isawaitable(page):
            page = await page
        return {"data": [{"id": model.id} for model in page.data]}
    except openai.APIError as exc:
        raise HTTPException(status_code=502, detail=_friendly_api_error(exc)) from exc


# ---------- PromptPreset CRUD ----------
@router.get("/ai/presets", response_model=list[PromptPresetOut])
def list_presets(db: Session = Depends(get_db)):
    return db.scalars(select(PromptPreset).order_by(PromptPreset.id)).all()


@router.post("/ai/presets", response_model=PromptPresetOut,
             status_code=status.HTTP_201_CREATED)
def create_preset(payload: PromptPresetCreate, db: Session = Depends(get_db)):
    preset = PromptPreset(**payload.model_dump())
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return preset


@router.patch("/ai/presets/{pid}", response_model=PromptPresetOut)
def update_preset(pid: int, payload: PromptPresetUpdate, db: Session = Depends(get_db)):
    preset = _get_preset_or_404(pid, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(preset, field, value)
    db.commit()
    db.refresh(preset)
    return preset


@router.delete("/ai/presets/{pid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_preset(pid: int, db: Session = Depends(get_db)):
    preset = _get_preset_or_404(pid, db)
    db.delete(preset)
    db.commit()


# ---------- AI 사용량 (고도화 G-060) ----------
@router.get("/ai/usage")
def ai_usage(days: int = 30, db: Session = Depends(get_db)):
    """문자량 기반 AI 사용 통계 — kind+model 그룹 집계."""
    from app.schemas import AiUsageSummaryOut
    return [AiUsageSummaryOut(**row).model_dump()
            for row in usage_service.summary(limit_days=max(min(days, 365), 1), db=db)]


def _split_review_stream():
    """감수 스트림을 '[감수]'/'[수정본]' 구간으로 분리하는 상태 기계.

    마커가 청크 경계에서 잘리는 것을 대비해 review 페이즈에서는
    항상 마커 길이만큼의 말미를 버퍼에 남긴다. 반환: (feed, flush) —
    feed(delta)는 ("review"|"refined", 청크)을 yield하는 async generator,
    flush()는 스트림 종료 시 호출하며 [수정본] 마커 없이 끝난 경우
    carry에 남은 마지막 구간을 review 청크로 방출한다.
    """
    phase = "review"
    carry = ""

    async def feed(delta: str):
        nonlocal carry, phase
        if phase == "refined":
            if delta:
                yield "refined", delta
            return
        buf = carry + delta
        idx = buf.find(REVIEW_MARKER)
        if idx == -1:
            # 마커가 다음 청크에 걸칠 수 있으므로 말미를 보존
            keep = max(0, len(buf) - (len(REVIEW_MARKER) - 1))
            carry = buf[keep:]
            if keep > 0:
                yield "review", buf[:keep]
            return
        head = buf[:idx].rstrip("\n")
        if head:
            yield "review", head
        rest = buf[idx + len(REVIEW_MARKER):]
        # 마커 뒤의 ':' 및 줄바꿈 제거 후 수정본 페이즈 진입
        rest = rest.lstrip(":\n\r ")
        phase = "refined"
        if rest:
            yield "refined", rest
        carry = ""

    async def flush():
        nonlocal carry
        if phase == "review" and carry:
            yield "review", carry
        carry = ""

    return feed, flush


def _review_backend(provider: gpt_oauth.GptOAuthProvider, review_opts,
                    default_max_tokens: int | None) -> dict:
    """감수 호출 설정 — JIPPEEL_REVIEW_PROVIDER=agy면 Antigravity CLI로 라우팅.

    생성은 고정 GPT OAuth 브릿지를 유지하고 감수만 두 번째 모델로 보내는
    교차 감수(cross-model review)다. agy는 모델명 체계가 다르므로 요청의
    review.model은 무시하고 JIPPEEL_AGY_MODEL만 사용한다.
    """
    agy_cfg = agy_review.get_agy_review_config()
    if agy_cfg is not None:
        return {"backend": "agy", "provider_name": agy_review.PROVIDER_NAME,
                "model": agy_cfg.model,
                "reasoning_effort": review_opts.reasoning_effort or "",
                "max_tokens": review_opts.max_tokens or default_max_tokens,
                "agy": agy_cfg}
    return {"backend": "bridge", "provider_name": provider.name,
            "model": _resolve_model(provider, review_opts.model),
            "reasoning_effort": review_opts.reasoning_effort or provider.reasoning_effort,
            "max_tokens": review_opts.max_tokens or default_max_tokens,
            "agy": None}


def _review_stream(review_cfg: dict, review_messages: list[dict], client):
    """review_cfg.backend에 따라 감수 텍스트 델타 스트림을 반환한다."""
    if review_cfg["backend"] == "agy":
        return agy_review.stream_agy_chat(
            review_cfg["agy"], review_cfg["model"], review_messages)
    return llm.stream_chat(
        client, review_cfg["model"], review_messages,
        max_tokens=review_cfg["max_tokens"],
        reasoning_effort=review_cfg["reasoning_effort"])


# ---------- AI 생성 스트리밍 ----------
@router.post("/ai/generate")
async def generate(payload: GenerateRequest, db: Session = Depends(get_db)):
    bundle = ai_context.build_context_bundle(db, ai_context.request_from_generate(payload))
    provider = _get_provider_or_503()
    _, messages, injected_lore, injected_outline, injected_foreshadows, context_metadata = _build_messages(payload, db, bundle=bundle)
    if payload.approved_plan is not None:
        # 계획→승인→집필: 작가 승인 계획을 계약으로 주입(planner 재호출 없음)
        try:
            parallel_writer.validate_plan_for_purpose(
                payload.approved_plan, bundle.episode_purpose)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        messages[-1] = {
            "role": "user",
            "content": (
                f"{messages[-1]['content']}\n\n"
                "[작가 승인 집필 계획 — 반드시 따를 것]\n"
                f"{payload.approved_plan.model_dump_json()}\n"
                "계획의 장면 순서·objective·choice·cost·결말 의도를 "
                "행동과 대사로 정확히 집필하라."
            ),
        }
    model = _resolve_model(provider, payload.params.model)
    client = llm.make_long_running_client(provider.base_url, None)

    # 감수 provider는 서버 설정이 결정한다 — 기본은 같은 고정 GPT OAuth
    # 브릿지, JIPPEEL_REVIEW_PROVIDER=agy면 Antigravity CLI(Gemini)로
    # 교차 감수한다. provider 선택/키 입력은 요청에서 받지 않는다.
    review_cfg = None
    if payload.review is not None:
        review_cfg = _review_backend(provider, payload.review, payload.params.max_tokens)

    manifest = {
        "context_metadata": context_metadata,
        "injected_lore": injected_lore,
        "injected_outline": injected_outline,
        "injected_foreshadows": injected_foreshadows,
        "episode_purpose": payload.context.episode_purpose,
        "scene_id": payload.context.scene_id,
        "has_prompt_override": payload.prompt_override is not None,
        "brief": payload.context.brief.model_dump() if payload.context.brief else None,
        "plan_source": ("approved" if payload.approved_plan is not None
                        else "none"),
        "plan_output_id": payload.plan_output_id,
    }

    async def event_stream():
        # 시작 이벤트 — 프론트가 스트림 개시를 확정하고, 자동 주입된 로어 목록을
        # 투명하게 표시할 수 있다(주입 내역 공개)
        yield {"event": "start",
               "data": json.dumps({"model": model, "injected_lore": injected_lore,
                                   "injected_outline": injected_outline,
                                   "injected_foreshadows": injected_foreshadows,
                                   "review_enabled": review_cfg is not None,
                                   "context_metadata": context_metadata},
                                  ensure_ascii=False)}
        t0 = time.monotonic()
        outputs: list[generation_runs_svc.OutputSpec] = []
        if payload.approved_plan is not None:
            outputs.append(generation_runs_svc.OutputSpec(
                channel="plan",
                text=payload.approved_plan.model_dump_json()))
        usage_ids: list[int] = []
        saved: dict = {"result": None}
        run_status = "completed"

        def _finalize():
            # E1 생성 이력 — 실패해도 스트림을 막지 않는다(best-effort)
            if saved["result"] is None:
                try:
                    saved["result"] = generation_runs_svc.save_run(
                    surface="generate",
                    project_id=payload.context.project_id,
                    chapter_id=payload.context.chapter_id,
                    preset_id=payload.preset_id,
                    model=model,
                    reasoning_effort=provider.reasoning_effort,
                    messages=messages,
                    manifest={**manifest, "ai_usage_ids": usage_ids},
                    status=run_status,
                    wall_ms=int((time.monotonic() - t0) * 1000),
                    outputs=outputs,
                    applied_rules=context_metadata.get("applied_rule_ids"),
                    ai_usage_id=usage_ids[0] if usage_ids else None,
                    db=db)
                except Exception:  # noqa: BLE001
                    saved["result"] = (None, {})
            return saved["result"]

        completion_chars = 0
        draft_parts: list[str] = []
        draft_error: str | None = None
        try:
            try:
                async for delta in llm.stream_chat(client, model, messages,
                                                   max_tokens=payload.params.max_tokens,
                                                   reasoning_effort=provider.reasoning_effort):
                    completion_chars += len(delta)
                    draft_parts.append(delta)
                    yield {"event": "message", "data": json.dumps({"delta": delta}, ensure_ascii=False)}
            except openai.APIError as exc:
                draft_error = _friendly_api_error(exc)
            except Exception as exc:  # noqa: BLE001 — 스트림 내 예외도 SSE 에러 이벤트로 전달
                draft_error = f"스트리밍 실패: {type(exc).__name__}"
            # E1 — 에러여도 부분 초안을 보존한다(실측이 곧 데이터)
            if draft_parts:
                outputs.append(generation_runs_svc.OutputSpec(
                    channel="draft", text="".join(draft_parts)))
            if draft_error is not None:
                run_status = "provider_error"
                yield {"event": "error",
                       "data": json.dumps({"detail": draft_error}, ensure_ascii=False)}
            else:
                # G-060 사용량 기록 (best-effort)
                uid = usage_service.record(
                    kind="generate", model=model, endpoint_name=provider.name,
                    prompt_chars=sum(len(str(m.get("content") or "")) for m in messages),
                    completion_chars=completion_chars, db=db)
                if uid is not None:
                    usage_ids.append(uid)

                # 기존 인라인 감수 — 초안 스트림이 정상 종료된 뒤 같은 SSE로 이어간다.
                if review_cfg is not None:
                    yield {"event": "review_start",
                           "data": json.dumps({"model": review_cfg["model"],
                                               "provider": review_cfg["provider_name"],
                                               "reasoning_effort": review_cfg["reasoning_effort"]},
                                              ensure_ascii=False)}
                    review_messages = [
                        {"role": "system", "content": _append_generation_style(REVIEW_SYSTEM_PROMPT, messages[0]["content"])},
                        {"role": "user",
                         "content": f"{messages[-1]['content']}\n\n---\n\n[초안 원고]\n{''.join(draft_parts)}"},
                    ]
                    review_chars = 0
                    channel_parts: dict[str, list[str]] = {"review": [], "refined": []}
                    try:
                        feed, flush_review = _split_review_stream()
                        async for delta in _review_stream(
                                review_cfg, review_messages, client):
                            review_chars += len(delta)
                            async for event_name, chunk in feed(delta):
                                channel_parts.setdefault(event_name, []).append(chunk)
                                yield {"event": event_name,
                                       "data": json.dumps({"delta": chunk}, ensure_ascii=False)}
                        # 종료 flush — [수정본] 마커 없이 끝나도 carry의 마지막 구간을 review로 방출
                        async for event_name, chunk in flush_review():
                            channel_parts.setdefault(event_name, []).append(chunk)
                            yield {"event": event_name,
                                   "data": json.dumps({"delta": chunk}, ensure_ascii=False)}
                    except openai.APIError as exc:
                        yield {"event": "review_error",
                               "data": json.dumps({"detail": _friendly_api_error(exc)}, ensure_ascii=False)}
                    except Exception as exc:  # noqa: BLE001
                        yield {"event": "review_error",
                               "data": json.dumps({"detail": f"감수 실패: {type(exc).__name__}"},
                                                  ensure_ascii=False)}
                    else:
                        if review_chars:
                            uid = usage_service.record(
                                kind="review", model=review_cfg["model"],
                                endpoint_name=review_cfg["provider_name"],
                                prompt_chars=sum(len(str(m.get("content") or "")) for m in review_messages),
                                completion_chars=review_chars, db=db)
                            if uid is not None:
                                usage_ids.append(uid)
                    finally:
                        for ch in ("review", "refined"):
                            if channel_parts.get(ch):
                                outputs.append(generation_runs_svc.OutputSpec(
                                    channel=ch, text="".join(channel_parts[ch])))
        except (GeneratorExit, asyncio.CancelledError):
            run_status = "aborted"
            raise
        finally:
            run_id, output_ids = _finalize()
        # 종료 계약 — generation_saved(additive). draft 에러 시 기존 계약대로
        # done 없이 종료(실패를 성공으로 오인하지 않도록)
        yield {"event": "generation_saved",
               "data": json.dumps({"run_id": run_id, "outputs": output_ids},
                                  ensure_ascii=False)}
        if draft_error is None:
            yield {"event": "done", "data": "[DONE]"}

    return EventSourceResponse(_with_generation_heartbeat(
        event_stream(), cleanup=lambda: _close_llm_client(client)))


# ---------- AI 어시스턴트 계획→승인→초안 집필 ----------
def _assistant_target_chapter(
    db: Session, pid: int, chapter_id: int | None,
) -> Chapter:
    """assistant 경로의 대상 회차 선택.

    chapter_id가 주어지면 그 회차(내용이 있어도 된다 — 원고를 쓰지 않으므로
    덮어쓰기 위험이 없다). 미지정이면 정렬 순서상 첫 빈 회차를 고른다.
    """
    if chapter_id is not None:
        chapter = db.get(Chapter, chapter_id)
        if chapter is None or chapter.project_id != pid:
            raise HTTPException(status_code=404, detail="chapter not found")
        return chapter
    chapters = db.scalars(
        select(Chapter)
        .where(Chapter.project_id == pid)
        .order_by(Chapter.volume.asc().nulls_last(), Chapter.sort_order.asc(), Chapter.id.asc())
    ).all()
    chapter = next(
        (row for row in chapters if not (row.content_md or "").strip()),
        None,
    )
    if chapter is None:
        raise HTTPException(status_code=409, detail="생성할 빈 회차가 없습니다.")
    return chapter


def _assistant_context(
    chapter: Chapter,
    pov_character_id: int | None = None,
    include_trend_pack: bool = False,
) -> GenerateContext:
    """assistant 경로 공용 컨텍스트 — 대상 회차에 내용이 있으면 함께 주입한다."""
    return GenerateContext(
        project_id=chapter.project_id,
        chapter_id=chapter.id,
        include_chapter_content=bool((chapter.content_md or "").strip()),
        expected_revision=chapter.revision,
        previous_chapter=True,
        auto_lore=True,
        auto_lore_semantic=True,
        auto_outline=True,
        auto_foreshadow=True,
        style_profile=True,
        include_memory=True,
        auto_characters=True,
        include_relationships=True,
        pov_character_id=pov_character_id,
        include_trend_pack=include_trend_pack,
    )


@router.post(
    "/projects/{pid}/assistant/plan-next",
    response_model=AssistantPlanNextResponse,
)
async def assistant_plan_next(
    pid: int,
    payload: AssistantPlanNextRequest,
    db: Session = Depends(get_db),
):
    """대상 회차의 집필 계획만 생성한다 — 원고는 절대 쓰지 않는다.

    작가는 반환된 계획을 검토한 뒤 generate-next에 approved_plan으로 넘겨
    집필을 승인한다. 계획 산출물은 생성 이력(channel=plan)에 보존된다.
    """
    if db.get(Project, pid) is None:
        raise HTTPException(status_code=404, detail="project not found")
    chapter = _assistant_target_chapter(db, pid, payload.chapter_id)

    request = GenerateRequest(
        prompt_override=(
            "현재 회차의 제목·회차 목표·목차·세계관·인물 설정을 정본으로 삼아 "
            "다음 회차 본문을 완성된 한국어 웹소설 원고로 집필하라."
        ),
        context=_assistant_context(
            chapter, payload.pov_character_id, payload.include_trend_pack
        ),
        params=GenerateParams(max_tokens=payload.max_tokens),
    )
    bundle = ai_context.build_context_bundle(
        db, ai_context.request_from_generate(request))
    provider = _get_provider_or_503()
    _, base_messages, injected_lore, injected_outline, injected_foreshadows, context_metadata = _build_messages(
        request, db, bundle=bundle)
    model = _resolve_model(provider)
    planner_messages = _planner_messages(base_messages)

    t0 = time.monotonic()
    status_str = "completed"
    outputs: list[generation_runs_svc.OutputSpec] = []
    plan: ParallelPlan | None = None
    error_detail: str | None = None
    try:
        plan_exc: ValueError | None = None
        for _attempt in range(2):  # 계약 밖 JSON은 일시적 — 1회 재시도
            planner_raw = await _call_planner(
                provider, model, planner_messages,
                payload.max_tokens, provider.reasoning_effort)
            try:
                plan = parallel_writer.parse_parallel_plan(
                    planner_raw, episode_purpose=bundle.episode_purpose)
                break
            except ValueError as exc:
                plan_exc = exc
        outputs.append(generation_runs_svc.OutputSpec(channel="plan", text=planner_raw))
        if plan is None:
            status_str = "provider_error"
            error_detail = f"계획 형식이 올바르지 않습니다: {plan_exc}"
    except openai.APIError as exc:
        status_str = "provider_error"
        error_detail = _friendly_api_error(exc)
    except Exception as exc:  # noqa: BLE001
        status_str = "provider_error"
        error_detail = f"계획 생성 실패: {type(exc).__name__}"

    usage_id = usage_service.record(
        kind="plan", model=model, endpoint_name=provider.name,
        prompt_chars=sum(len(str(m.get("content") or "")) for m in planner_messages),
        completion_chars=sum(len(o.text) for o in outputs), db=db)
    run_id, output_ids = generation_runs_svc.save_run(
        surface="plan",
        project_id=pid,
        chapter_id=chapter.id,
        preset_id=None,
        model=model,
        reasoning_effort=provider.reasoning_effort,
        messages=planner_messages,
        manifest={
            "assistant": True,
            "context_metadata": context_metadata,
            "injected_lore": injected_lore,
            "injected_outline": injected_outline,
            "injected_foreshadows": injected_foreshadows,
            "episode_purpose": bundle.episode_purpose,
            "ai_usage_ids": [usage_id] if usage_id else [],
        },
        status=status_str,
        wall_ms=int((time.monotonic() - t0) * 1000),
        outputs=outputs,
        applied_rules=context_metadata.get("applied_rule_ids"),
        ai_usage_id=usage_id,
        db=db)
    if plan is None:
        raise HTTPException(status_code=502, detail=error_detail or "계획 생성 실패")
    return AssistantPlanNextResponse(
        project_id=pid,
        chapter_id=chapter.id,
        chapter_title=chapter.title,
        chapter_revision=int(chapter.revision or 0),
        episode_purpose=bundle.episode_purpose,
        plan=plan,
        run_id=run_id,
        plan_output_id=output_ids.get("plan"),
    )


_ASSISTANT_PROMPT = (
    "현재 회차의 제목·회차 목표·목차·세계관·인물 설정을 정본으로 삼아 "
    "다음 회차 본문을 완성된 한국어 웹소설 원고로 집필하라. "
    "이전 회차의 끝에서 자연스럽게 이어지고, 이번 회차의 핵심 사건과 "
    "인물 선택·대가를 행동과 대사로 보여줘라. 작품의 핵심 독자 약속과 "
    "중심 성장 엔진(관계·조직·규칙·직업 등)이 이번 회차에서 어떻게 움직이는지 "
    "장면으로 드러내되, 필요하지 않은 클리셰나 고정된 숫자 규칙을 추가하지 마라. "
    "회차 끝에는 다음 사건의 압력을 남겨라. 원고 본문만 출력하고 설명·요약·메타 문구는 쓰지 마라."
)


@router.post(
    "/projects/{pid}/assistant/generate-next",
    response_model=AssistantGenerateNextResponse,
)
async def assistant_generate_next(
    pid: int,
    payload: AssistantGenerateNextRequest,
    db: Session = Depends(get_db),
):
    """대상 회차의 초안을 생성해 반환한다 — 원고를 자동으로 쓰지 않는다.

    결과는 초안/미리보기(GenerationOutput channel=draft)로만 보존되며,
    원고 적용은 작가의 명시 액션(POST /generation-outputs/{id}/apply)만이
    수행한다. 기존 원고가 있는 회차도 대상이 될 수 있지만 덮어쓰지 않는다.
    approved_plan이 주어지면 planner 재호출 없이 그 계획을 계약으로 집필한다.
    """
    if db.get(Project, pid) is None:
        raise HTTPException(status_code=404, detail="project not found")
    chapter = _assistant_target_chapter(db, pid, payload.chapter_id)

    context = _assistant_context(
        chapter, payload.pov_character_id, payload.include_trend_pack
    )
    request = GenerateRequest(
        prompt_override=_ASSISTANT_PROMPT,
        context=context,
        params=GenerateParams(max_tokens=payload.max_tokens),
    )

    provider = _get_provider_or_503()
    model = _resolve_model(provider)
    client = llm.make_client(provider.base_url, None)
    t0 = time.monotonic()
    try:
        bundle = ai_context.build_context_bundle(
            db, ai_context.request_from_generate(request)
        )
        _, messages, injected_lore, injected_outline, injected_foreshadows, context_metadata = _build_messages(
            request, db, bundle=bundle
        )
        if payload.approved_plan is not None:
            # 작가가 승인한 계획을 계약으로 주입 — planner 재호출 없음
            try:
                parallel_writer.validate_plan_for_purpose(
                    payload.approved_plan, bundle.episode_purpose)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            messages[-1] = {
                "role": "user",
                "content": (
                    f"{messages[-1]['content']}\n\n"
                    "[작가 승인 집필 계획 — 반드시 따를 것]\n"
                    f"{payload.approved_plan.model_dump_json()}\n"
                    "계획의 장면 순서·objective·choice·cost·결말 의도를 "
                    "행동과 대사로 정확히 집필하라."
                ),
            }
        raw = await llm.complete_chat(
            client,
            model,
            messages,
            max_tokens=payload.max_tokens,
            reasoning_effort=provider.reasoning_effort,
        )
        content = str(raw or "").strip()
        if not content:
            raise HTTPException(status_code=502, detail="AI가 빈 원고를 반환했습니다.")

        uid = usage_service.record(
            kind="assistant_generate",
            model=model,
            endpoint_name=provider.name,
            prompt_chars=sum(len(str(message.get("content") or "")) for message in messages),
            completion_chars=len(content),
            db=db,
        )
        # E1 — 초안을 산출물로 보존한다(적용은 작가의 apply 액션만이 수행)
        outputs = [generation_runs_svc.OutputSpec(channel="draft", text=content)]
        if payload.approved_plan is not None:
            outputs.insert(0, generation_runs_svc.OutputSpec(
                channel="plan", text=payload.approved_plan.model_dump_json()))
        run_id, output_ids = generation_runs_svc.save_run(
            surface="assistant_generate",
            project_id=pid,
            chapter_id=chapter.id,
            preset_id=None,
            model=model,
            reasoning_effort=provider.reasoning_effort,
            messages=messages,
            manifest={
                "injected_lore": injected_lore,
                "injected_outline": injected_outline,
                "injected_foreshadows": injected_foreshadows,
                "context_metadata": context_metadata,
                "chapter_revision": int(chapter.revision or 0),
                "plan_source": ("approved" if payload.approved_plan is not None
                                else "none"),
                "plan_output_id": payload.plan_output_id,
                "draft_only": True,
                "ai_usage_ids": [uid] if uid else [],
            },
            status="completed",
            wall_ms=int((time.monotonic() - t0) * 1000),
            outputs=outputs,
            applied_rules=context_metadata.get("applied_rule_ids"),
            ai_usage_id=uid,
            db=db,
        )
        return {
            "project_id": pid,
            "chapter_id": chapter.id,
            "chapter_title": chapter.title,
            "revision": int(chapter.revision or 0),
            "content_md": content,
            "word_count_cache": count_novelpia_chars(content),
            "applied": False,
            "run_id": run_id,
            "draft_output_id": output_ids.get("draft"),
        }
    except openai.APIError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=_friendly_api_error(exc)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:  # noqa: BLE001 — 원클릭 경로의 사용자 안내
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail=f"다음 빈 회차 생성 실패: {type(exc).__name__}",
        ) from exc
    finally:
        await _close_llm_client(client)


# ---------- 집필 계획 (작가 검토 게이트) ----------
PLANNER_SYSTEM_PROMPT = (
    "너는 한국 웹소설의 장면 설계자다. 반드시 단일 유효 JSON 객체만 출력하라. 독자 약속과 장르 엔진이 장면 목표·선택·보상으로 드러나야 한다.\n"
    "2~4개 장면으로 나누고, 장면 order는 1부터 연속이어야 한다.\n"
    "각 장면에는 title, purpose, objective, choice, cost, required_beats, characters, opening_state, closing_hook, ending_intent를 포함하라.\n"
    "serial은 closing_hook을 채우고, volume_end는 closing_hook 또는 ending_intent를 채우며, series_finale의 마지막 장면은 ending_intent를 채워라.\n"
    "objective는 즉시 목표, choice는 핵심 선택, cost는 선택의 대가다.\n"
    "required_beats에는 objective·choice·cost가 행동과 판단으로 드러나는 비트를 포함하라.\n"
    "각 장면은 이전 장면의 결과가 다음 목표나 위험을 만드는 인과로 연결하고, 설명만 이어지는 장면을 만들지 마라.\n"
    "초반 회차라면 첫 장면에서 작품의 독자 약속과 주 장르를 실제 갈등으로 보여 주고, 선택된 장르 클리셰가 있으면 갈등·선택·보상에 기여하게 하라. 키워드만 나열하거나 컨텍스트 밖의 유행 요소를 추가하지 마라.\n"
    "정본 컨텍스트와 브리프 밖의 사건·고유명사를 새로 만들지 마라."
)


def _planner_messages(base_messages: list[dict]) -> list[dict]:
    """planner 호출 메시지 — /ai/plan과 generate-parallel이 같은 계약을 쓴다."""
    instruction = (
        f"{base_messages[-1]['content']}\n\n"
        "[병렬 Planner — 장면 계약 생성]\n"
        "현재 회차를 2~4개 장면으로 분해하라. 각 worker는 자기 계약만 집필한다.\n"
        '{"scenes":[{"order":1,"title":"...","purpose":"...",'
        '"objective":"...","choice":"...","cost":"...",'
        '"required_beats":["..."],"characters":["..."],'
        '"opening_state":"...","closing_hook":"...","ending_intent":"..."}]} 형식만 출력하라. '
        'serial은 closing_hook, series_finale 마지막 장면은 ending_intent를 반드시 채워라. 작품의 독자 약속을 첫 장면의 갈등으로 드러내고, 각 장면은 목표·장애물·선택·결과를 포함하며 장면마다 실제 변화가 생기게 하라.'
    )
    return [
        {"role": "system", "content": _append_generation_style(
            PLANNER_SYSTEM_PROMPT, base_messages[0]["content"])},
        {"role": "user", "content": instruction},
    ]


async def _call_planner(provider, model, planner_messages, max_tokens, effort):
    """planner 1회 호출 — 일시적 bridge 끊김은 새 client로 한 번 재시도한다."""
    for attempt in range(2):
        client = llm.make_client(provider.base_url, None)
        try:
            return await llm.complete_chat(
                client, model, planner_messages,
                max_tokens=max_tokens, reasoning_effort=effort)
        except Exception as exc:  # noqa: BLE001 — 일시적 bridge 끊김만 재시도
            if attempt == 0 and _is_retryable_bridge_error(exc):
                continue
            raise
        finally:
            await _close_llm_client(client)
    raise AssertionError("unreachable")


@router.post("/ai/plan", response_model=PlanResponse)
async def create_plan(payload: PlanRequest, db: Session = Depends(get_db)):
    """컨텍스트를 분석해 장면 계획만 생성한다 — 원고는 절대 쓰지 않는다.

    작가가 전체 계획을 한 번에 검토한 뒤 [수락하고 집필]이
    /ai/generate-parallel의 approved_plan으로 이어진다. 계획 산출물은
    생성 이력(channel=plan)에 보존돼 이후 분석의 재료가 된다.
    """
    base_payload = GenerateRequest(
        preset_id=payload.preset_id,
        prompt_override=payload.prompt_override,
        context=payload.context,
        params=payload.params,
    )
    bundle = ai_context.build_context_bundle(
        db, ai_context.request_from_generate(base_payload))
    provider = _get_provider_or_503()
    _, base_messages, injected_lore, injected_outline, injected_foreshadows, context_metadata = _build_messages(
        base_payload, db, bundle=bundle)
    model = _resolve_model(provider, payload.params.model)
    planner_messages = _planner_messages(base_messages)

    t0 = time.monotonic()
    status_str = "completed"
    outputs: list[generation_runs_svc.OutputSpec] = []
    error_detail: str | None = None
    plan: ParallelPlan | None = None
    try:
        plan_exc: ValueError | None = None
        for _attempt in range(2):  # 계약 밖 JSON은 일시적 — 1회 재시도
            planner_raw = await _call_planner(
                provider, model, planner_messages,
                payload.params.max_tokens, payload.generation_reasoning_effort)
            try:
                plan = parallel_writer.parse_parallel_plan(
                    planner_raw, episode_purpose=bundle.episode_purpose)
                break
            except ValueError as exc:
                plan_exc = exc
        outputs.append(generation_runs_svc.OutputSpec(channel="plan", text=planner_raw))
        if plan is None:
            status_str = "provider_error"
            error_detail = f"계획 형식이 올바르지 않습니다: {plan_exc}"
    except openai.APIError as exc:
        status_str = "provider_error"
        error_detail = _friendly_api_error(exc)
    except Exception as exc:  # noqa: BLE001 — 계획 단계도 사용자 안내로 변환
        status_str = "provider_error"
        error_detail = f"계획 생성 실패: {type(exc).__name__}"

    usage_id = usage_service.record(
        kind="plan", model=model, endpoint_name=provider.name,
        prompt_chars=sum(len(str(m.get("content") or "")) for m in planner_messages),
        completion_chars=sum(len(o.text) for o in outputs), db=db)
    run_id, output_ids = generation_runs_svc.save_run(
        surface="plan",
        project_id=payload.context.project_id,
        chapter_id=payload.context.chapter_id,
        preset_id=payload.preset_id,
        model=model,
        reasoning_effort=payload.generation_reasoning_effort,
        messages=planner_messages,
        manifest={
            "context_metadata": context_metadata,
            "injected_lore": injected_lore,
            "injected_outline": injected_outline,
            "injected_foreshadows": injected_foreshadows,
            "episode_purpose": payload.context.episode_purpose,
            "has_prompt_override": payload.prompt_override is not None,
            "brief": (payload.context.brief.model_dump()
                      if payload.context.brief else None),
            "ai_usage_ids": [usage_id] if usage_id else [],
        },
        status=status_str,
        wall_ms=int((time.monotonic() - t0) * 1000),
        outputs=outputs,
        applied_rules=context_metadata.get("applied_rule_ids"),
        ai_usage_id=usage_id,
        db=db)
    if plan is None:
        raise HTTPException(status_code=502, detail=error_detail or "계획 생성 실패")
    return PlanResponse(
        run_id=run_id,
        plan_output_id=output_ids.get("plan"),
        plan=plan,
        chapter_revision=bundle.chapter_revision,
        episode_purpose=bundle.episode_purpose,
    )


# ---------- 병렬 장면 집필 스트리밍 ----------
@router.post("/ai/generate-parallel")
async def generate_parallel(payload: ParallelGenerateRequest, db: Session = Depends(get_db)):
    """Medium planner/worker 병렬 집필 후 xhigh 감수만 수행한다."""
    base_payload = GenerateRequest(
        preset_id=payload.preset_id,
        prompt_override=payload.prompt_override,
        context=payload.context,
        params=payload.params,
    )
    bundle = ai_context.build_context_bundle(db, ai_context.request_from_generate(base_payload))
    provider = _get_provider_or_503()
    _, base_messages, injected_lore, injected_outline, injected_foreshadows, context_metadata = _build_messages(
        base_payload, db, bundle=bundle)
    model = _resolve_model(provider, payload.params.model)

    reviewer_cfg = _review_backend(provider, payload.review, payload.params.max_tokens)
    reviewer_model = reviewer_cfg["model"]
    reviewer_provider = reviewer_cfg["provider_name"]
    reviewer_effort = reviewer_cfg["reasoning_effort"]

    # 작가 승인 계획이면 planner 호출 없이 그 계획을 그대로 실행한다.
    # 계획이 요청 컨텍스트의 목적과 어긋나면 스트림을 열기 전 422로 거절한다.
    if payload.approved_plan is not None:
        try:
            parallel_writer.validate_plan_for_purpose(
                payload.approved_plan, bundle.episode_purpose)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    async def event_stream():
        yield {
            "event": "parallel_start",
            "data": json.dumps({
                "model": model,
                "generation_reasoning_effort": payload.generation_reasoning_effort,
                "review_model": reviewer_model,
                "review_provider": reviewer_provider,
                "review_reasoning_effort": reviewer_effort,
                "worker_limit": payload.worker_limit,
                "injected_lore": injected_lore,
                "injected_outline": injected_outline,
                "injected_foreshadows": injected_foreshadows,
                "context_metadata": context_metadata,
            }, ensure_ascii=False),
        }
        t0 = time.monotonic()
        outputs: list[generation_runs_svc.OutputSpec] = []
        usage_ids: list[int] = []
        saved: dict = {"result": None}
        run_status = "completed"
        planner_debug: dict = {}

        def _finalize():
            # E1 생성 이력 — 실패해도 스트림을 막지 않는다(best-effort)
            if saved["result"] is None:
                try:
                    saved["result"] = generation_runs_svc.save_run(
                    surface="generate_parallel",
                    project_id=payload.context.project_id,
                    chapter_id=payload.context.chapter_id,
                    preset_id=payload.preset_id,
                    model=model,
                    reasoning_effort=payload.generation_reasoning_effort,
                    messages=base_messages,
                    manifest={
                        "context_metadata": context_metadata,
                        "injected_lore": injected_lore,
                        "injected_outline": injected_outline,
                        "injected_foreshadows": injected_foreshadows,
                        "episode_purpose": payload.context.episode_purpose,
                        "scene_id": payload.context.scene_id,
                        "worker_limit": payload.worker_limit,
                        "plan_source": ("approved" if payload.approved_plan is not None
                                        else "planner"),
                        "plan_output_id": payload.plan_output_id,
                        "has_prompt_override": payload.prompt_override is not None,
                        "brief": (payload.context.brief.model_dump()
                                  if payload.context.brief else None),
                        "ai_usage_ids": usage_ids,
                        "planner_debug": planner_debug or None,
                    },
                    status=run_status,
                    wall_ms=int((time.monotonic() - t0) * 1000),
                    outputs=outputs,
                    applied_rules=context_metadata.get("applied_rule_ids"),
                    ai_usage_id=usage_ids[0] if usage_ids else None,
                    db=db)
                except Exception:  # noqa: BLE001
                    saved["result"] = (None, {})
            return saved["result"]

        gen_failed = False
        try:
            try:
                planner_messages = None
                if payload.approved_plan is None:
                    planner_messages = _planner_messages(base_messages)
                    plan = None
                    last_plan_exc: ValueError | None = None
                    # LLM이 가끔 계약 밖 JSON을 반환한다 — 검증 실패는 1회 재시도.
                    for _attempt in range(2):
                        planner_raw = await _call_planner(
                            provider, model, planner_messages,
                            payload.params.max_tokens,
                            payload.generation_reasoning_effort)
                        try:
                            plan = parallel_writer.parse_parallel_plan(
                                planner_raw, episode_purpose=bundle.episode_purpose)
                            break
                        except ValueError as exc:  # ValidationError 포함
                            last_plan_exc = exc
                            planner_debug["parse_error"] = {
                                "detail": str(exc)[:1000],
                                "raw": planner_raw[:4000],
                            }
                    if plan is None:
                        raise last_plan_exc or ValueError("parallel plan parse failed")
                else:
                    # 작가가 승인한 계획을 그대로 실행 — planner 재호출 없음
                    plan = payload.approved_plan
                    planner_raw = plan.model_dump_json()
                outputs.append(generation_runs_svc.OutputSpec(channel="plan", text=planner_raw))
                yield {
                    "event": "planner_done",
                    "data": json.dumps({
                        "scene_count": len(plan.scenes),
                        "scenes": [{"order": s.order, "title": s.title} for s in plan.scenes],
                    }, ensure_ascii=False),
                }
                for scene in plan.scenes:
                    yield {
                        "event": "worker_start",
                        "data": json.dumps({"order": scene.order, "title": scene.title},
                                           ensure_ascii=False),
                    }

                async def run_scene(scene):
                    contract = json.dumps(scene.model_dump(), ensure_ascii=False)
                    worker_prompt = (
                        f"{base_messages[-1]['content']}\n\n"
                        "[병렬 Worker — 자기 장면만 집필]\n"
                        f"[장면 계약]\n{contract}\n"
                        "opening_state에서 시작하고 objective를 향해 진행하라. "
                        "choice를 인물의 행동과 판단으로 보여주고 cost를 실제 위험·손실로 드러내라. "
                        "마무리는 episode_purpose와 장면 계약의 closing_hook 또는 ending_intent를 따른다. "
                        "다른 장면을 대신 쓰지 말고 정본 컨텍스트 밖의 사실을 만들지 마라. "
                        "장면 계약·JSON·[감수]·[수정본] 같은 메타 문구 없이 원고 본문만 출력하라."
                    )
                    worker_messages = [
                        {"role": "system", "content": base_messages[0]["content"]},
                        {"role": "user", "content": worker_prompt},
                    ]
                    # 동시 worker가 하나의 AsyncOpenAI 연결을 공유하면 bridge의
                    # HTTP/2 stream 상태가 서로 영향을 주어 RemoteProtocolError가
                    # 발생할 수 있다. worker마다 짧은 수명의 독립 client를 쓴다.
                    for attempt in range(2):
                        worker_client = llm.make_long_running_client(provider.base_url, None)
                        try:
                            text = await llm.complete_chat(
                                worker_client, model, worker_messages,
                                max_tokens=payload.params.max_tokens,
                                reasoning_effort=payload.generation_reasoning_effort,
                            )
                            break
                        except Exception as exc:  # noqa: BLE001 — 일시적 bridge 끊김만 재시도
                            if attempt == 0 and _is_retryable_bridge_error(exc):
                                continue
                            raise
                        finally:
                            await _close_llm_client(worker_client)
                    # 콘텐츠 계약 위반(마커 누출·빈 장면·분량 초과)은 1회 재집필로 회복한다
                    content_issues = parallel_writer.validate_scene_result(scene, text)
                    if content_issues:
                        repair_messages = list(worker_messages) + [
                            {"role": "assistant", "content": text},
                            {"role": "user", "content": (
                                "직전 장면 원고가 계약을 위반했다: "
                                + "; ".join(content_issues)
                                + ". 장면 계약을 지키며 원고 본문만 다시 출력하라.")},
                        ]
                        repair_client = llm.make_long_running_client(provider.base_url, None)
                        try:
                            repaired = await llm.complete_chat(
                                repair_client, model, repair_messages,
                                max_tokens=payload.params.max_tokens,
                                reasoning_effort=payload.generation_reasoning_effort,
                            )
                        finally:
                            await _close_llm_client(repair_client)
                        if not parallel_writer.validate_scene_result(scene, repaired):
                            text = repaired
                    return parallel_writer.SceneResult(
                        order=scene.order, title=scene.title, text=text,
                    )

                results = await parallel_writer.run_parallel_workers(
                    plan.scenes, run_scene, payload.worker_limit,
                )
                quality_issues = parallel_writer.validate_results(results, plan.scenes)
                if quality_issues:
                    raise ValueError("parallel draft quality validation failed: " + "; ".join(quality_issues))
                review_source = parallel_writer.build_review_source(results, plan.scenes)
                for result in results:
                    # E1 — 장면별 worker 산출물도 보존(스티칭 결함 분석의 재료)
                    outputs.append(generation_runs_svc.OutputSpec(
                        channel="worker", text=result.text, scene_order=result.order))
                    yield {
                        "event": "worker_done",
                        "data": json.dumps({
                            "order": result.order,
                            "title": result.title,
                            "chars": len(result.text),
                        }, ensure_ascii=False),
                    }
                assembled = parallel_writer.assemble_scene_results(results)
                outputs.append(generation_runs_svc.OutputSpec(channel="draft", text=assembled))
                if planner_messages is not None:
                    # 승인 계획 경로는 planner 호출이 없으므로 사용량도 기록하지 않는다
                    uid = usage_service.record(
                        kind="parallel_plan", model=model, endpoint_name=provider.name,
                        prompt_chars=sum(len(str(m.get("content") or "")) for m in planner_messages),
                        completion_chars=len(planner_raw), db=db,
                    )
                    if uid is not None:
                        usage_ids.append(uid)
                uid = usage_service.record(
                    kind="parallel_generate", model=model, endpoint_name=provider.name,
                    prompt_chars=sum(len(str(m.get("content") or "")) for m in base_messages),
                    completion_chars=len(assembled), db=db,
                )
                if uid is not None:
                    usage_ids.append(uid)
                yield {"event": "message", "data": json.dumps({"delta": assembled}, ensure_ascii=False)}
            except openai.APIError as exc:
                gen_failed = True
                run_status = "provider_error"
                yield {
                    "event": "parallel_error",
                    "data": json.dumps({"stage": "generation", "detail": _friendly_api_error(exc)},
                                       ensure_ascii=False),
                }
            except Exception as exc:  # noqa: BLE001 — 병렬 단계 전체를 사용자 이벤트로 변환
                gen_failed = True
                run_status = "provider_error"
                yield {
                    "event": "parallel_error",
                    "data": json.dumps({
                        "stage": "generation",
                        "detail": f"병렬 집필 실패: {type(exc).__name__}: {str(exc)[:300]}",
                    }, ensure_ascii=False),
                }

            if gen_failed:
                run_id, output_ids = _finalize()
                yield {
                    "event": "generation_saved",
                    "data": json.dumps(
                        {"run_id": run_id, "outputs": output_ids},
                        ensure_ascii=False,
                    ),
                }
                return

            yield {
                "event": "review_start",
                "data": json.dumps({
                    "model": reviewer_model,
                    "provider": reviewer_provider,
                    "reasoning_effort": reviewer_effort,
                }, ensure_ascii=False),
            }
            review_messages = [
                {"role": "system", "content": _append_generation_style(PARALLEL_REVIEW_SYSTEM_PROMPT, base_messages[0]["content"])},
                {"role": "user", "content": (
                    f"{base_messages[-1]['content']}\n\n[장면별 조립 원고 — 감수 전용 메타데이터]\n{review_source}\n\n"
                    "다음 항목을 반드시 확인하라: episode_purpose에 맞는 마무리, 장면별 purpose·required_beats·closing_hook·ending_intent 달성, "
                    "장면 전환의 인과, 주인공의 objective·choice·cost가 행동과 판단으로 드러나는지, "
                    "캐릭터·세계관·시간축·위치·미회수 복선과 충돌하는지. "
                    "지적이 끝나면 [수정본] 마커 뒤에 수정 원고 전체를 출력하라.")},
            ]
            review_chars = 0
            channel_parts: dict[str, list[str]] = {"review": [], "refined": []}
            try:
                # 감수는 원고 조립·message 이벤트 뒤의 부가 단계다. 첫 토큰 전에
                # bridge가 끊기면 새 client로 한 번 재시도하고, 재시도까지 실패해도
                # 이미 조립된 원고를 실패로 되돌리지 않는다.
                feed_review, flush_review = _split_review_stream()
                for attempt in range(2):
                    reviewer_client = (
                        None if reviewer_cfg["backend"] == "agy"
                        else llm.make_long_running_client(provider.base_url, None))
                    attempt_chars = 0
                    try:
                        async for delta in _review_stream(
                                reviewer_cfg, review_messages, reviewer_client):
                            attempt_chars += len(delta)
                            review_chars += len(delta)
                            async for kind, chunk in feed_review(delta):
                                channel_parts[kind].append(chunk)
                                yield {"event": kind,
                                       "data": json.dumps({"delta": chunk}, ensure_ascii=False)}
                        async for kind, chunk in flush_review():
                            channel_parts[kind].append(chunk)
                            yield {"event": kind,
                                   "data": json.dumps({"delta": chunk}, ensure_ascii=False)}
                        break
                    except Exception as exc:  # noqa: BLE001 — 재시도 가능 transport 판별
                        if attempt == 0 and attempt_chars == 0 and (
                                reviewer_cfg["backend"] == "agy"
                                or _is_retryable_bridge_error(exc)):
                            continue
                        raise
                    finally:
                        if reviewer_client is not None:
                            await _close_llm_client(reviewer_client)
                if review_chars:
                    uid = usage_service.record(
                        kind="parallel_review", model=reviewer_model,
                        endpoint_name=reviewer_provider,
                        prompt_chars=sum(len(str(m.get("content") or "")) for m in review_messages),
                        completion_chars=review_chars, db=db,
                    )
                    if uid is not None:
                        usage_ids.append(uid)
            except openai.APIError as exc:
                yield {"event": "parallel_error",
                       "data": json.dumps({"stage": "review", "detail": _friendly_api_error(exc)},
                                          ensure_ascii=False)}
            except Exception as exc:  # noqa: BLE001
                yield {"event": "parallel_error",
                       "data": json.dumps({
                           "stage": "review", "detail": f"감수 실패: {type(exc).__name__}",
                       }, ensure_ascii=False)}
            finally:
                for ch in ("review", "refined"):
                    if channel_parts[ch]:
                        outputs.append(generation_runs_svc.OutputSpec(
                            channel=ch, text="".join(channel_parts[ch])))
        except (GeneratorExit, asyncio.CancelledError):
            run_status = "aborted"
            raise
        finally:
            run_id, output_ids = _finalize()
        # 종료 계약 — generation_saved(additive) 뒤 기존 done 이벤트
        yield {"event": "generation_saved",
               "data": json.dumps({"run_id": run_id, "outputs": output_ids},
                                  ensure_ascii=False)}

        yield {"event": "done", "data": "[DONE]"}

    return EventSourceResponse(_with_generation_heartbeat(event_stream()))


# ---------- 감수 패스 (백그라운드 병렬) ----------
@router.post("/ai/review")
async def review(payload: ReviewRequest, db: Session = Depends(get_db)):
    """초안 원고를 감수하고 수정본까지 스트리밍하는 독립 엔드포인트.

    생성(/ai/generate)과 분리되어 있어 프론트가 비동기로 발사한다 —
    감수(저속 xhigh 등)가 진행되는 동안에도 다음 회차 생성을 계속할 수 있다.
    SSE 이벤트: review_start / review(지적) / refined(수정본) / review_error / done.
    """
    provider = _get_provider_or_503()
    review_cfg = _review_backend(provider, payload, payload.max_tokens)
    model = review_cfg["model"]
    provider_name = review_cfg["provider_name"]
    reasoning_effort = review_cfg["reasoning_effort"]
    client = (llm.make_long_running_client(provider.base_url, None)
              if review_cfg["backend"] == "bridge" else None)
    review_messages = [
        {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
        {"role": "user", "content": f"[초안 원고]\n{payload.draft}"},
    ]

    async def event_stream():
        yield {"event": "review_start",
               "data": json.dumps({"model": model, "provider": provider_name,
                                   "reasoning_effort": reasoning_effort},
                                  ensure_ascii=False)}
        t0 = time.monotonic()
        outputs: list[generation_runs_svc.OutputSpec] = []
        usage_ids: list[int] = []
        saved: dict = {"result": None}
        run_status = "completed"

        def _finalize():
            # E1 생성 이력 — 실패해도 스트림을 막지 않는다(best-effort)
            if saved["result"] is None:
                try:
                    saved["result"] = generation_runs_svc.save_run(
                    surface="review",
                    project_id=payload.project_id,
                    chapter_id=payload.chapter_id,
                    preset_id=None,
                    model=model,
                    reasoning_effort=reasoning_effort,
                    messages=review_messages,
                    manifest={"ai_usage_ids": usage_ids},
                    status=run_status,
                    wall_ms=int((time.monotonic() - t0) * 1000),
                    outputs=outputs,
                    ai_usage_id=usage_ids[0] if usage_ids else None,
                    db=db)
                except Exception:  # noqa: BLE001
                    saved["result"] = (None, {})
            return saved["result"]

        review_chars = 0
        channel_parts: dict[str, list[str]] = {"review": [], "refined": []}
        try:
            try:
                feed, flush_review = _split_review_stream()
                async for delta in _review_stream(review_cfg, review_messages, client):
                    review_chars += len(delta)
                    async for event_name, chunk in feed(delta):
                        channel_parts.setdefault(event_name, []).append(chunk)
                        yield {"event": event_name,
                               "data": json.dumps({"delta": chunk}, ensure_ascii=False)}
                async for event_name, chunk in flush_review():
                    channel_parts.setdefault(event_name, []).append(chunk)
                    yield {"event": event_name,
                           "data": json.dumps({"delta": chunk}, ensure_ascii=False)}
            except openai.APIError as exc:
                run_status = "provider_error"
                yield {"event": "review_error",
                       "data": json.dumps({"detail": _friendly_api_error(exc)}, ensure_ascii=False)}
            except Exception as exc:  # noqa: BLE001
                run_status = "provider_error"
                yield {"event": "review_error",
                       "data": json.dumps({"detail": f"감수 실패: {type(exc).__name__}"},
                                          ensure_ascii=False)}
            else:
                if review_chars:
                    uid = usage_service.record(
                        kind="review", model=model, endpoint_name=provider_name,
                        prompt_chars=sum(len(str(m.get("content") or "")) for m in review_messages),
                        completion_chars=review_chars, db=db)
                    if uid is not None:
                        usage_ids.append(uid)
            finally:
                for ch in ("review", "refined"):
                    if channel_parts.get(ch):
                        outputs.append(generation_runs_svc.OutputSpec(
                            channel=ch, text="".join(channel_parts[ch])))
        except (GeneratorExit, asyncio.CancelledError):
            run_status = "aborted"
            raise
        finally:
            run_id, output_ids = _finalize()
        yield {"event": "generation_saved",
               "data": json.dumps({"run_id": run_id, "outputs": output_ids},
                                  ensure_ascii=False)}
        yield {"event": "done", "data": "[DONE]"}

    return EventSourceResponse(_with_generation_heartbeat(
        event_stream(), cleanup=lambda: _close_llm_client(client)))
