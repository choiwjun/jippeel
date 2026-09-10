"""provenance-aware long memory entries

Revision ID: 1b2c3d4e5f60
Revises: 0a1b2c3d4e5f
Create Date: 2026-09-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1b2c3d4e5f60"
down_revision: Union[str, Sequence[str], None] = "0a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "memory_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=True),
        sa.Column("source_revision", sa.Integer(), nullable=True),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("effective_from_sort_order", sa.Float(), nullable=True),
        sa.Column("effective_to_sort_order", sa.Float(), nullable=True),
        sa.Column("provenance_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('summary','beat','decision','fact','timeline','relationship_note')",
            name="ck_memory_entry_kind",
        ),
        sa.CheckConstraint(
            "visibility IN ('draft','approved','retired')",
            name="ck_memory_entry_visibility",
        ),
    )
    op.create_index("ix_memory_entries_project_id", "memory_entries", ["project_id"])
    op.create_index("ix_memory_entries_chapter_id", "memory_entries", ["chapter_id"])


def downgrade() -> None:
    op.drop_index("ix_memory_entries_chapter_id", table_name="memory_entries")
    op.drop_index("ix_memory_entries_project_id", table_name="memory_entries")
    op.drop_table("memory_entries")
