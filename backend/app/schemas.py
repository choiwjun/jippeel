"""Pydantic 스키마 — 프로젝트·회차 (Sprint 1 범위)."""
from datetime import datetime
import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ChapterStatus = Literal["초고", "수정중", "완료"]
EpisodePurpose = Literal["serial", "volume_end", "series_finale"]


# ---- Project ----
class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    genre: str | None = Field(default=None, max_length=100)
    synopsis: str | None = None
    platform_note: str | None = None


SerialState = Literal["ongoing", "hiatus", "completed"]


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    genre: str | None = Field(default=None, max_length=100)
    synopsis: str | None = None
    platform_note: str | None = None
    style_profile: str | None = None  # 문체 프로파일 (G-040)
    # D03-3 연재 상태 — 회차 confirmed(집필 확정)와 다른 수명주기
    serial_state: SerialState | None = None
    # D03-7 작품 수준 결말 후보 — 생략 시 불변, 명시적 null은 지우기
    ending_intent: str | None = None
    ending_locked: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_null_serial_state(cls, data):
        # 명시적 null은 "필드 생략"과 다르다 — 잘못된 값으로 422 처리한다.
        if isinstance(data, dict):
            if "serial_state" in data and data["serial_state"] is None:
                raise ValueError("serial_state must be one of: ongoing, hiatus, completed")
            # D03-7: NOT NULL 컬럼 — 명시적 null은 IntegrityError가 아니라 422다.
            if "ending_locked" in data and data["ending_locked"] is None:
                raise ValueError("ending_locked must be a boolean")
        return data


class TrendSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=120)
    note: str = Field(min_length=1, max_length=500)


class TrendPackWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # PUT is an upsert: create requires as_of/signals, update may omit fields.
    status: Literal["draft", "approved", "retired"] | None = None
    source: Literal["author", "research", "imported"] | None = None
    as_of: datetime | None = None
    signals: list[TrendSignal] | None = Field(default=None, min_length=1, max_length=12)


class TrendPackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    schema_version: str
    status: Literal["draft", "approved", "retired"]
    source: Literal["author", "research", "imported"]
    as_of: datetime
    version: int
    signals: list[TrendSignal]
    created_at: datetime
    updated_at: datetime


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    genre: str | None
    synopsis: str | None
    platform_note: str | None
    style_profile: str | None
    serial_state: str = "ongoing"
    serial_completed_at: datetime | None = None
    ending_intent: str | None = None
    ending_locked: bool = False
    ending_updated_at: datetime | None = None
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


# ---- ChapterGoal (D01 회차 목표 영속화) ----
# 저장 검증 ≠ 생성 검증: 부분·빈 저장을 허용하되 필드당 길이·배열 개수 상한은
# 생성 요청 계약(BriefText, 배열 상한)과 같은 보호 한도를 유지한다.
GoalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class ChapterGoalPayload(BaseModel):
    """저장용 목표 payload — EpisodeBrief와 같은 필드 구조, 전부 선택(부분 저장)."""

    model_config = ConfigDict(extra="forbid")

    emotion_goal: GoalText | None = None
    core_events: list[GoalText] | None = Field(default=None, max_length=3)
    character_choices: list[GoalText] | None = Field(default=None, max_length=4)
    cost: GoalText | None = None
    prohibitions: list[GoalText] | None = Field(default=None, max_length=10)
    next_hook: GoalText | None = None
    ending_intent: GoalText | None = None
    scene_type: Literal["대립", "액션", "정보정리", "감정", "이동"] | None = None
    target_chars_novelpia: int | None = Field(default=None, ge=1000, le=10000)


class ChapterGoalWrite(BaseModel):
    """PUT /chapters/{cid}/goal — expected_goal_version CAS.

    expected_goal_version=null → "현재 목표 없음" 기대(생성). N → 현재 버전 일치 필요.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: int | None = Field(default=None, ge=1)  # 지정 시 실제 회차 소속과 대조
    goal: ChapterGoalPayload
    episode_purpose: EpisodePurpose = "serial"
    expected_goal_version: int | None = Field(ge=1)
    base_manuscript_revision: int | None = Field(default=None, ge=0)


class ChapterGoalVersionOut(BaseModel):
    """현재 목표 한 버전."""

    model_config = ConfigDict(from_attributes=True)

    goal_version: int
    goal: dict
    episode_purpose: EpisodePurpose
    base_manuscript_revision: int | None
    created_at: datetime
    updated_at: datetime


class ChapterGoalOut(BaseModel):
    """회차 목표 응답 — 목표 없음은 goal=null로 오류와 구분한다."""

    chapter_id: int
    project_id: int
    goal: ChapterGoalVersionOut | None
    current_chapter_revision: int
    history_count: int


class ChapterGoalRevisionOut(BaseModel):
    """목표 이력 row — append-only."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_version: int
    goal: dict
    episode_purpose: EpisodePurpose
    base_manuscript_revision: int | None
    restored_from: int | None
    created_at: datetime


