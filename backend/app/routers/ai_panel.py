"""AI 패널 라우터 (사양 §5 M4, Sprint 3).

- AiEndpoint CRUD — api_key는 저장 시 암호화(NFR-202), 어떤 응답에도 평문 미반환
- PromptPreset CRUD
- POST /ai/generate — openai SDK(base_url 오버라이드) SSE 스트리밍 (FR-405)
"""
import inspect
import json

import openai
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.models import AiEndpoint, Chapter, Character, LoreEntry, PromptPreset
from app.schemas import (
    AiEndpointCreate,
    AiEndpointOut,
    AiEndpointUpdate,
    GenerateRequest,
    PromptPresetCreate,
    PromptPresetOut,
    PromptPresetUpdate,
)
from app.services import llm

router = APIRouter()


# ---------- helpers ----------
def _get_endpoint_or_404(eid: int, db: Session) -> AiEndpoint:
    endpoint = db.get(AiEndpoint, eid)
    if endpoint is None:
        raise HTTPException(status_code=404, detail="endpoint not found")
    return endpoint


def _get_preset_or_404(pid: int, db: Session) -> PromptPreset:
    preset = db.get(PromptPreset, pid)
    if preset is None:
        raise HTTPException(status_code=404, detail="preset not found")
    return preset


def _to_out(endpoint: AiEndpoint) -> AiEndpointOut:
    """평문·암호문 모두 절대 응답에 포함하지 않는다(NFR-202)."""
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


def _clear_default_flag(db: Session, exclude_id: int | None = None) -> None:
    stmt = select(AiEndpoint).where(AiEndpoint.is_default.is_(True))
    for row in db.scalars(stmt):
        if exclude_id is None or row.id != exclude_id:
            row.is_default = False


def _resolve_model(endpoint: AiEndpoint, requested: str | None) -> str:
    model = requested or endpoint.default_model
    if not model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="모델이 지정되지 않았습니다. 엔드포인트의 기본 모델을 설정하거나 params.model을 전달하세요.",
        )
    return model


AUTO_LORE_MAX = 12  # 자동 매칭 상한 — 프롬프트 과다 팽창 방지
AUTO_LORE_MIN_KEYWORD = 2  # 1글자 키워드는 오탐이 많아 제외


def _auto_match_lore(db: Session, chapter: Chapter) -> list[LoreEntry]:
    """본문에 키워드·제목이 등장하는 로어 항목을 자동 선별한다(백로그 P1).

    키워드·제목의 부분일치(casefold) 기준이며 2글자 미만 키워드는 오탐을
    줄이기 위해 무시한다. 정밀 검색은 FTS를 쓸 수 있지만 소규모 항목 수에서는
    순회가 더 단순하고 충분하다.
    """
    content = (chapter.content_md or "").casefold()
    if not content.strip():
        return []
    entries = db.scalars(
        select(LoreEntry).where(LoreEntry.project_id == chapter.project_id)
    ).all()
    matched: list[LoreEntry] = []
    for entry in entries:
        needles = [entry.title.casefold()] if entry.title else []
        for kw in entry.keywords or []:
            if isinstance(kw, str) and len(kw) >= AUTO_LORE_MIN_KEYWORD:
                needles.append(kw.casefold())
        if any(n and n in content for n in needles):
            matched.append(entry)
    return matched[:AUTO_LORE_MAX]


def _build_context_blocks(payload: GenerateRequest, db: Session) -> list[str]:
    """FR-404 — 요청된 컨텍스트(회차/캐릭터/로어북)를 프롬프트 블록으로 조립."""
    blocks: list[str] = []
    ctx = payload.context
    if ctx.chapter_id is not None:
        chapter = db.get(Chapter, ctx.chapter_id)
        if chapter is None:
            raise HTTPException(status_code=404, detail="chapter not found")
        blocks.append(f"[현재 회차: {chapter.title}]\n{chapter.content_md}")
    if ctx.character_ids:
        chars = db.scalars(
            select(Character).where(Character.id.in_(ctx.character_ids))
        ).all()
        for ch in chars:
            parts = [f"[캐릭터: {ch.name}]"]
            for field in ("role", "appearance", "personality", "speech_style", "background"):
                value = getattr(ch, field, None)
                if value:
                    parts.append(f"{field}: {value}")
            blocks.append("\n".join(parts))
    lore_ids = list(ctx.lore_ids or [])
    if ctx.auto_lore and ctx.chapter_id is not None:
        chapter = db.get(Chapter, ctx.chapter_id)
        if chapter is not None:
            explicit = (
                db.scalars(select(LoreEntry).where(LoreEntry.id.in_(lore_ids))).all()
                if lore_ids
                else []
            )
            known = {e.id for e in explicit}
            for entry in _auto_match_lore(db, chapter):
                if entry.id not in known:
                    lore_ids.append(entry.id)
                    known.add(entry.id)
    if lore_ids:
        entries = db.scalars(select(LoreEntry).where(LoreEntry.id.in_(lore_ids))).all()
        for entry in entries:
            blocks.append(f"[세계관: {entry.title}]\n{entry.content or ''}")
    return blocks


def _build_messages(payload: GenerateRequest, db: Session) -> tuple[str, list[dict]]:
    """프리셋 템플릿 + 컨텍스트 + override → chat messages. 반환: (model_hint, messages)"""
    sections = ["다음 컨텍스트를 참고해 작성하세요.", *_build_context_blocks(payload, db)]
    context_text = "\n\n".join(p for p in sections if p)

    instruction = payload.prompt_override
    if payload.preset_id is not None:
        preset = _get_preset_or_404(payload.preset_id, db)
        instruction = f"{preset.template_text}\n\n{instruction}" if instruction else preset.template_text
    if not instruction:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="preset_id 또는 prompt_override 중 하나는 필요합니다.")

    user_content = f"{context_text}\n\n---\n\n지시:\n{instruction}"
    return "default", [{"role": "user", "content": user_content}]


