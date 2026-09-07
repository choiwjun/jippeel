"""AI 패널 라우터 (사양 §5 M4, Sprint 3).

- AiEndpoint CRUD — api_key는 저장 시 암호화(NFR-202), 어떤 응답에도 평문 미반환
- PromptPreset CRUD
- POST /ai/generate — openai SDK(base_url 오버라이드) SSE 스트리밍 (FR-405)
"""
import asyncio
import inspect
import json

import openai
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.models import AiEndpoint, Chapter, Character, Foreshadow, LoreEntry, Project, PromptPreset, Scene
from app.schemas import (
    AiEndpointCreate,
    AiEndpointOut,
    AiEndpointUpdate,
    EpisodeBrief,
    GenerateRequest,
    ParallelGenerateRequest,
    PromptPresetCreate,
    PromptPresetOut,
    PromptPresetUpdate,
)
from app.services import injection, llm, parallel_writer, usage as usage_service

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
    "- 브리프에 다음 화 훅이 있으면 그 훅으로 향하는 미해결 질문이나 행동으로 화를 끝낸다. 훅이 없어도 장면의 긴장이 완전히 풀리기 전에 끝낸다.\n"
    "[문체]\n"
    "- '~하고 ~했다' 식의 문학적 장문 대신, 인물의 시선에서 흐르는 구어체 단문을 쓴다.\n"
    "- 형용사·수식어를 걷어내고 동사와 구체적 행동으로 보여준다. 설명은 절제하고, 보여줄 수 있는 것은 묘사하지 않는다.\n"
    "- 내면 묘사는 짧은 독백 한 줄로 과감하게: 의심·비웃음·각오.\n"
    "- 갈등을 다 풀지 마라. 해결은 다음 화에 남긴다.\n"
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
    "- 문장/리듬: 중복·군더더기·설명 과다. 장면 유형에 맞는 대사·행동·설명의 리듬.\n"
    "- 플랫폼: 노벨피아·문피아 연재 관행 — 도입 페이스, 화 전환, 다음 화 클릭을 유도하는 마무리.\n"
    "[출력 형식 — 절대 어긋나지 않는다]\n"
    "[감수]\n"
    "- 중요한 문제만 3~7개. 각 항목은 '- '으로 시작하고, 관점, 원문 위치와 근거(원문 표현), 이유, 수정 제안을 한국어로 간결하게 쓴다. 사소한 취향 지적은 하지 않는다.\n"
    "[수정본]\n"
    "지적을 반영해 초안 전체를 수정한 원고를 그대로 쓴다. 설명·메타 코멘트 금지.\n"
    "분량은 초안과 비슷하게 유지하고, 좋은 부분은 함부로 바꾸지 않는다. 브리프와 작품 설정 밖의 사실을 새로 만들지 않는다."
)
REVIEW_MARKER = "[수정본]"  # 감수 의견 → 수정본 전환 지점 (라인 단위 매칭)
PARALLEL_REVIEW_SYSTEM_PROMPT = (
    "너는 한국 웹소설 편집장이다. 아래 조립 원고를 구조·캐릭터·연속성/설정·문장/리듬·플랫폼 "
    "다섯 관점에서 감수하라.\n"
    "[출력 형식]\n"
    "[감수]\n"
    "- 중요한 문제만 3~7개. 원문 위치, 근거, 이유, 수정 제안을 한국어로 간결하게 쓴다.\n"
    "[수정본] 섹션은 출력하지 마라. 원고를 다시 쓰거나 자동 수정하지 마라.\n"
    "컨텍스트와 장면 계약 밖의 사실을 새로 만들지 마라."
)

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