class ChapterGoalRestoreRequest(BaseModel):
    """POST /chapters/{cid}/goal/restore — 이력을 새 현재 버전으로 기록."""

    model_config = ConfigDict(extra="forbid")

    goal_version: int = Field(ge=1)
    expected_goal_version: int | None = Field(ge=1)
    base_manuscript_revision: int | None = Field(default=None, ge=0)


# ---- ChapterFlow (D03-1 집필 흐름) ----
# status(초고/수정중/완료, 원고 성숙도 표시)와 독립된 작업 흐름 단계.
# confirmed는 집필 확정이며 연재/발행 완결이 아니다.
FlowStage = Literal["planning", "writing", "revising", "confirmed"]


class ChapterFlowEventOut(BaseModel):
    """집필 흐름 전이 이력 row — append-only."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    from_stage: FlowStage
    to_stage: FlowStage
    goal_version: int | None
    manuscript_revision: int
    created_at: datetime


class ChapterFlowOut(BaseModel):
    """회차 집필 흐름 상태 — 재개 시 앵커(목표 버전·원고 revision)를 함께 돌려준다."""

    chapter_id: int
    project_id: int
    flow_stage: FlowStage
    last_event: ChapterFlowEventOut | None
    current_goal_version: int | None
    current_chapter_revision: int


class ChapterFlowTransition(BaseModel):
    """POST /chapters/{cid}/flow/transition — expected_flow_stage CAS."""

    model_config = ConfigDict(extra="forbid")

    to_stage: FlowStage
    expected_flow_stage: FlowStage


# ---- ChapterResume (D03-2 재개 계약) ----
# 순수 파생 읽기 — 새 상태를 만들지 않는다.
class ChapterResumeSceneOut(BaseModel):
    """다음에 이어쓸 장면 후보 — 본문이 비어 있는 첫 장면."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sort_order: float
    title: str


class ChapterResumeOut(BaseModel):
    """재개 요약 — D03-1 앵커 대비 드리프트 + 미해결 감수 + 다음 장면."""

    chapter_id: int
    project_id: int
    flow_stage: FlowStage
    last_event: ChapterFlowEventOut | None
    current_goal_version: int | None
    current_chapter_revision: int
    goal_changed_since_transition: bool
    manuscript_changed_since_transition: bool
    pending_refine_runs: int
    next_scene: ChapterResumeSceneOut | None
    scene_count: int


# ---- EvidenceLinks (D03-4 근거 연결) ----
# 목표 필드(사건/선택/대가) ↔ 원문 발췌의 수동 링크. 자동 판정 없음(§6.3).
EvidenceLinkField = Literal["core_events", "character_choices", "cost"]


class EvidenceLinkCreate(BaseModel):
    """POST /chapters/{cid}/evidence-links — 발췌문 기반 링크 생성."""

    model_config = ConfigDict(extra="forbid")

    goal_field: EvidenceLinkField
    item_index: int | None = Field(default=None, ge=0)  # 목록 필드 필수, cost는 금지(라우터 검증)
    excerpt: str = Field(min_length=1, max_length=500)


class EvidenceLinkOut(BaseModel):
    """근거 링크 — 저장 필드 + 읽기 시점 파생 상태."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    goal_field: EvidenceLinkField
    item_index: int | None
    goal_item_text: str
    excerpt: str
    goal_version: int  # 링크 생성 시점의 목표 버전 앵커
    current_goal_version: int | None
    manuscript_status: Literal["intact", "broken"]
    goal_status: Literal["unchanged", "drifted", "goal_deleted"]
    created_at: datetime


class EvidenceLinkListOut(BaseModel):
    chapter_id: int
    links: list[EvidenceLinkOut]


# ---- FinalEdition (D03-6 완결본 관리) ----
# 완결본 = 명시적 생성의 불변 스냅샷. 점검표는 파생 읽기 — 자동 완결 판정 없음.


class FinalEditionCreate(BaseModel):
    """POST /projects/{pid}/final-editions."""

    model_config = ConfigDict(extra="forbid")

    label: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=200)] = None


class FinalEditionChapterEntry(BaseModel):
    """완결본 매니페스트의 회차 항목(캡처 순서=sort_order)."""

    chapter_id: int
    title: str
    sort_order: float
    revision: int
    flow_stage: str
    status: str
    chars: int


class FinalEditionOut(BaseModel):
    """완결본 목록 메타 — 본문·매니페스트·점검표는 detail에서만."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    label: str | None
    created_at: datetime
    serial_state: str
    chapter_count: int
    total_chars: int


