"""SQLAlchemy 2.x 모델 — 사양 §4 데이터 모델 개요."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, CheckConstraint, Float, ForeignKey, Integer, String, Text, func
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

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Chapter.sort_order"
    )
    characters: Mapped[list["Character"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    lore_entries: Mapped[list["LoreEntry"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
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
    word_count_cache: Mapped[int] = mapped_column(Integer, default=0)  # 공백 제외 글자 수
    memo: Mapped[str | None] = mapped_column(Text)  # 빠른 메모 (FR-108, v0.3)

    project: Mapped["Project"] = relationship(back_populates="chapters")
    refine_runs: Mapped[list["RefineRun"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan"
    )

    __table_args__ = (CheckConstraint("status IN ('초고','수정중','완료')", name="ck_chapter_status"),)


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
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)

    chapter: Mapped["Chapter"] = relationship(back_populates="refine_runs")
