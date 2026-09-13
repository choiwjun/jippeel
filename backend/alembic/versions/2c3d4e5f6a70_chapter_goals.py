"""chapter goal persistence (D01) — current value + append-only revisions

Revision ID: 2c3d4e5f6a70
Revises: 1b2c3d4e5f60
Create Date: 2026-09-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2c3d4e5f6a70"
down_revision: Union[str, Sequence[str], None] = "1b2c3d4e5f60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chapter_goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_json", sa.JSON(), nullable=False),
        sa.Column("episode_purpose", sa.String(20), nullable=False, server_default="serial"),
        sa.Column("goal_version", sa.Integer(), nullable=False),
        sa.Column("base_manuscript_revision", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("chapter_id", name="uq_chapter_goals_chapter"),
        sa.CheckConstraint(
            "episode_purpose IN ('serial','volume_end','series_finale')",
            name="ck_chapter_goal_purpose",
        ),
        sa.CheckConstraint("goal_version >= 1", name="ck_chapter_goal_version_positive"),
    )
    op.create_index("ix_chapter_goals_chapter_id", "chapter_goals", ["chapter_id"])

    op.create_table(
        "chapter_goal_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_version", sa.Integer(), nullable=False),
        sa.Column("goal_json", sa.JSON(), nullable=False),
        sa.Column("episode_purpose", sa.String(20), nullable=False, server_default="serial"),
        sa.Column("base_manuscript_revision", sa.Integer(), nullable=True),
        sa.Column("restored_from", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("chapter_id", "goal_version", name="uq_goal_revisions_chapter_version"),
        sa.CheckConstraint(
            "episode_purpose IN ('serial','volume_end','series_finale')",
            name="ck_goal_revision_purpose",
        ),
    )
    op.create_index("ix_chapter_goal_revisions_chapter_id", "chapter_goal_revisions", ["chapter_id"])
    op.create_index("ix_chapter_goal_revisions_created_at", "chapter_goal_revisions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_chapter_goal_revisions_created_at", table_name="chapter_goal_revisions")
    op.drop_index("ix_chapter_goal_revisions_chapter_id", table_name="chapter_goal_revisions")
    op.drop_table("chapter_goal_revisions")
    op.drop_index("ix_chapter_goals_chapter_id", table_name="chapter_goals")
    op.drop_table("chapter_goals")