class FinalEditionDetail(FinalEditionOut):
    manifest: list[FinalEditionChapterEntry]
    content_md: str
    checklist: "CompletionChecklist"


class ChecklistOpenForeshadow(BaseModel):
    id: int
    title: str
    status: str


class ChecklistChapters(BaseModel):
    total: int
    by_stage: dict[str, int]
    unconfirmed: int


class ChecklistForeshadows(BaseModel):
    total: int
    open: list[ChecklistOpenForeshadow]
    by_disposition: dict[str, int]


class ChecklistFinaleGoal(BaseModel):
    chapter_id: int
    title: str


class CompletionChecklist(BaseModel):
    """완결 점검표 — 결말 설계와 실제 상태를 대조하는 파생 사실 나열.

    완결 가능/불가 판정은 하지 않는다(작가 판단). 모든 필드는 읽기 시점
    또는 완결본 캡처 시점의 파생값이다.
    """

    serial_state: str
    serial_completed_at: datetime | None
    chapters: ChecklistChapters
    foreshadows: ChecklistForeshadows
    pending_refine_runs: int
    broken_evidence_links: int
    finale_goals_missing_ending: list[ChecklistFinaleGoal]


FinalEditionDetail.model_rebuild()


# ---- EndingImpact (D03-7 결말 변경 영향) ----


class EndingImpactOpenForeshadow(BaseModel):
    id: int
    title: str


class EndingImpactStaleChapter(BaseModel):
    chapter_id: int
    title: str
    goal_version: int


class EndingImpactFinaleChapter(BaseModel):
    chapter_id: int
    title: str
    has_ending_intent: bool


class EndingImpactOut(BaseModel):
    """결말 변경 영향 — 파생 읽기. 자동 판정 없음.

    - open_foreshadows: status='설치'인 복선 — 결말이 답해야 할 미해결.
    - stale_goal_chapters: ending_updated_at 이전에 저장된 목표를 가진 회차 —
      옛 결말 가정으로 쓰였을 수 있어 대조 대상.
    - finale_chapters: series_finale 목표를 가진 회차와 ending_intent 유무.
    """

    ending_intent: str | None
    ending_locked: bool
    ending_updated_at: datetime | None
    open_foreshadows: list[EndingImpactOpenForeshadow]
    stale_goal_chapters: list[EndingImpactStaleChapter]
    finale_chapters: list[EndingImpactFinaleChapter]


# ---- MemoryEntry (장편 기억 거버넌스) ----
MemoryKind = Literal[
    "summary", "beat", "decision", "fact", "timeline", "relationship_note",
    "arc_summary", "volume_memory",
]
MemoryVisibility = Literal["draft", "approved", "retired"]


class MemoryEntryCreate(BaseModel):
    """작가가 직접 추가하는 기억. source provenance는 서버가 계산한다."""

    model_config = ConfigDict(extra="forbid")

    chapter_id: int | None = Field(default=None, ge=1)
    kind: MemoryKind
    body: str = Field(min_length=1, max_length=20_000)
    effective_from_sort_order: float | None = None
    effective_to_sort_order: float | None = None

    @model_validator(mode="after")
    def validate_effective_range(self):
        for label, value in (
            ("effective_from_sort_order", self.effective_from_sort_order),
            ("effective_to_sort_order", self.effective_to_sort_order),
        ):
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{label} must be finite")
        if (
            self.effective_from_sort_order is not None
            and self.effective_to_sort_order is not None
            and self.effective_from_sort_order > self.effective_to_sort_order
        ):
            raise ValueError("memory effective range is reversed")
        if not self.body.strip():
            raise ValueError("memory body must not be empty")
        return self