def _friendly_api_error(exc: openai.APIError) -> str:
    """FR-408 — API 오류를 사용자가 이해 가능한 안내로 변환."""
    if isinstance(exc, openai.APITimeoutError):
        return "엔드포인트 응답 시간 초과. 로컬 모델이라면 로딩 상태를, 클라우드라면 네트워크를 확인하세요."
    if isinstance(exc, openai.APIConnectionError):
        return "엔드포인트에 연결할 수 없습니다. base_url과 서버 실행 여부를 확인하세요."
    if isinstance(exc, openai.AuthenticationError):
        return "인증 실패(401). api_key를 확인하세요."
    if isinstance(exc, openai.NotFoundError):
        return "모델 또는 경로를 찾을 수 없습니다. base_url 끝 /v1 여부와 모델 이름을 확인하세요."
    if isinstance(exc, openai.RateLimitError):
        return "요청 한도 초과(429). 잠시 후 다시 시도하세요."
    return f"엔드포인트 오류: {getattr(exc, 'message', None) or type(exc).__name__}"


# ---------- AiEndpoint CRUD ----------
@router.get("/ai/endpoints", response_model=list[AiEndpointOut])
def list_endpoints(db: Session = Depends(get_db)):
    rows = db.scalars(select(AiEndpoint).order_by(AiEndpoint.id)).all()
    return [_to_out(r) for r in rows]


@router.post("/ai/endpoints", response_model=AiEndpointOut,
             status_code=status.HTTP_201_CREATED)
def create_endpoint(payload: AiEndpointCreate, db: Session = Depends(get_db)):
    from app.services.crypto import get_cipher

    endpoint = AiEndpoint(
        name=payload.name,
        base_url=payload.base_url,
        api_key_encrypted=get_cipher().encrypt(payload.api_key) if payload.api_key else None,
        default_model=payload.default_model,
        temperature=payload.temperature,
        is_default=False,
    )
    if payload.is_default:
        _clear_default_flag(db)
        endpoint.is_default = True
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return _to_out(endpoint)


@router.patch("/ai/endpoints/{eid}", response_model=AiEndpointOut)
def update_endpoint(eid: int, payload: AiEndpointUpdate, db: Session = Depends(get_db)):
    from app.services.crypto import get_cipher

    endpoint = _get_endpoint_or_404(eid, db)
    data = payload.model_dump(exclude_unset=True)
    if "api_key" in data:
        raw_key = data.pop("api_key")
        endpoint.api_key_encrypted = get_cipher().encrypt(raw_key) if raw_key else None
    if data.pop("is_default", None):
        _clear_default_flag(db, exclude_id=eid)
        endpoint.is_default = True
    for field, value in data.items():
        setattr(endpoint, field, value)
    db.commit()
    db.refresh(endpoint)
    return _to_out(endpoint)


@router.delete("/ai/endpoints/{eid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_endpoint(eid: int, db: Session = Depends(get_db)):
    endpoint = _get_endpoint_or_404(eid, db)
    db.delete(endpoint)
    db.commit()


@router.get("/ai/endpoints/{eid}/models")
async def list_remote_models(eid: int, db: Session = Depends(get_db)):
    """GET {base_url}/models 프록시 (사양 §5 M4) — api_key 미노출."""
    endpoint = _get_endpoint_or_404(eid, db)
    client = llm.make_client(endpoint.base_url, endpoint.api_key_encrypted)
    try:
        page = client.models.list()
        if inspect.isawaitable(page):
            page = await page
        return {"data": [{"id": m.id} for m in page.data]}
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


# ---------- AI 생성 스트리밍 ----------
@router.post("/ai/generate")
async def generate(payload: GenerateRequest, db: Session = Depends(get_db)):
    endpoint = _get_endpoint_or_404(payload.endpoint_id, db)
    _, messages = _build_messages(payload, db)
    model = _resolve_model(endpoint, payload.params.model)
    temperature = payload.params.temperature
    if temperature is None:
        temperature = endpoint.temperature

    client = llm.make_client(endpoint.base_url, endpoint.api_key_encrypted)

    async def event_stream():
        # 시작 이벤트 — 프론트가 스트림 개시를 확정할 수 있다
        yield {"event": "start", "data": json.dumps({"model": model}, ensure_ascii=False)}
        try:
            async for delta in llm.stream_chat(client, model, messages,
                                               temperature=temperature,
                                               max_tokens=payload.params.max_tokens,
                                               reasoning_effort=endpoint.reasoning_effort):
                yield {"event": "message", "data": json.dumps({"delta": delta}, ensure_ascii=False)}
        except openai.APIError as exc:
            yield {"event": "error",
                   "data": json.dumps({"detail": _friendly_api_error(exc)}, ensure_ascii=False)}
            return
        except Exception as exc:  # noqa: BLE001 — 스트림 내 예외도 SSE 에러 이벤트로 전달
            yield {"event": "error",
                   "data": json.dumps({"detail": f"스트리밍 실패: {type(exc).__name__}"},
                                      ensure_ascii=False)}
            return
        yield {"event": "done", "data": "[DONE]"}

    return EventSourceResponse(event_stream())
