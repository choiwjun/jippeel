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
from app.services import injection, llm

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


def _build_context_blocks(payload: GenerateRequest, db: Session) -> tuple[list[str], list[dict]]:
    """FR-404 — 요청된 컨텍스트(회차/캐릭터/로어북)를 프롬프트 블록으로 조립.

    자동 주입(auto_lore, 백로그 P1)이 켜지면 본문·지시문에 언급된 로어 항목을
    점수순으로 추가한다. 주입은 입력 컨텍스트일 뿐이며 원고에 자동 삽입되지
    않는다(P1·FR-406). 반환: (블록 목록, 자동 주입된 항목 [{id,title}])
    """
    blocks: list[str] = []
    injected: list[dict] = []
    ctx = payload.context
    source_parts: list[str] = []
    project_id = ctx.project_id
    if ctx.chapter_id is not None:
        chapter = db.get(Chapter, ctx.chapter_id)
        if chapter is None:
            raise HTTPException(status_code=404, detail="chapter not found")
        blocks.append(f"[현재 회차: {chapter.title}]\n{chapter.content_md}")
        source_parts.append(chapter.content_md or "")
        project_id = project_id or chapter.project_id
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
    if ctx.lore_ids:
        entries = db.scalars(select(LoreEntry).where(LoreEntry.id.in_(ctx.lore_ids))).all()
        for entry in entries:
            blocks.append(f"[세계관: {entry.title}]\n{entry.content or ''}")
    if ctx.auto_lore and project_id is not None:
        if payload.prompt_override:
            source_parts.append(payload.prompt_override)
        selected = injection.select_lore_for_text(
            db, project_id, "\n".join(source_parts), limit=ctx.auto_lore_limit)
        exclude = set(ctx.lore_ids or [])
        for entry in selected:
            if entry.id in exclude:
                continue  # 명시 선택분과 중복 주입 방지
            blocks.append(f"[세계관(자동): {entry.title}]\n{entry.content or ''}")
            injected.append({"id": entry.id, "title": entry.title})
    return blocks, injected


def _build_messages(payload: GenerateRequest, db: Session) -> tuple[str, list[dict]]:
    """프리셋 템플릿 + 컨텍스트 + override → chat messages.

    반환: (model_hint, messages, 자동 주입된 로어 목록)
    """
    context_blocks, injected = _build_context_blocks(payload, db)
    sections = ["다음 컨텍스트를 참고해 작성하세요.", *context_blocks]
    context_text = "\n\n".join(p for p in sections if p)

    instruction = payload.prompt_override
    if payload.preset_id is not None:
        preset = _get_preset_or_404(payload.preset_id, db)
        instruction = f"{preset.template_text}\n\n{instruction}" if instruction else preset.template_text
    if not instruction:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="preset_id 또는 prompt_override 중 하나는 필요합니다.")

    user_content = f"{context_text}\n\n---\n\n지시:\n{instruction}"
    return "default", [{"role": "user", "content": user_content}], injected


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
    _, messages, injected_lore = _build_messages(payload, db)
    model = _resolve_model(endpoint, payload.params.model)
    temperature = payload.params.temperature
    if temperature is None:
        temperature = endpoint.temperature

    client = llm.make_client(endpoint.base_url, endpoint.api_key_encrypted)

    async def event_stream():
        # 시작 이벤트 — 프론트가 스트림 개시를 확정할 수 있다
        # 시작 이벤트 — 프론트가 스트림 개시를 확정하고, 자동 주입된 로어 목록을
        # 투명하게 표시할 수 있다(주입 내역 공개)
        yield {"event": "start",
               "data": json.dumps({"model": model, "injected_lore": injected_lore},
                                  ensure_ascii=False)}
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