class MemoryEntryUpdate(BaseModel):
    """기억의 상태·시간 범위만 수정한다. 본문과 provenance는 append-only다."""

    model_config = ConfigDict(extra="forbid")

    visibility: MemoryVisibility | None = None
    effective_from_sort_order: float | None = None
    effective_to_sort_order: float | None = None

    @model_validator(mode="after")
    def validate_effective_values(self):
        for label, value in (
            ("effective_from_sort_order", self.effective_from_sort_order),
            ("effective_to_sort_order", self.effective_to_sort_order),
        ):
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{label} must be finite")
        if (
            self.effective_from_sort_order is not None
            and self.effective_to_sort_order is not None
            and self.effective_from_sort_order > self.effective_to_sort_order
        ):
            raise ValueError("memory effective range is reversed")
        return self


class MemoryEntryOut(BaseModel):
    """저장 provenance와 현재 원문 기준 stale 상태를 함께 표시한다."""

    id: int
    project_id: int
    chapter_id: int | None
    source_revision: int | None
    source_sha256: str
    kind: MemoryKind
    body: str
    visibility: MemoryVisibility
    effective_from_sort_order: float | None
    effective_to_sort_order: float | None
    provenance: dict
    created_at: datetime
    updated_at: datetime
    stale: bool
    source_chapter_title: str | None
    source_chapter_revision: int | None
    source_chapter_sort_order: float | None


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
CharacterLifecycle = Literal["active", "departed", "deceased", "retired"]


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    aliases: list[str] | None = None
    role: CharacterRole | None = None
    appearance: str | None = None
    personality: str | None = None
    speech_style: str | None = None
    background: str | None = None
    card_json: dict | None = None
    lifecycle_status: CharacterLifecycle = "active"
    lifecycle_chapter_id: int | None = None
    lifecycle_note: str | None = None
    volume_roles: list[dict] | None = None


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    aliases: list[str] | None = None
    role: CharacterRole | None = None
    appearance: str | None = None
    personality: str | None = None
    speech_style: str | None = None
    background: str | None = None
    lifecycle_status: CharacterLifecycle | None = None
    lifecycle_chapter_id: int | None = None
    lifecycle_note: str | None = None
    volume_roles: list[dict] | None = None


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
    lifecycle_status: CharacterLifecycle
    lifecycle_chapter_id: int | None
    lifecycle_chapter_title: str | None
    lifecycle_note: str | None
    volume_roles: list[dict] | None
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


# ---- Legacy AiEndpoint compatibility (read/write only for migration) ----
# 집필 경로는 이 모델을 조회하지 않는다. 기존 로컬 DB와 구버전 도구가
# 안전하게 종료될 수 있도록 API 계약만 임시 유지하며 신규 UI에는 노출하지 않는다.
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
    api_key: str | None = Field(default=None, max_length=4096)
    default_model: str | None = Field(default=None, max_length=255)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    reasoning_effort: Literal["minimal", "low", "medium", "high", "xhigh"] | None = None
    is_default: bool | None = None


class AiEndpointOut(BaseModel):
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
    # 어시스턴트 계획 경로 — 프로젝트의 인물 카드를 자동으로 전부 주입한다.
    # character_ids에 명시된 인물은 앞순서를 유지하고 나머지를 자동으로 채운다.
    auto_characters: bool = False
    auto_character_limit: int = Field(default=12, ge=1, le=30)
    # D02 P3 — POV 인물 시야. 지정된 인물이 모르는 사실·복선을 컨텍스트에서 제외.
    pov_character_id: int | None = Field(default=None, ge=1)
    # 작품별 시장 참고자료 — 승인 pack도 명시적으로 opt-in한 생성에서만 주입
    include_trend_pack: bool = False

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
    """Fixed GPT OAuth request controls; temperature is intentionally unsupported."""

    model: str | None = Field(default=None, max_length=255)  # fixed provider ignores hint
    max_tokens: int | None = Field(default=None, ge=1)


class GenerateReviewOptions(BaseModel):
    """생성 직후 자동 감수 패스 — GPT OAuth provider를 재사용한다.

    provider와 계정은 서버의 고정 OAuth 설정으로 결정하며, 클라이언트가
    endpoint나 API key를 선택하지 않는다. 감수만 실패해도 초안은 이미 수신
    완료된 상태이므로 review_error 이벤트로 통보하고 스트림은 정상 종료한다.
    """

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
    """Medium 장면 병렬 집필 + GPT OAuth provider 감수 요청.

    approved_plan이 있으면 planner 호출을 건너뛰고 작가가 승인한 계획을
    그대로 worker 계약으로 사용한다(계획→승인→집필 흐름의 집필 단계).
    """

    preset_id: int | None = None
    prompt_override: str | None = None
    context: GenerateContext = Field(default_factory=GenerateContext)
    params: GenerateParams = Field(default_factory=GenerateParams)
    worker_limit: int = Field(default=3, ge=2, le=4)
    generation_reasoning_effort: Literal["minimal", "low", "medium", "high", "xhigh"] = "medium"
    review: GenerateReviewOptions = Field(
        default_factory=lambda: GenerateReviewOptions(reasoning_effort="xhigh"))
    approved_plan: ParallelPlan | None = None
    plan_output_id: int | None = Field(default=None, ge=1)  # 승인한 계획 산출물 provenance


