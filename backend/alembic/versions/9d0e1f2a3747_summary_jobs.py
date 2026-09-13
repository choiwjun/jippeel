"""summary_jobs (D04-1) — 자동 요약 backfill 작업 영속

Revision ID: 9d0e1f2a3747
Revises: 8c9d0e1f2636
Create Date: 2026-09-13

provider-free planner의 manifest를 DB에 보존하고 idempotency_key unique로
중복 계획을 차단한다. chapter 삭제 시 job은 chapter_id SET NULL로 감사 보존,
project 삭제는 기존 관례대로 CASCADE.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9d0e1f2a3747"
down_revision: Union[str, Sequence[str], None] = "8c9d0e1f2636"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "summary_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chapter_id",
            sa.Integer(),
            sa.ForeignKey("chapters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "memory_entry_id",
            sa.Integer(),
            sa.ForeignKey("memory_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_sort_order", sa.Float(), nullable=False),
        sa.Column("source_content_length", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="summary"),
        sa.Column("prompt_version", sa.String(length=120), nullable=False),
        sa.Column("provider_identity", sa.String(length=120), nullable=False),
        sa.Column("model_snapshot", sa.String(length=120), nullable=False),
        sa.Column("request_options_hash", sa.String(length=64), nullable=False),
        sa.Column("request_options_json", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="planned"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind = 'summary'", name="ck_summary_job_kind"),
        sa.CheckConstraint(
            "status IN ('planned','running','draft_saved','skipped_empty',"
            "'stale_source','provider_error','rejected','duplicate_skipped')",
            name="ck_summary_job_status",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_summary_job_idempotency_key"),
    )
    op.create_index("ix_summary_jobs_project_id", "summary_jobs", ["project_id"])
    op.create_index("ix_summary_jobs_chapter_id", "summary_jobs", ["chapter_id"])
    op.create_index("ix_summary_jobs_idempotency_key", "summary_jobs", ["idempotency_key"])


def downgrade() -> None:
    op.drop_index("ix_summary_jobs_idempotency_key", table_name="summary_jobs")
    op.drop_index("ix_summary_jobs_chapter_id", table_name="summary_jobs")
    op.drop_index("ix_summary_jobs_project_id", table_name="summary_jobs")
    op.drop_table("summary_jobs")