def _build_context_blocks(payload: GenerateRequest, db: Session) -> tuple[list[str], list[dict], dict, list[dict]]:
    """FR-404 — 요청된 컨텍스트(회차/캐릭터/로어북)를 프롬프트 블록으로 조립.

    자동 주입(auto_lore, 백로그 P1)이 켜지면 본문·지시문에 언급된 로어 항목을
    점수순으로 추가한다. auto_outline(고도화 G-001)이 켜지면 현재 회차의
    목차 메모(시놉시스·핵심 사건)와 다음 회차 전개 방향을 추가한다.
    주입은 입력 컨텍스트일 뿐이며 원고에 자동 삽입되지
    않는다(P1·FR-406). 반환: (블록 목록, 자동 주입 로어 [{id,title}], 목차 주입 정보)
    """
    blocks: list[str] = []
    injected: list[dict] = []
    injected_foreshadows: list[dict] = []
    outline_info: dict = {}
    ctx = payload.context
    # 회차 브리프 — 브리프 우선 원칙: 다른 컨텍스트 블록보다 앞에 위치
    if ctx.brief is not None:
        blocks.append(_format_brief_block(ctx.brief))
    source_parts: list[str] = []
    project_id = ctx.project_id
    if ctx.scene_id is not None:
        scene = db.get(Scene, ctx.scene_id)
        if scene is None:
            raise HTTPException(status_code=404, detail="scene not found")
        blocks.append(f"[현재 장면: {scene.title or '무제'} — 이 장면 안에서만 집필]\n{scene.content_md}")
        source_parts.append(scene.content_md or "")
        if chapter_ref := db.get(Chapter, scene.chapter_id):
            project_id = project_id or chapter_ref.project_id
    if ctx.chapter_id is not None:
        chapter = db.get(Chapter, ctx.chapter_id)
        if chapter is None:
            raise HTTPException(status_code=404, detail="chapter not found")
        blocks.append(f"[현재 회차: {chapter.title}]\n{chapter.content_md}")
        source_parts.append(chapter.content_md or "")
        project_id = project_id or chapter.project_id
        chapter_memo = (chapter.memo or "").strip()
        if chapter_memo and ctx.auto_lore:
            # 신규 회차는 본문이 비어 있을 수 있으므로 목차 메모도 로어 매칭 원본에 포함한다.
            source_parts.append(chapter_memo)
        if chapter_memo and ctx.auto_outline:
            blocks.append(f"[이번 회차 목표(목차) — 이 화에서 반드시 다뤄야 할 내용]\n{chapter_memo}")
            outline_info["current"] = True
        if ctx.auto_outline and chapter.volume is not None:
            from app.models import VolumeNote
            vnote = db.scalars(
                select(VolumeNote).where(
                    VolumeNote.project_id == chapter.project_id,
                    VolumeNote.volume == chapter.volume)).first()
            if vnote is not None:
                parts = [f"[{chapter.volume}권 개요 — 권 전체 방향, 이 화가 어긋나지 않게]"]
                for field in ("overview", "emotion_curve", "climax_note"):
                    value = getattr(vnote, field, None)
                    if value and value.strip():
                        parts.append(value.strip()[:400])
                blocks.append("\n".join(parts))
                outline_info["volume_note"] = vnote.volume
        if ctx.previous_chapter:
            prev = db.scalars(
                select(Chapter).where(
                    Chapter.project_id == chapter.project_id,
                    Chapter.sort_order < chapter.sort_order,
                ).order_by(Chapter.sort_order.desc())
            ).first()
            if prev and (prev.content_md or "").strip():
                tail = prev.content_md[-PREVIOUS_CHAPTER_TAIL_CHARS:]
                blocks.append(f"[직전 회차: {prev.title} 끝부분]\n…{tail}")
        if ctx.auto_outline:
            nxt = db.scalars(
                select(Chapter).where(
                    Chapter.project_id == chapter.project_id,
                    Chapter.sort_order > chapter.sort_order,
                ).order_by(Chapter.sort_order.asc())
            ).first()
            if nxt is not None:
                direction = (nxt.memo or "").strip()
                blocks.append(f"[다음 회차 예고: {nxt.title}]")
                if direction:
                    # 다음 회차를 다 쓰지 않도록 요약 수준만 전달
                    blocks[-1] += f"\n{direction[:600]}"
                outline_info["next_chapter_id"] = nxt.id
                outline_info["next_title"] = nxt.title
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
        if ctx.auto_lore_semantic:
            # G-070 시맨틱 하이브리드 — v1 점수 + 2-gram 코사인 랭킹
            selected = injection.select_lore_for_text_hybrid(
                db, project_id, "\n".join(source_parts), limit=ctx.auto_lore_limit)
        else:
            selected = injection.select_lore_for_text(
                db, project_id, "\n".join(source_parts), limit=ctx.auto_lore_limit)
        exclude = set(ctx.lore_ids or [])
        for entry in selected:
            if entry.id in exclude:
                continue  # 명시 선택분과 중복 주입 방지
            blocks.append(f"[세계관(자동): {entry.title}]\n{entry.content or ''}")
            injected.append({"id": entry.id, "title": entry.title})
    if ctx.auto_foreshadow and project_id is not None:
        rows = db.scalars(
            select(Foreshadow).where(
                Foreshadow.project_id == project_id,
                Foreshadow.status == "설치",
            ).order_by(Foreshadow.created_at.desc(), Foreshadow.id.desc())
        ).all()
        for row in rows[:ctx.auto_foreshadow_limit]:
            content = (row.content or "").strip()
            block = f"[미회수 복선: {row.title}]"
            if content:
                block += f"\n{content[:400]}"
            block += "\n→ 이 복선은 아직 회수 전이다. 이 화에서 건드릴 거면 자연스럽게, 건드리지 않으면 결론을 미리 풀지 마라."
            blocks.append(block)
            injected_foreshadows.append({"id": row.id, "title": row.title})
    return blocks, injected, outline_info, injected_foreshadows