class PlanRequest(BaseModel):
    """집필 계획만 생성하는 요청 — 원고를 쓰지 않고 계획을 작가에게 제시한다."""

    preset_id: int | None = None
    prompt_override: str | None = None
    context: GenerateContext = Field(default_factory=GenerateContext)
    params: GenerateParams = Field(default_factory=GenerateParams)
    generation_reasoning_effort: Literal["minimal", "low", "medium", "high", "xhigh"] = "medium"


class PlanResponse(BaseModel):
    """계획 생성 결과 — 검토용 계획 + 생성 이력 앵커."""

    run_id: int | None
    plan_output_id: int | None
    plan: ParallelPlan
    chapter_revision: int | None
    episode_purpose: str


class ReviewRequest(BaseModel):
    """감수 패스 요청 — /ai/generate와 분리된 독립 엔드포인트.

    초안 스트림이 끝난 뒤 별도 호출할 수 있다. provider는 고정 GPT OAuth
    계정이며 클라이언트가 endpoint를 선택하지 않는다.
    """

    model: str | None = Field(default=None, max_length=255)
    reasoning_effort: str | None = Field(default=None, max_length=20)
    max_tokens: int | None = Field(default=None, ge=1)
    draft: str = Field(min_length=1)
    # E1 생성 이력 — 프론트가 알 때만 전송하는 이력 스코프(additive, 미전송 시 null)
    project_id: int | None = Field(default=None, ge=1)
    chapter_id: int | None = Field(default=None, ge=1)


class GenerateRequest(BaseModel):
    """GPT OAuth provider를 사용하는 집필 요청."""

    preset_id: int | None = None
    prompt_override: str | None = None
    context: GenerateContext = Field(default_factory=GenerateContext)
    params: GenerateParams = Field(default_factory=GenerateParams)
    # 기존 인라인 감수 SSE 계약 — 별도 /ai/review와 병행 지원
    review: GenerateReviewOptions | None = None
    # 계획→승인→집필: 작가가 승인한 계획을 계약으로 주입한다(planner 재호출 없음)
    approved_plan: ParallelPlan | None = None
    plan_output_id: int | None = Field(default=None, ge=1)


class AssistantPlanNextRequest(BaseModel):
    """다음 대상 회차의 집필 계획만 생성하는 요청 — 원고는 쓰지 않는다."""

    chapter_id: int | None = Field(default=None, ge=1)  # 미지정 시 첫 빈 회차
    max_tokens: int | None = Field(default=None, ge=1)
    pov_character_id: int | None = Field(default=None, ge=1)
    include_trend_pack: bool = False


class AssistantPlanNextResponse(BaseModel):
    """assistant 경로의 계획 검토 응답 — 작가 승인 전 원고 변경 없음."""

    project_id: int
    chapter_id: int
    chapter_title: str
    chapter_revision: int
    episode_purpose: str
    plan: ParallelPlan
    run_id: int | None
    plan_output_id: int | None


class AssistantGenerateNextRequest(BaseModel):
    """다음 회차 집필 요청 — 결과는 초안 산출물로만 보존되며 원고를 쓰지 않는다.

    approved_plan을 넘기면 planner를 다시 부르지 않고 작가가 승인한 계획을
    프롬프트 계약으로 주입한다(assistant/plan-next의 승인 단계).
    """

    chapter_id: int | None = Field(default=None, ge=1)  # 미지정 시 첫 빈 회차
    max_tokens: int | None = Field(default=None, ge=1)
    pov_character_id: int | None = Field(default=None, ge=1)
    include_trend_pack: bool = False
    approved_plan: ParallelPlan | None = None
    plan_output_id: int | None = Field(default=None, ge=1)


