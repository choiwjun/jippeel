"""project final editions (D03-6) — 완결본 관리

Revision ID: 7b8c9d0e1f25
Revises: 6a7b8c9d0e14
Create Date: 2026-09-13

project_final_editions: 명시적 생성 시점의 완결본 불변 스냅샷
(조립 원고 content_md + 회차 매니페스트 + 동결 완결 점검표).
UPDATE 경로 없음 — 삭제만 명시적. 신규 테이블이라 FK pragma 래핑 불필요.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7b8c9d0e1f25"
down_revision: Union[str, Sequence[str], None] = "6a7b8c9d0e14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_final_editions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("serial_state", sa.String(20), nullable=False),
        sa.Column("chapter_count", sa.Integer(), nullable=False),
        sa.Column("total_chars", sa.Integer(), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("checklist_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_final_editions_project_id",
        "project_final_editions",
        ["project_id"],
    )
    op.create_index(
        "ix_project_final_editions_created_at",
        "project_final_editions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_final_editions_created_at",
        table_name="project_final_editions",
    )
    op.drop_index(
        "ix_project_final_editions_project_id",
        table_name="project_final_editions",
    )
    op.drop_table("project_final_editions")
