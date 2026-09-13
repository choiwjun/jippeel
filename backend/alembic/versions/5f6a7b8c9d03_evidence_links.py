"""evidence links (D03-4) — 목표 필드 ↔ 원문 발췌의 수동 링크

Revision ID: 5f6a7b8c9d03
Revises: 4e5f6a7b8c92
Create Date: 2026-09-13

chapter_goal_evidence_links 테이블 생성. 새 테이블만 추가하므로
기존 테이블 재작성·FK pragma 조정이 필요 없다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5f6a7b8c9d03"
down_revision: Union[str, Sequence[str], None] = "4e5f6a7b8c92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chapter_goal_evidence_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_version", sa.Integer(), nullable=False),
        sa.Column("goal_field", sa.String(40), nullable=False),
        sa.Column("item_index", sa.Integer(), nullable=True),
        sa.Column("goal_item_text", sa.String(500), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "goal_field IN ('core_events','character_choices','cost')",
            name="ck_evidence_link_field",
        ),
    )
    op.create_index(
        "ix_chapter_goal_evidence_links_chapter_id",
        "chapter_goal_evidence_links",
        ["chapter_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chapter_goal_evidence_links_chapter_id",
        table_name="chapter_goal_evidence_links",
    )
    op.drop_table("chapter_goal_evidence_links")