class AssistantGenerateNextResponse(BaseModel):
    """자동 집필 결과 — 초안/미리보기. 원고 적용은 POST …/apply가 유일 경로."""

    project_id: int
    chapter_id: int
    chapter_title: str
    revision: int  # apply의 expected_revision 앵커 — 현재 회차 revision
    content_md: str  # 생성된 초안 텍스트(미적용)
    word_count_cache: int  # 초안의 공백 제외 글자 수
    applied: bool = False  # 원고에 자동 반영됐는지 — 항상 False여야 한다
    run_id: int | None = None
    draft_output_id: int | None = None


class GenerationOutputApplyIn(BaseModel):
    """초안 산출물을 회차 원고에 적용하는 명시적 작가 액션."""

    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)  # CAS 앵커 — 필수


class GenerationOutputApplyResult(BaseModel):
    """apply 결과 — 새 revision과 기록된 처분."""

    output_id: int
    chapter_id: int
    chapter_title: str
    revision: int
    outcome: str


# ---- 생성 이력 (작가 피드백 자가개선 E1/E2) ----
GenerationOutcome = Literal["inserted", "replaced", "copied", "discarded"]


class GenerationOutcomeIn(BaseModel):
    """산출물 처분 기록 — AiPanel 끼워넣기/교체/복사/폐기의 유일한 반영 경로."""

    model_config = ConfigDict(extra="forbid")
    outcome: GenerationOutcome
    landed_text: str | None = None  # 실제 삽입·교체된 텍스트(편집 후 반영이면 원본과 다를 수 있음)
    chapter_revision: int | None = Field(default=None, ge=0)  # 처분 시점 revision 앵커


class GenerationOutputOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    channel: str
    scene_order: int | None
    output_sha256: str
    output_chars: int
    outcome: str
    outcome_events_json: list
    chapter_revision_at_action: int | None
    outcome_at: datetime | None
    created_at: datetime


class GenerationOutputDetail(GenerationOutputOut):
    output_text: str
    landed_text: str | None


class GenerationRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None
    chapter_id: int | None
    surface: str
    preset_id: int | None
    model: str | None
    reasoning_effort: str | None
    prompt_chars: int
    status: str
    wall_ms: int
    created_at: datetime
    outputs: list[GenerationOutputOut] = []


class GenerationRunDetail(GenerationRunOut):
    input_sha256: str | None
    input_manifest_json: dict | None
    applied_rules_json: list | None
    ai_usage_id: int | None
    outputs: list[GenerationOutputDetail] = []


# ---- 결정론 생성 분석 (E3) — LLM 없는 이력 집계 ----

class SurfaceAcceptStats(BaseModel):
    surface: str
    runs: int
    outputs: int
    outcome_counts: dict[str, int]
    accept_rate: float | None  # (inserted+replaced)/처분 결정된 산출물
    avg_wall_ms: float


class EditDistanceEntry(BaseModel):
    output_id: int
    chapter_id: int | None
    channel: str
    surface: str
    ratio: float  # output↔landed 유사도 — 1.0이면 무변경 수용
    output_chars: int
    landed_chars: int
    landed_still_present: bool | None  # 현재 원고에 landed_text 잔존 여부


class DeletedExpressionStat(BaseModel):
    text: str
    count: int
    output_ids: list[int]  # 근거 산출물 링크(최대 10)


class ChannelLengthStats(BaseModel):
    channel: str
    count: int
    avg_chars: float
    min_chars: int
    max_chars: int


class GenerationAnalysisOut(BaseModel):
    project_id: int
    total_runs: int
    total_outputs: int
    surfaces: list[SurfaceAcceptStats]
    edit_distances: list[EditDistanceEntry]
    avg_edit_ratio: float | None
    deleted_expressions: list[DeletedExpressionStat]
    length_distribution: list[ChannelLengthStats]



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
# D03-5 이관 구분 — 닫힌 복선의 처분 라벨
ForeshadowDisposition = Literal["resolved", "intentional_unresolved", "side_story"]


class ForeshadowCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str | None = None
    keywords: list[str] | None = None
    status: ForeshadowStatus = "설치"
    disposition: ForeshadowDisposition | None = None
    audience_knows: bool = False  # 독자가 이미 알게 된 사실인지 (G-045)
    planted_chapter_id: int | None = None
    resolved_chapter_id: int | None = None


class ForeshadowUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = None
    keywords: list[str] | None = None
    status: ForeshadowStatus | None = None
    disposition: ForeshadowDisposition | None = None
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
    disposition: ForeshadowDisposition | None
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
    # D02 — 지정 시 canon 컨텍스트도 해당 인물의 승인된 인지 시야로 제한한다.
    pov_character_id: int | None = Field(default=None, ge=1)


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
    first_chapter_id: int | None = None
    title_candidates: list[str]
    theme: str | None
    used_ai: bool
    fallback: bool


