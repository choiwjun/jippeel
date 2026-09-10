"""Pydantic 스키마 — 프로젝트·회차 (Sprint 1 범위)."""
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

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
    style_profile: str | None = None  # 문체 프로파일 (G-040)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    genre: str | None
    synopsis: str | None
    platform_note: str | None
    style_profile: str | None
    created_at: datetime
    updated_at: datetime
    # 목록 카드용 집계 — 상세 조회에서는 채워지지 않는다
    chapter_count: int = 0
    total_chars: int = 0


# ---- Chapter ----
class ChapterCreate(BaseModel):
    title: str = Field(default="", max_length=255)
    volume: int | None = Field(default=None, ge=1)  # Q1: 생략 시 권 없는(NULL) 평면 회차
    sort_order: float = Field(default=0.0)


class ChapterUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    volume: int | None = Field(default=None, ge=1)
    sort_order: float | None = None
    status: ChapterStatus | None = None
    memo: str | None = None


class ChapterContentPut(BaseModel):
    """본문 저장 (PUT/POST content — 자동저장 debounce 대상)."""

    content_md: str
    expected_revision: int


class ChapterRestorePost(BaseModel):
    """복구본을 현재 회차 원고로 복원."""

    snapshot_id: int
    expected_revision: int


class SceneMergePut(BaseModel):
    """장면 본문을 회차 원고로 조립."""

    expected_revision: int



class ChapterOut(BaseModel):
    """회차 목록/트리용 (본문 제외)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    volume: int | None  # Q1: NULL = 권 없는 평면 회차
    sort_order: float
    title: str
    status: ChapterStatus
    word_count_cache: int
    revision: int
    memo: str | None
    created_at: datetime
    updated_at: datetime


class ChapterDetail(ChapterOut):
    """본문 포함."""

    content_md: str


class ChapterSnapshotOut(BaseModel):
    """회차 복구본 목록용 메타데이터."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    revision: int
    reason: str
    created_at: datetime


class ChapterSnapshotDetail(ChapterSnapshotOut):
    """회차 복구본 상세."""

    content_md: str


# ---- 노벨피아 PLUS 충족 현황 (A-038 / F-033, 결정사항_G4 Q3) ----
PLUS_MIN_CHAPTERS = 15        # 프로젝트 내 회차 수 기준
PLUS_MIN_CHARS_DONE = 3000    # 완료 회차 공백제외 글자 수 기준


class PlusStatusOut(BaseModel):
    """노벨피아 PLUS 충족 현황 (F-033).

    - chapter_count_met: 프로젝트 내 회차 수 ≥ 15회 (Q3 확정 해석)
    - done_chars_met: '완료' 회차가 1개 이상이고 그 모든 회차의
      공백제외 글자 수 캐시 ≥ 3,000 (완료 회차 0개면 미충족)
    """

    chapter_count: int
    chapter_count_met: bool
    done_chapter_count: int
    done_chapters_3000: int
    done_chars_met: bool
    eligible: bool


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
    temperature: float | None = Field(default=0.7, ge=0.0, le=2.0)
    reasoning_effort: Literal["minimal", "low", "medium", "high", "xhigh"] | None = None
    is_default: bool = False


class AiEndpointUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    base_url: str | None = Field(default=None, min_length=1, max_length=512)
    api_key: str | None = Field(default=None, max_length=4096)  # 전달 시 재암호화
    default_model: str | None = Field(default=None, max_length=255)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    reasoning_effort: Literal["minimal", "low", "medium", "high", "xhigh"] | None = None
    is_default: bool | None = None


