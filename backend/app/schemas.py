"""Pydantic 스키마 — 프로젝트·회차 (Sprint 1 범위)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChapterStatus = Literal["초고", "수정중", "완료"]


# ---- Project ----
class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    genre: str | None = Field(default=None, max_length=100)
    synopsis: str | None = None
    platform_note: str | None = None


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    genre: str | None = Field(default=None, max_length=100)
    synopsis: str | None = None
    platform_note: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    genre: str | None
    synopsis: str | None
    platform_note: str | None
    created_at: datetime
    updated_at: datetime


# ---- Chapter ----
class ChapterCreate(BaseModel):
    title: str = Field(default="", max_length=255)
    volume: int = Field(default=1, ge=1)
    sort_order: float = Field(default=0.0)


class ChapterUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    volume: int | None = Field(default=None, ge=1)
    sort_order: float | None = None
    status: ChapterStatus | None = None
    memo: str | None = None


class ChapterContentPut(BaseModel):
    """본문 저장 (PUT content — 자동저장 debounce 대상)."""

    content_md: str


class ChapterOut(BaseModel):
    """회차 목록/트리용 (본문 제외)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    volume: int
    sort_order: float
    title: str
    status: ChapterStatus
    word_count_cache: int
    memo: str | None
    created_at: datetime
    updated_at: datetime


class ChapterDetail(ChapterOut):
    """본문 포함."""

    content_md: str


# ---- Character (M2, Sprint 2) ----
CharacterRole = Literal["주연", "조연", "단역", "기타"]


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    aliases: list[str] | None = None
    role: CharacterRole | None = None
    appearance: str | None = None
    personality: str | None = None
    speech_style: str | None = None
    background: str | None = None
    card_json: dict | None = None


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    aliases: list[str] | None = None
    role: CharacterRole | None = None
    appearance: str | None = None
    personality: str | None = None
    speech_style: str | None = None
    background: str | None = None


class CardJsonPatch(BaseModel):
    """card_json 부분 업데이트(RFC 7386 JSON Merge Patch 유사).

    값이 None인 키는 제거, 나머지는 재귀 병합.
    """

    patch: dict


class CharacterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    aliases: list[str] | None
    role: CharacterRole | None
    appearance: str | None
    personality: str | None
    speech_style: str | None
    background: str | None
    card_json: dict | None
    created_at: datetime
    updated_at: datetime


# ---- Relationship ----
class RelationshipCreate(BaseModel):
    from_character_id: int
    to_character_id: int
    label: str | None = Field(default=None, max_length=255)
    note: str | None = None


class RelationshipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_character_id: int
    to_character_id: int
    label: str | None
    note: str | None


# ---- LoreEntry (M3, Sprint 2) ----
LoreCategory = Literal["용어", "장소", "세력", "기타"]


class LoreEntryCreate(BaseModel):
    category: LoreCategory = "기타"
    title: str = Field(min_length=1, max_length=255)
    content: str | None = None
    keywords: list[str] | None = None


class LoreEntryUpdate(BaseModel):
    category: LoreCategory | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = None


class KeywordsPut(BaseModel):
    """keywords[] 전체 교체."""

    keywords: list[str]


class LoreEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    category: LoreCategory
    title: str
    content: str | None
    keywords: list[str] | None
    created_at: datetime
    updated_at: datetime


# ---- Chapter reorder (Sprint 2) ----
class ReorderItem(BaseModel):
    id: int
    volume: int | None = Field(default=None, ge=1)
    sort_order: float | None = None


class ChaptersReorder(BaseModel):
    items: list[ReorderItem] = Field(min_length=1)
# ---- Chapter reorder (Sprint 2) ----
class ReorderItem(BaseModel):
    id: int
    volume: int | None = Field(default=None, ge=1)
    sort_order: float | None = None


class ChaptersReorder(BaseModel):
    items: list[ReorderItem] = Field(min_length=1)


# ---- AiEndpoint (M4, Sprint 3) — NFR-202: 평문 api_key는 어떤 응답에도 미반환 ----
class AiEndpointCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_url: str = Field(min_length=1, max_length=512)
    api_key: str | None = Field(default=None, max_length=4096)
    default_model: str | None = Field(default=None, max_length=255)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    is_default: bool = False


class AiEndpointUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    base_url: str | None = Field(default=None, min_length=1, max_length=512)
    api_key: str | None = Field(default=None, max_length=4096)  # 전달 시 재암호화
    default_model: str | None = Field(default=None, max_length=255)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    is_default: bool | None = None


class AiEndpointOut(BaseModel):
    """api_key는 has_api_key 플래그로만 노출한다 (FR-402)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_url: str
    default_model: str | None
    temperature: float
    is_default: bool
    has_api_key: bool


# ---- PromptPreset (M4) ----
ContextFlag = Literal["chapter", "characters", "lore"]


class PromptPresetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    template_text: str = Field(min_length=1)
    context_flags: list[ContextFlag] | None = None


class PromptPresetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    template_text: str | None = None
    context_flags: list[ContextFlag] | None = None


class PromptPresetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    template_text: str
    context_flags: list[ContextFlag] | None


# ---- AI 생성 요청 (POST /ai/generate) ----
class GenerateContext(BaseModel):
    chapter_id: int | None = None
    character_ids: list[int] | None = None
    lore_ids: list[int] | None = None


class GenerateParams(BaseModel):
    model: str | None = Field(default=None, max_length=255)  # endpoint.default_model 대체
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)


class GenerateRequest(BaseModel):
    endpoint_id: int
    preset_id: int | None = None
    prompt_override: str | None = None
    context: GenerateContext = Field(default_factory=GenerateContext)
    params: GenerateParams = Field(default_factory=GenerateParams)


# ---- Refine (M5, Sprint 3) — 부록05 §⑤-5 span 규격 / 사양 §5 윤문 API ----
RefineRoute = Literal["light", "standard", "heavy"]
TaxonomyCategory = Literal["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
SpanSeverity = Literal["info", "warn"]


class SpanOut(BaseModel):
    category: TaxonomyCategory
    start: int
    end: int
    severity: SpanSeverity = "info"
    message: str | None = None


class RefineRequest(BaseModel):
    chapter_id: int
    force_route: RefineRoute | None = None


class RefineResult(BaseModel):
    run_id: int
    route_hint: str
    spans: list[SpanOut]
    original: str
    refined: str
    changed_ratio: float
    gate: Literal["pass", "warn", "block"]
    status: Literal["ok", "blocked"]  # FR-505: block 시 status=blocked


class RefineRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    route_hint: str | None
    changed_ratio: float
    report_json: dict | None
    result_text: str | None
    accepted: bool


class SimpleOk(BaseModel):
    ok: bool = True


# ---- Project Bootstrap (입력 하나로 작품 전체 구조 AI 생성) ----
class BootstrapRequest(BaseModel):
    genre: str = Field(min_length=1, max_length=100, examples=["판타지"])
    premise: str | None = Field(default=None, max_length=2000,
                                description="한 줄 프리미스 — 없으면 AI가 발상")
    volume_count: int = Field(default=1, ge=1, le=50)
    chapters_per_volume: int = Field(default=10, ge=1, le=200)
    title_style: str = Field(default="웹소설식 긴 제목", max_length=100)
    use_ai: bool = True


class BootstrapResponse(BaseModel):
    project_id: int
    title: str
    logline: str
    outline_summary: str
    character_count: int
    lore_count: int
    chapter_count: int
    volume_count: int
    relationship_count: int
    title_candidates: list[str]
    theme: str | None
    used_ai: bool
    fallback: bool