def _build_messages(payload: GenerateRequest, db: Session) -> tuple[str, list[dict]]:
    """프리셋 템플릿 + 컨텍스트 + override → chat messages.

    반환: (model_hint, messages, 자동 주입된 로어 목록, 목차 주입 정보, 복선 주입 목록)
    context.style_profile(G-040)이면 해당 프로젝트의 문체 프로파일을
    system 프롬프트 뒤에 결합한다(작품별 문체 유지).
    """
    context_blocks, injected, outline_info, injected_foreshadows = _build_context_blocks(payload, db)
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
    system_prompt = NOVEL_SYSTEM_PROMPT
    if payload.context.style_profile:
        # project_id 복원 — context에 명시 없으면 회차/장면 소속 프로젝트로 판별
        style_project_id = payload.context.project_id
        if style_project_id is None and payload.context.chapter_id is not None:
            ch_row = db.get(Chapter, payload.context.chapter_id)
            style_project_id = ch_row.project_id if ch_row else None
        if style_project_id is None and payload.context.scene_id is not None:
            scene_row = db.get(Scene, payload.context.scene_id)
            ch_row = db.get(Chapter, scene_row.chapter_id) if scene_row else None
            style_project_id = ch_row.project_id if ch_row else None
        project = db.get(Project, style_project_id) if style_project_id else None
        if project is not None and (project.style_profile or "").strip():
            system_prompt = (f"{NOVEL_SYSTEM_PROMPT}\n\n[작품 문체 프로파일 — 반드시 따른다]\n"
                             f"{project.style_profile.strip()}")
    messages = [{"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}]
    return "default", messages, injected, outline_info, injected_foreshadows


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
        reasoning_effort=payload.reasoning_effort,
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


# ---------- AI 사용량 (고도화 G-060) ----------
@router.get("/ai/usage")
def ai_usage(days: int = 30):
    """문자량 기반 AI 사용 통계 — kind+model 그룹 집계."""
    from app.schemas import AiUsageSummaryOut
    return [AiUsageSummaryOut(**row).model_dump()
            for row in usage_service.summary(limit_days=max(min(days, 365), 1))]


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


# ---------- AI 생성 스트리밍 ----------
@router.post("/ai/generate")
async def generate(payload: GenerateRequest, db: Session = Depends(get_db)):
    endpoint = _get_endpoint_or_404(payload.endpoint_id, db)
    _, messages, injected_lore, injected_outline, injected_foreshadows = _build_messages(payload, db)
    model = _resolve_model(endpoint, payload.params.model)
    temperature = payload.params.temperature
    if temperature is None:
        temperature = endpoint.temperature

    client = llm.make_client(endpoint.base_url, endpoint.api_key_encrypted)

    # 감수 패스 사전 검증 — 초안 스트리밍 시작 전에 설정 오류를 잡는다
    review_cfg = None
    if payload.review is not None:
        rid = payload.review.endpoint_id or endpoint.id
        reviewer = _get_endpoint_or_404(rid, db)
        review_cfg = {
            "client": llm.make_client(reviewer.base_url, reviewer.api_key_encrypted)
            if reviewer.id != endpoint.id else client,
            "endpoint_name": reviewer.name,
            "model": _resolve_model(reviewer, payload.review.model),
            "reasoning_effort": payload.review.reasoning_effort if payload.review.reasoning_effort
            else reviewer.reasoning_effort,
            "max_tokens": payload.review.max_tokens if payload.review.max_tokens is not None
            else payload.params.max_tokens,
        }

    async def event_stream():
        # 시작 이벤트 — 프론트가 스트림 개시를 확정할 수 있다
        # 시작 이벤트 — 프론트가 스트림 개시를 확정하고, 자동 주입된 로어 목록을
        # 투명하게 표시할 수 있다(주입 내역 공개)
        yield {"event": "start",
               "data": json.dumps({"model": model, "injected_lore": injected_lore,
                                   "injected_outline": injected_outline,
                                   "injected_foreshadows": injected_foreshadows,
                                   "review_enabled": review_cfg is not None},
                                  ensure_ascii=False)}
        completion_chars = 0
        draft_parts: list[str] = []
        try:
            async for delta in llm.stream_chat(client, model, messages,
                                               temperature=temperature,
                                               max_tokens=payload.params.max_tokens,
                                               reasoning_effort=endpoint.reasoning_effort):
                completion_chars += len(delta)
                draft_parts.append(delta)
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
        # G-060 사용량 기록 (best-effort)
        usage_service.record(
            kind="generate", model=model, endpoint_name=endpoint.name,
            prompt_chars=sum(len(str(m.get("content") or "")) for m in messages),
            completion_chars=completion_chars)

        # 감수 패스 — 초안 스트림이 정상 종료된 직후 같은 SSE에서 이어 실행
        if review_cfg is not None:
            yield {"event": "review_start",
                   "data": json.dumps({"model": review_cfg["model"],
                                       "endpoint": review_cfg["endpoint_name"],
                                       "reasoning_effort": review_cfg["reasoning_effort"]},
                                      ensure_ascii=False)}
            review_messages = [
                {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                {"role": "user",
                 "content": f"{messages[-1]['content']}\n\n---\n\n[초안 원고]\n{''.join(draft_parts)}"},
            ]
            review_chars = 0
            try:
                feed, flush_review = _split_review_stream()
                async for delta in llm.stream_chat(
                        review_cfg["client"], review_cfg["model"], review_messages,
                        max_tokens=review_cfg["max_tokens"],
                        reasoning_effort=review_cfg["reasoning_effort"]):
                    review_chars += len(delta)
                    async for event_name, chunk in feed(delta):
                        yield {"event": event_name,
                               "data": json.dumps({"delta": chunk}, ensure_ascii=False)}
                # 종료 flush — [수정본] 마커 없이 끝나도 carry의 마지막 구간을 review로 방출
                async for event_name, chunk in flush_review():
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
                    usage_service.record(
                        kind="review", model=review_cfg["model"],
                        endpoint_name=review_cfg["endpoint_name"],
                        prompt_chars=sum(len(str(m.get("content") or "")) for m in review_messages),
                        completion_chars=review_chars)
        yield {"event": "done", "data": "[DONE]"}

    return EventSourceResponse(event_stream())


# ---------- 병렬 장면 집필 스트리밍 ----------
@router.post("/ai/generate-parallel")
async def generate_parallel(payload: ParallelGenerateRequest, db: Session = Depends(get_db)):
    """Medium planner/worker 병렬 집필 후 xhigh 감수만 수행한다."""
    endpoint = _get_endpoint_or_404(payload.endpoint_id, db)
    base_payload = GenerateRequest(
        endpoint_id=payload.endpoint_id,
        prompt_override=payload.prompt_override,
        context=payload.context,
        params=payload.params,
    )
    _, base_messages, injected_lore, injected_outline, injected_foreshadows = _build_messages(
        base_payload, db)
    model = _resolve_model(endpoint, payload.params.model)
    temperature = payload.params.temperature
    if temperature is None:
        temperature = endpoint.temperature
    generation_client = llm.make_client(endpoint.base_url, endpoint.api_key_encrypted)

    reviewer = _get_endpoint_or_404(payload.review.endpoint_id or endpoint.id, db)
    reviewer_model = _resolve_model(reviewer, payload.review.model)
    reviewer_effort = payload.review.reasoning_effort or "xhigh"
    reviewer_client = (llm.make_client(reviewer.base_url, reviewer.api_key_encrypted)
                       if reviewer.id != endpoint.id else generation_client)

    planner_system = (
        "너는 한국 웹소설의 장면 설계자다. 반드시 단일 유효 JSON 객체만 출력하라.\n"
        "2~4개 장면으로 나누고, 장면 order는 1부터 연속이어야 한다.\n"
        "각 장면에는 title, purpose, required_beats, characters, opening_state, closing_hook을 포함하라.\n"
        "정본 컨텍스트와 브리프 밖의 사건·고유명사를 새로 만들지 마라."
    )
    planner_instruction = (
        f"{base_messages[-1]['content']}\n\n"
        "[병렬 Planner — 장면 계약 생성]\n"
        "현재 회차를 2~4개 장면으로 분해하라. 각 worker는 자기 계약만 집필한다.\n"
        '{"scenes":[{"order":1,"title":"...","purpose":"...",'
        '"required_beats":["..."],"characters":["..."],'
        '"opening_state":"...","closing_hook":"..."}]} 형식만 출력하라.'
    )

    async def event_stream():
        yield {
            "event": "parallel_start",
            "data": json.dumps({
                "model": model,
                "generation_reasoning_effort": payload.generation_reasoning_effort,
                "review_model": reviewer_model,
                "review_endpoint": reviewer.name,
                "review_reasoning_effort": reviewer_effort,
                "worker_limit": payload.worker_limit,
                "injected_lore": injected_lore,
                "injected_outline": injected_outline,
                "injected_foreshadows": injected_foreshadows,
            }, ensure_ascii=False),
        }
        try:
            planner_messages = [
                {"role": "system", "content": planner_system},
                {"role": "user", "content": planner_instruction},
            ]
            planner_raw = await llm.complete_chat(
                generation_client, model, planner_messages,
                temperature=temperature,
                max_tokens=payload.params.max_tokens,
                reasoning_effort=payload.generation_reasoning_effort,
            )
            plan = parallel_writer.parse_parallel_plan(planner_raw)
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
                    "앞 장면의 opening_state에서 시작하고 closing_hook으로 끝내라. "
                    "다른 장면을 대신 쓰지 말고, 정본 컨텍스트 밖의 사실을 만들지 마라. "
                    "원고 본문만 출력하라."
                )
                worker_messages = [
                    {"role": "system", "content": NOVEL_SYSTEM_PROMPT},
                    {"role": "user", "content": worker_prompt},
                ]
                text = await llm.complete_chat(
                    generation_client, model, worker_messages,
                    temperature=temperature,
                    max_tokens=payload.params.max_tokens,
                    reasoning_effort=payload.generation_reasoning_effort,
                )
                return parallel_writer.SceneResult(
                    order=scene.order, title=scene.title, text=text,
                )

            results = await parallel_writer.run_parallel_workers(
                plan.scenes, run_scene, payload.worker_limit,
            )
            for result in results:
                yield {
                    "event": "worker_done",
                    "data": json.dumps({
                        "order": result.order,
                        "title": result.title,
                        "chars": len(result.text),
                    }, ensure_ascii=False),
                }
            assembled = parallel_writer.assemble_scene_results(results)
            usage_service.record(
                kind="parallel_plan", model=model, endpoint_name=endpoint.name,
                prompt_chars=sum(len(str(m.get("content") or "")) for m in planner_messages),
                completion_chars=len(planner_raw),
            )
            usage_service.record(
                kind="parallel_generate", model=model, endpoint_name=endpoint.name,
                prompt_chars=sum(len(str(m.get("content") or "")) for m in base_messages),
                completion_chars=len(assembled),
            )
            yield {"event": "message", "data": json.dumps({"delta": assembled}, ensure_ascii=False)}
        except openai.APIError as exc:
            yield {
                "event": "parallel_error",
                "data": json.dumps({"stage": "generation", "detail": _friendly_api_error(exc)},
                                   ensure_ascii=False),
            }
            return
        except Exception as exc:  # noqa: BLE001 — 병렬 단계 전체를 사용자 이벤트로 변환
            yield {
                "event": "parallel_error",
                "data": json.dumps({
                    "stage": "generation", "detail": f"병렬 집필 실패: {type(exc).__name__}",
                }, ensure_ascii=False),
            }
            return

        yield {
            "event": "review_start",
            "data": json.dumps({
                "model": reviewer_model,
                "endpoint": reviewer.name,
                "reasoning_effort": reviewer_effort,
            }, ensure_ascii=False),
        }
        review_messages = [
            {"role": "system", "content": PARALLEL_REVIEW_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"{base_messages[-1]['content']}\n\n[조립 원고]\n{assembled}\n\n"
                "위 원고만 감수하고 [감수] 의견만 출력하라.")},
        ]
        review_chars = 0
        try:
            async for delta in llm.stream_chat(
                    reviewer_client, reviewer_model, review_messages,
                    max_tokens=payload.review.max_tokens or payload.params.max_tokens,
                    reasoning_effort=reviewer_effort):
                review_chars += len(delta)
                yield {"event": "review",
                       "data": json.dumps({"delta": delta}, ensure_ascii=False)}
            if review_chars:
                usage_service.record(
                    kind="parallel_review", model=reviewer_model,
                    endpoint_name=reviewer.name,
                    prompt_chars=sum(len(str(m.get("content") or "")) for m in review_messages),
                    completion_chars=review_chars,
                )
        except openai.APIError as exc:
            yield {"event": "parallel_error",
                   "data": json.dumps({"stage": "review", "detail": _friendly_api_error(exc)},
                                      ensure_ascii=False)}
        except Exception as exc:  # noqa: BLE001
            yield {"event": "parallel_error",
                   "data": json.dumps({
                       "stage": "review", "detail": f"감수 실패: {type(exc).__name__}",
                   }, ensure_ascii=False)}
        yield {"event": "done", "data": "[DONE]"}
    return EventSourceResponse(event_stream())