class AiEndpointOut(BaseModel):
    """api_key는 has_api_key 플래그로만 노출한다 (FR-402)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_url: str
    default_model: str | None
    temperature: float | None
    reasoning_effort: str | None
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
# 회차 브리프 문자열·배열 항목 공통 검증 — 앞뒤 공백 제거 후 1~500자.
BriefText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
EpisodePurpose = Literal["serial", "volume_end", "series_finale"]


class EpisodeBrief(BaseModel):
    """회차 브리프 — 생성 요청 단위의 선택적 계약 (한국어 회차 품질 슬라이스).

    필수 필드 6개는 앞뒤 공백을 제거한 뒤 비어 있으면 안 되고(공백만 있는 값·항목도
    거부), 문자열·배열 항목 모두 500자로 제한한다. 배열 개수 상한은 유지한다.
    DB 마이그레이션 없이 요청에만 존재하는 구조체다.
    """

    emotion_goal: BriefText
    core_events: list[BriefText] = Field(min_length=1, max_length=3)
    character_choices: list[BriefText] = Field(min_length=1, max_length=4)
    cost: BriefText
    prohibitions: list[BriefText] = Field(min_length=1, max_length=10)
    next_hook: BriefText | None = None
    ending_intent: BriefText | None = None
    scene_type: Literal["대립", "액션", "정보정리", "감정", "이동"] | None = None
    target_chars_novelpia: int | None = Field(default=None, ge=1000, le=10000)


class GenerateContext(BaseModel):
    chapter_id: int | None = None
    project_id: int | None = Field(default=None, description="현재 요청이 속한 작품 ID")
    include_chapter_content: bool = True
    expected_revision: int | None = Field(default=None, ge=0)
    episode_purpose: EpisodePurpose = "serial"
    approved_foreshadow_ids: list[int] = Field(default_factory=list, max_length=20)
    include_relationships: bool = False
    character_ids: list[int] | None = None
    lore_ids: list[int] | None = None
    # 로어북 자동 주입 (백로그 P1) — chapter가 없으면 project_id로 프로젝트 판별
    auto_lore: bool = False
    auto_lore_limit: int = Field(default=6, ge=1, le=20)
    # 시맨틱 매칭 강화 (고도화 G-070) — 2-gram 코사인 하이브리드 랭킹
    auto_lore_semantic: bool = False
    # 직전 회차 끝부분 자동 포함 (백로그 — 이어쓰기 맥락 유지)
    previous_chapter: bool = False
    # 목차 자동 주입 (고도화 G-001) — 현재 회차 시놉시스·다음 회차 전개 방향 포함
    auto_outline: bool = False
    # 장면 단위 생성 (고도화 G-012) — chapter_id 대신(또는 함께) 지정 시 장면 본문 주입
    scene_id: int | None = None
    # 미회수 복선 자동 주입 (고도화 G-022)
    auto_foreshadow: bool = False
    auto_foreshadow_limit: int = Field(default=5, ge=1, le=10)
    # 작품 문체 프로파일 적용 (고도화 G-040) — Project.style_profile을 system 프롬프트에 결합
    style_profile: bool = False
    # 회차 브리프 (한국어 회차 품질 슬라이스) — 선택적 생성 계약, 없으면 기존 동작 유지
    brief: EpisodeBrief | None = None
    # provenance 기반 장편 기억 자동 주입. draft는 명시적으로 요청한 미리보기에서만 포함
    include_memory: bool = True
    include_draft_memory: bool = False

    @model_validator(mode="after")
    def validate_context_contract(self):
        if self.expected_revision is not None and self.chapter_id is None:
            raise ValueError("expected_revision requires chapter_id")
        if self.brief is not None:
            has_hook = bool(self.brief.next_hook)
            has_ending = bool(self.brief.ending_intent)
            if self.episode_purpose == "serial" and not has_hook:
                raise ValueError("serial brief requires next_hook")
            if self.episode_purpose == "volume_end" and not (has_hook or has_ending):
                raise ValueError("volume_end brief requires next_hook or ending_intent")
            if self.episode_purpose == "series_finale" and not has_ending:
                raise ValueError("series_finale brief requires ending_intent")
        return self


class GenerateParams(BaseModel):
    model: str | None = Field(default=None, max_length=255)  # endpoint.default_model 대체
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)


class GenerateReviewOptions(BaseModel):
    """생성 직후 자동 감수 패스 — 기존 /ai/generate SSE 계약을 유지한다.

    endpoint_id 미지정 시 생성 엔드포인트를 재사용하고, reasoning_effort 미지정 시
    감수 엔드포인트의 설정값을 따른다. 감수만 실패해도 초안은 이미 수신 완료된
    상태이므로 review_error 이벤트로 통보하고 스트림은 정상 종료한다.
    """

    endpoint_id: int | None = None
    model: str | None = Field(default=None, max_length=255)
    reasoning_effort: str | None = Field(default=None, max_length=20)
    max_tokens: int | None = Field(default=None, ge=1)


class ParallelScenePlan(BaseModel):
    """Medium planner가 반환하는 한 장면의 집필 계약."""

    order: int = Field(ge=1, le=4)
    title: BriefText
    purpose: BriefText
    objective: BriefText
    choice: BriefText
    cost: BriefText
    required_beats: list[BriefText] = Field(min_length=1, max_length=5)
    characters: list[BriefText] = Field(min_length=1, max_length=8)
    opening_state: BriefText
    closing_hook: BriefText | None = None
    ending_intent: BriefText | None = None


class ParallelPlan(BaseModel):
    """병렬 집필 planner 결과 — 2~4개 연속 장면."""

    scenes: list[ParallelScenePlan] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def validate_contiguous_orders(self):
        orders = [scene.order for scene in self.scenes]
        if orders != list(range(1, len(orders) + 1)):
            raise ValueError("scene orders must be contiguous from 1")
        return self


class ParallelGenerateRequest(BaseModel):
    """Medium 장면 병렬 집필 + xhigh 전체 감수 요청."""

    endpoint_id: int
    preset_id: int | None = None
    prompt_override: str | None = None
    context: GenerateContext = Field(default_factory=GenerateContext)
    params: GenerateParams = Field(default_factory=GenerateParams)
    worker_limit: int = Field(default=3, ge=2, le=4)
    generation_reasoning_effort: Literal["minimal", "low", "medium", "high", "xhigh"] = "medium"
    review: GenerateReviewOptions = Field(
        default_factory=lambda: GenerateReviewOptions(reasoning_effort="xhigh"))


class ReviewRequest(BaseModel):
    """감수 패스 요청 — /ai/generate와 분리된 독립 엔드포인트.

    초안 스트림이 끝난 뒤 별도 호출할 수 있다. 기존 /ai/generate의
    인라인 감수 계약과 병행해 클라이언트 마이그레이션을 지원한다.
    """

    endpoint_id: int
    model: str | None = Field(default=None, max_length=255)
    reasoning_effort: str | None = Field(default=None, max_length=20)
    max_tokens: int | None = Field(default=None, ge=1)
    draft: str = Field(min_length=1)


class GenerateRequest(BaseModel):
    endpoint_id: int
    preset_id: int | None = None
    prompt_override: str | None = None
    context: GenerateContext = Field(default_factory=GenerateContext)
    params: GenerateParams = Field(default_factory=GenerateParams)
    # 기존 인라인 감수 SSE 계약 — 별도 /ai/review와 병행 지원
    review: GenerateReviewOptions | None = None


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
    expected_revision: int
    force_route: RefineRoute | None = None


class RefineResult(BaseModel):
    run_id: int
    base_revision: int
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
    base_revision: int | None
    accepted: bool


class SimpleOk(BaseModel):
    ok: bool = True


# ---- Scene (고도화 G-010 — 회차 → 장면 계층) ----
class SceneCreate(BaseModel):
    title: str = Field(default="", max_length=255)
    sort_order: float = 0.0
    content_md: str = ""


class SceneUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    sort_order: float | None = None
    content_md: str | None = None


class SceneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    sort_order: float
    title: str
    content_md: str
    created_at: datetime
    updated_at: datetime


class ScenesReorderItem(BaseModel):
    id: int
    sort_order: float | None = None


class ScenesReorder(BaseModel):
    items: list[ScenesReorderItem] = Field(min_length=1)


# ---- Foreshadow (고도화 G-020 — 복선 관리) ----
ForeshadowStatus = Literal["설치", "회수", "보류"]


class ForeshadowCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str | None = None
    keywords: list[str] | None = None
    status: ForeshadowStatus = "설치"
    audience_knows: bool = False  # 독자가 이미 알게 된 사실인지 (G-045)
    planted_chapter_id: int | None = None
    resolved_chapter_id: int | None = None


class ForeshadowUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = None
    keywords: list[str] | None = None
    status: ForeshadowStatus | None = None
    audience_knows: bool | None = None
    planted_chapter_id: int | None = None
    resolved_chapter_id: int | None = None


class ForeshadowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    content: str | None
    keywords: list[str] | None
    status: ForeshadowStatus
    audience_knows: bool
    planted_chapter_id: int | None
    resolved_chapter_id: int | None
    created_at: datetime
    updated_at: datetime


# ---- 복선 자동 추출 (G-046) ----
class ForeshadowSuggestRequest(BaseModel):
    chapter_id: int


class ForeshadowSuggestCandidate(BaseModel):
    title: str
    content: str | None = None
    keywords: list[str] | None = None


class ForeshadowSuggestResponse(BaseModel):
    chapter_id: int
    model: str | None
    candidates: list[ForeshadowSuggestCandidate]


# ---- CanonCheck (고도화 G-023 — 회차-설정 모순 검사) ----
class CanonIssueOut(BaseModel):
    quote: str
    reason: str
    severity: Literal["info", "warn", "error"] = "warn"


class CanonCheckRequest(BaseModel):
    chapter_id: int
    expected_revision: int | None = Field(default=None, ge=0)
    episode_purpose: EpisodePurpose = "serial"
    approved_foreshadow_ids: list[int] = Field(default_factory=list, max_length=20)
    include_relationships: bool = False


class CanonCheckResponse(BaseModel):
    run_id: int
    chapter_id: int
    model: str | None
    issues: list[CanonIssueOut]
    checked_context: dict  # 주입된 컨텍스트 내역(투명성) — {"characters": n, "lore": n, "foreshadows": n}


class CanonRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    model: str | None
    issues_json: list | None
    context_json: dict | None
    created_at: datetime


# ---- Chapter 품질 진단 (고도화 G-031 — 규칙 기반) ----
class ChapterQualityOut(BaseModel):
    chapter_id: int
    score: int  # 0~100
    metrics: dict
    suggestions: list[str]
    suggested_preset_names: list[str]
    recorded: bool = False  # 이력 기록 여부(같은 본문이면 스킵)


class QualityCheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    score: int
    metrics_json: dict | None
    suggestions_json: list | None
    presets_json: list | None
    created_at: datetime


# ---- 권 개요 (고도화 G-050) ----
class VolumeNoteCreate(BaseModel):
    volume: int = Field(ge=1)
    title: str = Field(default="", max_length=255)
    overview: str | None = None
    emotion_curve: str | None = None
    climax_note: str | None = None


class VolumeNoteUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    overview: str | None = None
    emotion_curve: str | None = None
    climax_note: str | None = None


class VolumeNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    volume: int
    title: str
    overview: str | None
    emotion_curve: str | None
    climax_note: str | None
    created_at: datetime
    updated_at: datetime


# ---- AI 사용량 (고도화 G-060 — 문자량 기반 집계) ----
class AiUsageSummaryOut(BaseModel):
    kind: str
    model: str | None
    calls: int
    prompt_chars: int
    completion_chars: int
    last_at: datetime


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
    volume_note_count: int = 0
    title_candidates: list[str]
    theme: str | None
    used_ai: bool
    fallback: bool
