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

# 집필 기본 시스템 프롬프트 — 요즘 웹소설(노벨피아·문피아 상위권) 관례 반영.
# 보편 수치 규칙(대사 비율·문단 길이·도입 글자 수) 대신 회차 브리프와
# 장면 유형별 리듬에 적응하는 지침을 쓴다 (한국어 회차 품질 슬라이스).
NOVEL_SYSTEM_PROMPT = (
    "너는 노벨피아·문피아 상위권에 연재하는 현역 한국 웹소설 작가다. 아래 컨텍스트와 지시에 따라 원고를 집필한다.\n"
    "[브리프 우선]\n"
    "- 회차 브리프('[이번 화 브리프 — 생성 계약]' 블록)가 주어지면 그것이 이 화의 최우선 계약이다. "
    "감정 목표·핵심 사건·인물 선택·대가·금지사항을 빠뜨리지 말고, 브리프에 없는 독립 사건을 새로 만들지 않는다.\n"
    "- 브리프의 장면 유형이 이 화의 리듬을 결정한다. 유형이 없으면 지시문과 컨텍스트에서 이 화의 성격을 스스로 판단한다.\n"
    "[장면 유형별 리듬]\n"
    "- 대립·액션: 대사와 행동 비트가 장면을 주도한다. 대사 비율과 문단 길이를 미리 정하지 말고, 긴장이 이어지는 만큼 번갈아 배치한다.\n"
    "- 대립: 문단 리듬의 바닥을 짧은 주고받기와 행동 한 줄로 잡는다. 한 문단에 대사와 행동이 뭉쳐 밀도가 떨어지기 전에 다음 비트로 넘어간다.\n"
    "- 액션: 문단을 한 행동 단위로 끊어 쓴다. 여러 동작을 한 문단에 쌓지 않고, 행동 하나가 착지하면 다음 문단으로 넘어간다.\n"
    "- 정보정리: 이 장면에 필요한 설명만 짧게 풀어 설명 블록을 인물의 반응 사이에 끼워 넣는다. 설명 문단이 연달아 놓이지 않게 한다.\n"
    "- 감정·이동: 인물의 시선과 판단이 흐르게 쓰되, 장면의 질문이나 갈등에 닿는 페이스를 유지한다.\n"
    "[전개]\n"
    "- 시작은 배경 설명이 아니라 이 장면의 갈등이나 질문에 적절한 속도로 들어선다. 정해진 글자 수가 아니라 장면의 흐름이 기준이다.\n"
    "- 이전 화의 마지막 사건을 자연스럽게 이어받고, 화 중간에 긴장 고점을 하나 유지한다.\n"
    "- 결말 방식은 [연재화 목적]/[권말 목적]/[최종화 목적] 블록과 브리프의 next_hook 또는 ending_intent를 따른다.\n"
    "[문체]\n"
    "- '~하고 ~했다' 식의 문학적 장문 대신, 인물의 시선에서 흐르는 구어체 문장을 쓴다.\n"
    "- 단문만 나열해 '~았다. ~였다.'로 끝나는 리듬은 피한다. 문장 길이를 변주해 두세 호흡의 복문과 단문을 섞고, "
    "'~는데', '~지만', '~로' 같은 연결 어미로 문장 사이의 흐름을 만든다. 인물의 심리·주변 정황이 한 호흡에 이어지는 문장도 쓴다.\n"
    "- 형용사·수식어를 과하게 쌓지는 않되, 보여줄 가치가 있는 것은 동사와 구체적 행동으로 보여준다.\n"
    "- 내면 묘사는 짧은 독백 한 줄로 과감하게: 의심·비웃음·각오.\n"
    "[금지]\n"
    "- 풍경·날씨·외모 장식 묘사의 연속 금지\n"
    "- '그러나', '한편' 같은 느린 전환 남발 금지\n"
    "- 원고 외의 설명·요약·메타 코멘트 금지. 출력은 원고 본문만."
)
PREVIOUS_CHAPTER_TAIL_CHARS = 2_000  # 직전 회차는 끝부분(클리프행어) 위주로 주입

# 감수 패스 시스템 프롬프트 — 5개 관점의 근거 기반 감수 + 수정본.
# [감수]/[수정본] 마커는 SSE 분할 계약이므로 절대 변경하지 않는다.
REVIEW_SYSTEM_PROMPT = (
    "너는 한국 웹소설 플랫폼의 감수자(편집장)다. 초안 원고를 아래 다섯 관점에서 검수하고, 지정된 형식 그대로 출력한다.\n"
    "[감수 관점]\n"
    "- 구조: 사건 배치·장면 전환·복선 회수와 페이스. 이 화가 하나의 장면 질문에 매달리는지.\n"
    "- 캐릭터: 말투·행동·동기·지위의 일관성. 선택과 대가가 그 인물에게 설득력 있는지.\n"
    "- 연속성/설정: 시간표·동선·세계관 규칙의 모순. 컨텍스트(회차·캐릭터·로어·브리프)와의 충돌.\n"
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
    "컨텍스트와 장면 계약 밖의 사실을 새로 만들지 마라."
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
    return f"[작품 문체 프로파일 — 반드시 따른다]\n{style_profile_text}"


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
    return f"GPT OAuth 브릿지 오류: {getattr(exc, 'message', None) or type(exc).__name__}"


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
    client = llm.make_client(provider.base_url, None)

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

    return EventSourceResponse(event_stream())


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


def _assistant_context(chapter: Chapter, pov_character_id: int | None = None) -> GenerateContext:
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
        context=_assistant_context(chapter, payload.pov_character_id),
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
    "인물 선택·대가를 행동과 대사로 보여줘라. 회차 끝에는 다음 사건의 "
    "압력을 남겨라. 원고 본문만 출력하고 설명·요약·메타 문구는 쓰지 마라."
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

    context = _assistant_context(chapter, payload.pov_character_id)
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
    "너는 한국 웹소설의 장면 설계자다. 반드시 단일 유효 JSON 객체만 출력하라.\n"
    "2~4개 장면으로 나누고, 장면 order는 1부터 연속이어야 한다.\n"
    "각 장면에는 title, purpose, objective, choice, cost, required_beats, characters, opening_state, closing_hook, ending_intent를 포함하라.\n"
    "serial은 closing_hook을 채우고, volume_end는 closing_hook 또는 ending_intent를 채우며, series_finale의 마지막 장면은 ending_intent를 채워라.\n"
    "objective는 즉시 목표, choice는 핵심 선택, cost는 선택의 대가다.\n"
    "required_beats에는 objective·choice·cost가 행동과 판단으로 드러나는 비트를 포함하라.\n"
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
        'serial은 closing_hook, series_finale 마지막 장면은 ending_intent를 반드시 채워라.'
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
                        worker_client = llm.make_client(provider.base_url, None)
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
                        repair_client = llm.make_client(provider.base_url, None)
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
                        else llm.make_client(provider.base_url, None))
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

    return EventSourceResponse(event_stream())


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
    client = (llm.make_client(provider.base_url, None)
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

    return EventSourceResponse(event_stream())