# ---- 작가 개선 규칙 (작가 피드백 자가개선 E4) ----
ImprovementRuleCategory = Literal[
    "style", "deleted_expression", "character_voice", "pacing",
    "length", "recurring_error", "canon_gap", "long_arc",
]
ImprovementRuleStatus = Literal["proposed", "approved", "rejected", "retired"]


class ImprovementRuleEvidence(BaseModel):
    """규칙 제안의 근거 링크 — 산출물/회차 참조 또는 자유 메모."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["generation_output", "chapter", "note"]
    id: int | None = Field(default=None, ge=1)
    text: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_shape(self):
        if self.kind == "note":
            if not (self.text or "").strip():
                raise ValueError("note evidence requires text")
        elif self.id is None:
            raise ValueError(f"{self.kind} evidence requires id")
        return self


class ImprovementRuleCreate(BaseModel):
    """규칙 생성 — HTTP 경로는 항상 author_written. 작가가 직접 쓴 규칙은
    생성 즉시 approved로 둘 수 있다(생성 자체가 명시 승인)."""

    model_config = ConfigDict(extra="forbid")
    category: ImprovementRuleCategory
    rule_text: str = Field(min_length=1, max_length=500)
    status: Literal["proposed", "approved"] = "proposed"
    rationale: str | None = Field(default=None, max_length=2000)
    evidence: list[ImprovementRuleEvidence] = Field(default_factory=list, max_length=20)


class ImprovementRuleUpdate(BaseModel):
    """본문 수정은 proposed 상태에서만 가능 — 승인 후엔 retire+재제안."""

    model_config = ConfigDict(extra="forbid")
    category: ImprovementRuleCategory | None = None
    rule_text: str | None = Field(default=None, min_length=1, max_length=500)
    rationale: str | None = Field(default=None, max_length=2000)
    evidence: list[ImprovementRuleEvidence] | None = Field(default=None, max_length=20)


class ImprovementRuleDecision(BaseModel):
    """상태 전이 — approve: proposed→approved, reject: proposed→rejected,
    retire: approved→retired. 그 외 전이는 409."""

    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject", "retire"]


class ImprovementRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    category: str
    rule_text: str
    status: str
    source: str
    evidence_json: list
    rationale: str | None
    status_events_json: list
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ImprovementProposalResult(BaseModel):
    """E5 제안 job 결과 — 만들어진 proposed 초안과 평가 통계."""

    created: list[ImprovementRuleOut]
    created_count: int
    skipped_existing: int
    signals_evaluated: int


# ---- 레퍼런스 스타일 분석 (문체 프로파일 초안 생성) ----
class StyleAnalysisRequest(BaseModel):
    """작가가 직접 붙여넣은 레퍼런스 텍스트 — 외부 자동 수집 없음."""

    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=200, max_length=20000)


class StyleAnalysisResponse(BaseModel):
    """결정적 지표 + LLM 합성 프로파일 초안 — 저장하지 않고 반환만 한다."""

    metrics: dict
    profile_draft: str


# ---- 자동 요약 잡 (D04 — 멱등 backfill) ----

class SummaryJobOut(BaseModel):
    id: int
    project_id: int
    chapter_id: int | None
    memory_entry_id: int | None
    kind: str
    status: str
    source_revision: int
    source_sort_order: float
    source_content_length: int
    prompt_version: str
    provider_identity: str
    model_snapshot: str
    attempt_count: int
    error: str | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SummaryJobPlanRequest(BaseModel):
    """회차 요약 잡 계획 — 생략하면 본문 있는 전 회차를 대상으로 한다."""

    chapter_ids: list[int] | None = None
    include_arc: bool = True
    include_volume: bool = True


class SummaryJobPlanResult(BaseModel):
    summary: dict
    arc: dict | None = None
    volume: dict | None = None


class SummaryJobRunResult(BaseModel):
    processed: list[SummaryJobOut]


# ---- 인지 상태·사건 영향 (D02) ----

KnowledgeSubjectType = Literal["author", "reader", "character"]
KnowledgeTargetKind = Literal["fact", "foreshadow", "lore", "event"]
KnowledgeStatus = Literal["unaware", "aware", "false_belief", "forgotten"]
CognitiveVisibility = Literal["draft", "approved", "retired"]


class KnowledgeStateCreate(BaseModel):
    """작가가 직접 기록하는 인지 상태. subject=character일 때만 character_id."""

    model_config = ConfigDict(extra="forbid")

    subject_type: KnowledgeSubjectType
    character_id: int | None = Field(default=None, ge=1)
    target_kind: KnowledgeTargetKind
    target_id: int = Field(ge=1)
    status: KnowledgeStatus
    revealed_chapter_id: int | None = Field(default=None, ge=1)
    effective_from_sort_order: float | None = None

    @model_validator(mode="after")
    def validate_subject_character(self):
        if self.subject_type == "character":
            if self.character_id is None:
                raise ValueError("character_id required for subject_type=character")
        elif self.character_id is not None:
            raise ValueError("character_id only allowed for subject_type=character")
        if self.effective_from_sort_order is not None and not math.isfinite(
            self.effective_from_sort_order
        ):
            raise ValueError("effective_from_sort_order must be finite")
        return self


class KnowledgeStateUpdate(BaseModel):
    """인지 상태는 append-only — visibility·상태 전이만 허용."""

    model_config = ConfigDict(extra="forbid")

    status: KnowledgeStatus | None = None
    visibility: CognitiveVisibility | None = None
    revealed_chapter_id: int | None = Field(default=None, ge=1)
    effective_from_sort_order: float | None = None

    @model_validator(mode="after")
    def validate_finite(self):
        if self.effective_from_sort_order is not None and not math.isfinite(
            self.effective_from_sort_order
        ):
            raise ValueError("effective_from_sort_order must be finite")
        return self


class KnowledgeStateOut(BaseModel):
    id: int
    project_id: int
    subject_type: KnowledgeSubjectType
    character_id: int | None
    character_name: str | None
    target_kind: KnowledgeTargetKind
    target_id: int
    status: KnowledgeStatus
    revealed_chapter_id: int | None
    revealed_chapter_title: str | None
    effective_from_sort_order: float | None
    visibility: CognitiveVisibility
    source_sha256: str | None
    generated_by: str | None
    provenance: dict | None
    created_at: datetime
    updated_at: datetime


class EventImpactCreate(BaseModel):
    """작가가 직접 기록하는 사건 영향."""

    model_config = ConfigDict(extra="forbid")

    chapter_id: int = Field(ge=1)
    label: str = Field(min_length=1, max_length=255)
    character_deltas: list[dict] = Field(default_factory=list)
    relationship_deltas: list[dict] = Field(default_factory=list)
    foreshadow_deltas: list[dict] = Field(default_factory=list)
    state_after: str | None = Field(default=None, max_length=10_000)

    @model_validator(mode="after")
    def validate_label(self):
        if not self.label.strip():
            raise ValueError("label must not be empty")
        return self


class EventImpactUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, min_length=1, max_length=255)
    character_deltas: list[dict] | None = None
    relationship_deltas: list[dict] | None = None
    foreshadow_deltas: list[dict] | None = None
    state_after: str | None = Field(default=None, max_length=10_000)
    visibility: CognitiveVisibility | None = None


class EventImpactOut(BaseModel):
    id: int
    project_id: int
    chapter_id: int
    chapter_title: str | None
    chapter_sort_order: float | None
    label: str
    character_deltas: list[dict]
    relationship_deltas: list[dict]
    foreshadow_deltas: list[dict]
    state_after: str | None
    visibility: CognitiveVisibility
    source_sha256: str | None
    generated_by: str | None
    provenance: dict | None
    created_at: datetime
    updated_at: datetime


class KnowledgeVisibleRequest(BaseModel):
    """특정 시점·주체 기준 인지 조회."""

    model_config = ConfigDict(extra="forbid")

    subject_type: KnowledgeSubjectType
    character_id: int | None = Field(default=None, ge=1)
    at_sort_order: float | None = None

    @model_validator(mode="after")
    def validate_subject_character(self):
        if self.subject_type == "character" and self.character_id is None:
            raise ValueError("character_id required for subject_type=character")
        if self.subject_type != "character" and self.character_id is not None:
            raise ValueError("character_id only allowed for subject_type=character")
        if self.at_sort_order is not None and not math.isfinite(self.at_sort_order):
            raise ValueError("at_sort_order must be finite")
        return self


class KnowledgeVisibleEntry(BaseModel):
    target_kind: KnowledgeTargetKind
    target_id: int
    status: KnowledgeStatus


class KnowledgeVisibleOut(BaseModel):
    subject_type: KnowledgeSubjectType
    character_id: int | None
    at_sort_order: float | None
    entries: list[KnowledgeVisibleEntry]
