"""generation_runs + generation_outputs (E1) — 생성 이력·작가 처분 영속

Revision ID: ae1f2b3c4d58
Revises: 9d0e1f2a3747
Create Date: 2026-09-14

AI 생성 요청의 입력 컨텍스트(sha·주입 내역)와 전송 결과를 run 봉투로,
개별 산출물(draft/review/refined/plan/worker)과 작가 처분(outcome)을
output으로 분리해 보존한다. chapter 삭제 시 run은 SET NULL로 감사 보존,
project 삭제는 CASCADE. 원문과 무관한 참조 데이터이므로 원고 복원 경로와
독립이다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ae1f2b3c4d58"
down_revision: Union[str, Sequence[str], None] = "9d0e1f2a3747"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "chapter_id",
            sa.Integer(),
            sa.ForeignKey("chapters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("surface", sa.String(length=32), nullable=False),
        sa.Column("preset_id", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("reasoning_effort", sa.String(length=20), nullable=True),
        sa.Column("input_sha256", sa.String(length=64), nullable=True),
        sa.Column("input_manifest_json", sa.JSON(), nullable=True),
        sa.Column("prompt_chars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("applied_rules_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("wall_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "ai_usage_id",
            sa.Integer(),
            sa.ForeignKey("ai_usage.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "surface IN ('generate','generate_parallel','review')",
            name="ck_generation_run_surface",
        ),
        sa.CheckConstraint(
            "status IN ('completed','provider_error','aborted')",
            name="ck_generation_run_status",
        ),
    )
    op.create_index("ix_generation_runs_project_id", "generation_runs", ["project_id"])
    op.create_index("ix_generation_runs_chapter_id", "generation_runs", ["chapter_id"])

    op.create_table(
        "generation_outputs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("generation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("scene_order", sa.Integer(), nullable=True),
        sa.Column("output_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("output_sha256", sa.String(length=64), nullable=False),
        sa.Column("output_chars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outcome", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("outcome_events_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("landed_text", sa.Text(), nullable=True),
        sa.Column("chapter_revision_at_action", sa.Integer(), nullable=True),
        sa.Column("outcome_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "channel IN ('draft','review','refined','plan','worker')",
            name="ck_generation_output_channel",
        ),
        sa.CheckConstraint(
            "outcome IN ('pending','inserted','replaced','copied','discarded')",
            name="ck_generation_output_outcome",
        ),
    )
    op.create_index("ix_generation_outputs_run_id", "generation_outputs", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_generation_outputs_run_id", table_name="generation_outputs")
    op.drop_table("generation_outputs")
    op.drop_index("ix_generation_runs_chapter_id", table_name="generation_runs")
    op.drop_index("ix_generation_runs_project_id", table_name="generation_runs")
    op.drop_table("generation_runs")
