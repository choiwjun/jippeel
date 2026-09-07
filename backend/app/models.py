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

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Chapter.sort_order"
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
    canon_runs: Mapped[list["CanonRun"]] = relationship(
        cascade="all, delete-orphan")
    quality_checks: Mapped[list["QualityCheck"]] = relationship(
        cascade="all, delete-orphan")

    __table_args__ = (CheckConstraint("status IN ('초고','수정중','완료')", name="ck_chapter_status"),)


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
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list | None] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="설치")
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

    project: Mapped["Project"] = relationship(back_populates="characters")


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
