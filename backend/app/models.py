"""SQLAlchemy 2.x 모델 — 사양 §4 데이터 모델 개요."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, CheckConstraint, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    genre: Mapped[str | None] = mapped_column(String(100))
    synopsis: Mapped[str | None] = mapped_column(Text)
    platform_note: Mapped[str | None] = mapped_column(Text)  # 플랫폼 메모
    memo: Mapped[str | None] = mapped_column(Text)  # 부트스트랩 메타(후보 제목·주제의식 등)
    style_profile: Mapped[str | None] = mapped_column(Text)  # 작품 문체 프로파일(G-040)
    trend_pack: Mapped["ProjectTrendPack | None"] = relationship(
        back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    # D03-3 연재 상태 — 회차 flow_stage/confirmed(원고 수준)와 다른 수명주기. ongoing|hiatus|completed
    serial_state: Mapped[str] = mapped_column(
        String(20), default="ongoing", server_default="ongoing"
    )
    serial_completed_at: Mapped[datetime | None] = mapped_column()  # completed 진입 시각
    # D03-7 작품 수준 결말 후보 — 회차 목표 ending_intent와 별개. 잠금은 실수 방지이며
    # 변경 자체는 금지하지 않는다(해제를 같은 요청에 포함하면 허용).
    ending_intent: Mapped[str | None] = mapped_column(Text)
    ending_locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    ending_updated_at: Mapped[datetime | None] = mapped_column()  # ending_intent 실제 변경 시각

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Chapter.sort_order"
    )
    memory_entries: Mapped[list["MemoryEntry"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    volume_notes: Mapped[list["VolumeNote"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    characters: Mapped[list["Character"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    lore_entries: Mapped[list["LoreEntry"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    foreshadows: Mapped[list["Foreshadow"]] = relationship(
        cascade="all, delete-orphan"
    )
    final_editions: Mapped[list["ProjectFinalEdition"]] = relationship(
        cascade="all, delete-orphan"
    )
    knowledge_states: Mapped[list["KnowledgeState"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    event_impacts: Mapped[list["EventImpact"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "serial_state IN ('ongoing','hiatus','completed')",
            name="ck_project_serial_state",
        ),
    )


class ProjectTrendPack(TimestampMixin, Base):
    """작품별 시장 참고자료 — 정본·사실이 아닌 명시적 opt-in 자료."""

    __tablename__ = "project_trend_packs"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_project_trend_pack_project"),
        CheckConstraint(
            "status IN ('draft','approved','retired')",
            name="ck_project_trend_pack_status",
        ),
        CheckConstraint(
            "source IN ('author','research','imported')",
            name="ck_project_trend_pack_source",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    schema_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="trend-pack-v1", server_default="trend-pack-v1"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft"
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="author", server_default="author"
    )
    as_of: Mapped[datetime] = mapped_column(nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    project: Mapped["Project"] = relationship(back_populates="trend_pack")


class Chapter(TimestampMixin, Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    volume: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)  # 권 (Q1 결정안: 권 없는 평면 회차 — NULL 허용)
    sort_order: Mapped[float] = mapped_column(Float, default=0.0)  # 정렬 순서
    title: Mapped[str] = mapped_column(String(255), default="")
    content_md: Mapped[str] = mapped_column(Text, default="")
    # 초고|수정중|완료 (사양 S2 상태 칩)
    status: Mapped[str] = mapped_column(String(20), default="초고")
    # D03-1 집필 흐름 단계 — status(원고 성숙도 표시)와 독립. planning|writing|revising|confirmed
    flow_stage: Mapped[str] = mapped_column(
        String(20), default="planning", server_default="planning"
    )
    word_count_cache: Mapped[int] = mapped_column(Integer, default=0)  # 노벨피아 모드 글자 수(공백·문장부호·특수문자 제외)
    revision: Mapped[int] = mapped_column(Integer, default=0)  # 원고 낙관적 잠금 revision
    memo: Mapped[str | None] = mapped_column(Text)  # 빠른 메모 (FR-108, v0.3)

    project: Mapped["Project"] = relationship(back_populates="chapters")
    refine_runs: Mapped[list["RefineRun"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan"
    )
    scenes: Mapped[list["Scene"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan",
        order_by="Scene.sort_order"
    )
    snapshots: Mapped[list["ChapterSnapshot"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan", order_by="ChapterSnapshot.id"
    )
    memory_entries: Mapped[list["MemoryEntry"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan"
    )
    goal: Mapped["ChapterGoal | None"] = relationship(
        back_populates="chapter", cascade="all, delete-orphan", uselist=False
    )
    goal_revisions: Mapped[list["ChapterGoalRevision"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan",
        order_by="ChapterGoalRevision.goal_version"
    )
    flow_events: Mapped[list["ChapterFlowEvent"]] = relationship(
        back_populates="chapter", cascade="all",
        order_by="ChapterFlowEvent.id"
    )
    evidence_links: Mapped[list["ChapterGoalEvidenceLink"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan",
        order_by="ChapterGoalEvidenceLink.id"
    )
    canon_runs: Mapped[list["CanonRun"]] = relationship(
        cascade="all, delete-orphan")
    quality_checks: Mapped[list["QualityCheck"]] = relationship(
        cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('초고','수정중','완료')", name="ck_chapter_status"),
        CheckConstraint(
            "flow_stage IN ('planning','writing','revising','confirmed')",
            name="ck_chapter_flow_stage",
        ),
    )


class ChapterSnapshot(Base):
    """회차 본문 교체 전 복구본."""

    __tablename__ = "chapter_snapshots"
    __table_args__ = (
        UniqueConstraint("chapter_id", "revision", name="uq_chapter_snapshots_chapter_revision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, server_default=func.now(), index=True)

    chapter: Mapped["Chapter"] = relationship(back_populates="snapshots")


class ChapterGoal(TimestampMixin, Base):
    """회차 목표(브리프) 현재값 — D01.

    원고 정본이 아닌 작가 의도 데이터다. goal_version은 회차 내 단조 증가하는
    독립 낙관적 버전이며 Chapter.revision과 무관하다. 목표 저장은 snapshot을
    만들지 않고 원문 CAS에 영향을 주지 않는다.
    """

    __tablename__ = "chapter_goals"
    __table_args__ = (
        CheckConstraint(
            "episode_purpose IN ('serial','volume_end','series_finale')",
            name="ck_chapter_goal_purpose",
        ),
        CheckConstraint("goal_version >= 1", name="ck_chapter_goal_version_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    goal_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    episode_purpose: Mapped[str] = mapped_column(String(20), default="serial", nullable=False)
    goal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    base_manuscript_revision: Mapped[int | None] = mapped_column(Integer)

    chapter: Mapped["Chapter"] = relationship(back_populates="goal")


class ChapterGoalRevision(Base):
    """회차 목표 변경 이력 — append-only. 복원은 새 버전 기록으로 처리한다."""

    __tablename__ = "chapter_goal_revisions"
    __table_args__ = (
        UniqueConstraint("chapter_id", "goal_version", name="uq_goal_revisions_chapter_version"),
        CheckConstraint(
            "episode_purpose IN ('serial','volume_end','series_finale')",
            name="ck_goal_revision_purpose",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    goal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    goal_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    episode_purpose: Mapped[str] = mapped_column(String(20), default="serial", nullable=False)
    base_manuscript_revision: Mapped[int | None] = mapped_column(Integer)
    restored_from: Mapped[int | None] = mapped_column(Integer)  # 복원 원본 goal_version
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, server_default=func.now(), index=True)

    chapter: Mapped["Chapter"] = relationship(back_populates="goal_revisions")


class ChapterFlowEvent(Base):
    """D03-1 집필 흐름 전이 로그 — append-only.

    goal_version은 전이 시점 저장본 목표의 버전 참조(내용 복사 아님)이고
    manuscript_revision은 전이 시점의 Chapter.revision이다. 전이 자체는
    revision을 증가시키지 않고 snapshot·memo·목표를 건드리지 않는다.
    """

    __tablename__ = "chapter_flow_events"
    __table_args__ = (
        CheckConstraint(
            "from_stage IN ('planning','writing','revising','confirmed')",
            name="ck_flow_event_from_stage",
        ),
        CheckConstraint(
            "to_stage IN ('planning','writing','revising','confirmed')",
            name="ck_flow_event_to_stage",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    from_stage: Mapped[str] = mapped_column(String(20), nullable=False)
    to_stage: Mapped[str] = mapped_column(String(20), nullable=False)
    goal_version: Mapped[int | None] = mapped_column(Integer)
    manuscript_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, server_default=func.now(), index=True)

    chapter: Mapped["Chapter"] = relationship(back_populates="flow_events")


class ChapterGoalEvidenceLink(Base):
    """D03-4 근거 연결 — 목표 필드 ↔ 원문 발췌의 수동 링크.

    offset 대신 발췌문을 저장해 편집 후에도 정확히 매칭된다. 읽기 시점에
    원문 포함 여부(manuscript_status)와 목표 항목 스냅샷 대비(goal_status)를
    파생한다 — 자동 판정 없이 사용자의 명시적 주장만 저장한다.
    """

    __tablename__ = "chapter_goal_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "goal_field IN ('core_events','character_choices','cost')",
            name="ck_evidence_link_field",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    goal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    goal_field: Mapped[str] = mapped_column(String(40), nullable=False)
    item_index: Mapped[int | None] = mapped_column(Integer)
    goal_item_text: Mapped[str] = mapped_column(String(500), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, server_default=func.now())

    chapter: Mapped["Chapter"] = relationship(back_populates="evidence_links")


class MemoryEntry(TimestampMixin, Base):
    """Provenance-aware long-memory projection, never the manuscript source of truth."""

    __tablename__ = "memory_entries"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('summary','beat','decision','fact','timeline',"
            "'relationship_note','arc_summary','volume_memory')",
            name="ck_memory_entry_kind",
        ),
        CheckConstraint(
            "visibility IN ('draft','approved','retired')",
            name="ck_memory_entry_visibility",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), index=True)
    source_revision: Mapped[int | None] = mapped_column(Integer)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    effective_from_sort_order: Mapped[float | None] = mapped_column(Float)
    effective_to_sort_order: Mapped[float | None] = mapped_column(Float)
    provenance_json: Mapped[dict | None] = mapped_column(JSON, default=dict)

    project: Mapped["Project"] = relationship(back_populates="memory_entries")
    chapter: Mapped["Chapter | None"] = relationship(back_populates="memory_entries")


class SummaryJob(TimestampMixin, Base):
    """자동 요약 backfill 작업 — D04-1.

    provider-free planner가 만든 manifest를 영속한다. 동일 manifest 조합은
    idempotency_key unique 제약으로 한 번만 생성된다. worker는 주입된 provider를
    호출해 결과를 MemoryEntry(draft)로 append만 한다 — 자동 승인 없음.
    chapter 삭제 시 job 행은 chapter_id SET NULL로 보존(감사).

    request_options_json은 planner의 비밀 키 패턴 거부를 거친 값만 영속한다 —
    패턴에 맞지 않는 키 이름으로 credential을 넣지 않는 것은 호출자 책임이다.
    """

    __tablename__ = "summary_jobs"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('summary','arc','volume')", name="ck_summary_job_kind"
        ),
        CheckConstraint(
            "status IN ('planned','running','draft_saved','skipped_empty',"
            "'stale_source','provider_error','rejected','duplicate_skipped')",
            name="ck_summary_job_status",
        ),
        UniqueConstraint("idempotency_key", name="uq_summary_job_idempotency_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), index=True
    )
    memory_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("memory_entries.id", ondelete="SET NULL")
    )
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_sort_order: Mapped[float] = mapped_column(Float, nullable=False)
    source_content_length: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="summary", nullable=False)
    source_ids_json: Mapped[list | None] = mapped_column(JSON)
    prompt_version: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_identity: Mapped[str] = mapped_column(String(120), nullable=False)
    model_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    request_options_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_options_json: Mapped[dict | None] = mapped_column(JSON)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="planned", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column()
    lease_owner: Mapped[str | None] = mapped_column(String(128), index=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column()

    memory_entry: Mapped["MemoryEntry | None"] = relationship()


class Scene(TimestampMixin, Base):
    """장면 — 회차 → 장면 계층 (고도화 G-010, 백로그 P2).

    회차 본문(content_md)은 통짜로 유지하되, 작가가 장면 단위로
    AI 생성·재작성을 할 수 있게 병행 저장한다.
    """

    __tablename__ = "scenes"

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), index=True, nullable=False)
    sort_order: Mapped[float] = mapped_column(Float, default=0.0)
    title: Mapped[str] = mapped_column(String(255), default="")
    content_md: Mapped[str] = mapped_column(Text, default="")

    chapter: Mapped["Chapter"] = relationship(back_populates="scenes")


class Foreshadow(TimestampMixin, Base):
    """복선 — 설치/회수 상태 관리 (고도화 G-020).

    status: 설치(아직 회수 안 됨) | 회수(해결됨) | 보류(의도적으로 유예)
    미회수(설치) 복선은 AI 생성 시 [복선 경고] 블록으로 주입된다(G-022).
    """

    __tablename__ = "foreshadows"
    __table_args__ = (
        CheckConstraint("status IN ('설치','회수','보류')", name="ck_foreshadow_status"),
        CheckConstraint(
            "disposition IS NULL OR disposition IN ('resolved','intentional_unresolved','side_story')",
            name="ck_foreshadow_disposition",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list | None] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="설치")
    # D03-5 이관 구분 — 닫힌 복선의 처분: resolved(해결) / intentional_unresolved(의도적
    # 미해결) / side_story(외전 이관). status='설치'이면 반드시 NULL(라우터에서 강제).
    disposition: Mapped[str | None] = mapped_column(String(30), nullable=True)
    audience_knows: Mapped[bool] = mapped_column(Boolean, default=False)  # 독자가 이미 알게 됨(G-045)
    planted_chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id"), nullable=True)
    resolved_chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id"), nullable=True)


class VolumeNote(TimestampMixin, Base):
    """권 개요 — 1권 단위 감정 곡선·고봉 설계 레이어 (고도화 G-050).

    부트스트랩 목차(회차 memo)와 회차 본문 사이의 중간 서사 레이어.
    """

    __tablename__ = "volume_notes"
    __table_args__ = (
        CheckConstraint("volume >= 1", name="ck_volume_note_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="")
    overview: Mapped[str | None] = mapped_column(Text)       # 권 전체 개요
    emotion_curve: Mapped[str | None] = mapped_column(Text)  # 감정 곡선 설계
    climax_note: Mapped[str | None] = mapped_column(Text)    # 권 고봉(클라이맥스) 노트

    project: Mapped["Project"] = relationship(back_populates="volume_notes")


class CanonRun(TimestampMixin, Base):
    """canon 충돌 검사 이력 — 고도화 G-023 후속(응답만 반환 → 이력 보존)."""

    __tablename__ = "canon_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), index=True, nullable=False)
    model: Mapped[str | None] = mapped_column(String(255))
    issues_json: Mapped[list | None] = mapped_column(JSON, default=list)
    context_json: Mapped[dict | None] = mapped_column(JSON)


class QualityCheck(TimestampMixin, Base):
    """회차 품질 진단 이력 — 고도화 G-030 후속(점수 추이 그래프용).

    content_hash가 직전 기록과 같으면 재기록하지 않는다(중복 방지).
    """

    __tablename__ = "quality_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), index=True, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    metrics_json: Mapped[dict | None] = mapped_column(JSON)
    suggestions_json: Mapped[list | None] = mapped_column(JSON, default=list)
    presets_json: Mapped[list | None] = mapped_column(JSON, default=list)


class AiUsage(Base):
    """AI 사용량 기록 — 고도화 G-060 (문자량 기반, 엔드포인트별 집계).

    토큰 수는 엔드포인트별 편차가 커서 집계 신뢰가 낮아 문자량으로 기록한다.
    """

    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # generate|review|canon|bootstrap|foreshadow_suggest
    model: Mapped[str | None] = mapped_column(String(255))
    endpoint_name: Mapped[str | None] = mapped_column(String(255))
    prompt_chars: Mapped[int] = mapped_column(Integer, default=0)
    completion_chars: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, server_default=func.now(), index=True)


class Character(TimestampMixin, Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[list | None] = mapped_column(JSON, default=list)  # 별명 []
    role: Mapped[str | None] = mapped_column(String(50))  # 주연|조연|...
    appearance: Mapped[str | None] = mapped_column(Text)
    personality: Mapped[str | None] = mapped_column(Text)
    speech_style: Mapped[str | None] = mapped_column(Text)
    background: Mapped[str | None] = mapped_column(Text)
    card_json: Mapped[dict | None] = mapped_column(JSON)  # ST 호환 확장 여지
    # 라이프사이클 — 퇴장·사망·권별 역할을 first-class 필드로 관리
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # active|departed|deceased|retired
    lifecycle_chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id"), nullable=True
    )  # 퇴장·사망이 발생한 회차
    lifecycle_note: Mapped[str | None] = mapped_column(Text)  # 퇴장·사망 사유 메모
    volume_roles: Mapped[list | None] = mapped_column(JSON, default=list)
    # [{"volume":1,"role":"주연"},{"volume":2,"role":"조연"}]

    project: Mapped["Project"] = relationship(back_populates="characters")
    lifecycle_chapter: Mapped["Chapter"] = relationship()


class Relationship(Base):
    """관계 (MVP: 단순 텍스트 링크)."""

    __tablename__ = "relationships"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id"), index=True, nullable=False
    )
    to_character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id"), index=True, nullable=False
    )
    label: Mapped[str | None] = mapped_column(String(255))  # 예: "주군-가신"
    note: Mapped[str | None] = mapped_column(Text)


class LoreEntry(TimestampMixin, Base):
    __tablename__ = "lore_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="기타")  # 용어|장소|세력|기타
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list | None] = mapped_column(JSON, default=list)  # 자동 컨텍스트 주입용

    project: Mapped["Project"] = relationship(back_populates="lore_entries")


class AiEndpoint(TimestampMixin, Base):
    """전역 테이블 (프로젝트 독립).

    api_key_encrypted에는 암호문만 저장한다.
    암복호화 인터페이스는 app/services/crypto.py로 추상화하며,
    실제 DPAPI(Python keyring)/Fernet 폴백 구현은 후속 스프린트(사양 §8.2).
    """

    __tablename__ = "ai_endpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(512))
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    default_model: Mapped[str | None] = mapped_column(String(255))
    temperature: Mapped[float | None] = mapped_column(Float, default=0.7)  # None → 파라미터 미전송(Codex 계열 거부)
    reasoning_effort: Mapped[str | None] = mapped_column(String(32))  # minimal|low|medium|high|xhigh — None → 미전송
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class PromptPreset(Base):
    """프롬프트 프리셋 (전역 테이블)."""

    __tablename__ = "prompt_presets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    context_flags: Mapped[list | None] = mapped_column(JSON, default=list)  # chapter/characters/lore


class RefineRun(Base):
    """윤문 실행 기록."""

    __tablename__ = "refine_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), index=True, nullable=False)
    route_hint: Mapped[str | None] = mapped_column(String(20))  # light|standard|heavy
    changed_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    report_json: Mapped[dict | None] = mapped_column(JSON)
    result_text: Mapped[str | None] = mapped_column(Text)
    base_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)

    chapter: Mapped["Chapter"] = relationship(back_populates="refine_runs")


class ProjectFinalEdition(Base):
    """완결본 스냅샷 — D03-6.

    명시적 생성 시점의 전 회차 본문(content_md 조립본)·매니페스트·완결 점검표를
    불변으로 보존한다. 회차 이후 수정·삭제와 무관. UPDATE 경로 없음 — 삭제만
    명시적으로 허용한다.
    """

    __tablename__ = "project_final_editions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    label: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        default=_utcnow, server_default=func.now(), index=True
    )
    serial_state: Mapped[str] = mapped_column(String(20), nullable=False)
    chapter_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    manifest_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    content_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    checklist_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class GenerationRun(TimestampMixin, Base):
    """생성 요청 봉투 — 작가 피드백 자가개선 E1.

    /ai/generate·/ai/generate-parallel·/ai/review 호출 1건의 입력 컨텍스트·
    전송 결과를 보존한다. 프롬프트 원문은 저장하지 않고 sha256·주입 내역만
    남긴다. 산출물과 작가 처분은 GenerationOutput이 담당한다.
    chapter 삭제 시 chapter_id는 SET NULL로 보존(감사), project 삭제 시 CASCADE.
    """

    __tablename__ = "generation_runs"
    __table_args__ = (
        CheckConstraint(
            "surface IN ('generate','generate_parallel','review','plan','assistant_generate')",
            name="ck_generation_run_surface",
        ),
        CheckConstraint(
            "status IN ('completed','provider_error','aborted')",
            name="ck_generation_run_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), index=True
    )
    surface: Mapped[str] = mapped_column(String(32), nullable=False)
    preset_id: Mapped[int | None] = mapped_column(Integer)
    model: Mapped[str | None] = mapped_column(String(255))
    reasoning_effort: Mapped[str | None] = mapped_column(String(20))
    input_sha256: Mapped[str | None] = mapped_column(String(64))
    input_manifest_json: Mapped[dict | None] = mapped_column(JSON, default=dict)
    prompt_chars: Mapped[int] = mapped_column(Integer, default=0)
    applied_rules_json: Mapped[list | None] = mapped_column(JSON)  # E6이 채울 승인 규칙 id
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    wall_ms: Mapped[int] = mapped_column(Integer, default=0)
    ai_usage_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_usage.id", ondelete="SET NULL")
    )

    outputs: Mapped[list["GenerationOutput"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="GenerationOutput.id"
    )


class GenerationOutput(Base):
    """생성 산출물 — run이 만든 개별 텍스트 + 작가 처분.

    작가가 끼워넣기/교체/복사/폐기하는 대상은 호출이 아니라 이 산출물이다.
    outcome은 최신 처분 상태, outcome_events_json은 전이 이력(append-only).
    """

    __tablename__ = "generation_outputs"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('draft','review','refined','plan','worker')",
            name="ck_generation_output_channel",
        ),
        CheckConstraint(
            "outcome IN ('pending','inserted','replaced','copied','discarded')",
            name="ck_generation_output_outcome",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("generation_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    scene_order: Mapped[int | None] = mapped_column(Integer)
    output_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    output_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    output_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    outcome_events_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    landed_text: Mapped[str | None] = mapped_column(Text)
    chapter_revision_at_action: Mapped[int | None] = mapped_column(Integer)
    outcome_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, server_default=func.now())

    run: Mapped["GenerationRun"] = relationship(back_populates="outputs")


class ImprovementRule(TimestampMixin, Base):
    """작품별 개선 규칙 — 작가 피드백 자가개선 E4.

    제안(proposed)은 시스템 분석·작가 작성 모두 가능하지만, 다음 생성에
    적용되는 것은 작가가 명시 승인한 approved 규칙뿐이다. rejected·retired는
    종결이며 규칙 본문은 승인 후 불변 — 수정은 retire + 새 proposed로 한다.
    project 삭제 시 CASCADE — 규칙은 작품에 귀속돼 다른 작품과 섞이지 않는다.
    """

    __tablename__ = "improvement_rules"
    __table_args__ = (
        CheckConstraint(
            "category IN ('style','deleted_expression','character_voice',"
            "'pacing','length','recurring_error','canon_gap','long_arc')",
            name="ck_improvement_rule_category",
        ),
        CheckConstraint(
            "status IN ('proposed','approved','rejected','retired')",
            name="ck_improvement_rule_status",
        ),
        CheckConstraint(
            "source IN ('author_written','system_proposal')",
            name="ck_improvement_rule_source",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed")
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="author_written")
    # 제안 근거 — [{"kind":"generation_output","id":..}|{"kind":"chapter","id":..}|{"kind":"note","text":..}]
    evidence_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rationale: Mapped[str | None] = mapped_column(Text)
    status_events_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    decided_at: Mapped[datetime | None] = mapped_column()


class KnowledgeState(TimestampMixin, Base):
    """주체별 인지 상태 — D02 P1 (작가/독자/인물 시야).

    같은 (subject, target) 쌍의 상태는 append-only로 누적한다. 현재 상태는
    (effective_from_sort_order, id) 기준 가장 최신 행이며 과거 시점 조회는
    경계 이전 행을 고른다. 승인 전 draft는 컨텍스트 주입에서 제외한다.
    """

    __tablename__ = "knowledge_states"
    __table_args__ = (
        CheckConstraint(
            "subject_type IN ('author','reader','character')",
            name="ck_knowledge_state_subject",
        ),
        CheckConstraint(
            "target_kind IN ('fact','foreshadow','lore','event')",
            name="ck_knowledge_state_target",
        ),
        CheckConstraint(
            "status IN ('unaware','aware','false_belief','forgotten')",
            name="ck_knowledge_state_status",
        ),
        CheckConstraint(
            "visibility IN ('draft','approved','retired')",
            name="ck_knowledge_state_visibility",
        ),
        CheckConstraint(
            "subject_type != 'character' OR character_id IS NOT NULL",
            name="ck_knowledge_state_character_required",
        ),
        CheckConstraint(
            "subject_type = 'character' OR character_id IS NULL",
            name="ck_knowledge_state_character_forbidden",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)
    character_id: Mapped[int | None] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    target_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    revealed_chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL")
    )
    effective_from_sort_order: Mapped[float | None] = mapped_column(Float)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    generated_by: Mapped[str | None] = mapped_column(String(64))
    provenance_json: Mapped[dict | None] = mapped_column(JSON, default=dict)

    project: Mapped["Project"] = relationship(back_populates="knowledge_states")
    character: Mapped["Character | None"] = relationship()
    revealed_chapter: Mapped["Chapter | None"] = relationship()


class EventImpact(TimestampMixin, Base):
    """사건 영향 — D02 P1 (회차 안 사건이 남긴 관계·복선·인물 델타).

    사건은 장면 비트와 별개로, 서사 상태에 변화를 남기는 단위다. 델타는
    JSON 배열로 영속하고, 파생 행은 draft로만 생성돼 작가 승인 후에만
    컨텍스트·뷰에 올라간다.
    """

    __tablename__ = "event_impacts"
    __table_args__ = (
        CheckConstraint(
            "visibility IN ('draft','approved','retired')",
            name="ck_event_impact_visibility",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    character_deltas_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    relationship_deltas_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    foreshadow_deltas_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    state_after: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    generated_by: Mapped[str | None] = mapped_column(String(64))
    provenance_json: Mapped[dict | None] = mapped_column(JSON, default=dict)

    project: Mapped["Project"] = relationship(back_populates="event_impacts")
    chapter: Mapped["Chapter"] = relationship()
