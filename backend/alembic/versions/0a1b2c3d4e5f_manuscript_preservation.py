"""manuscript preservation revisions and snapshots

Revision ID: 0a1b2c3d4e5f
Revises: f9a1b2c3d4e5
Create Date: 2026-09-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "f9a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("chapters", schema=None) as batch_op:
        batch_op.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "chapter_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("chapter_id", "revision", name="uq_chapter_snapshots_chapter_revision"),
    )
    op.create_index("ix_chapter_snapshots_chapter_id", "chapter_snapshots", ["chapter_id"])
    op.create_index("ix_chapter_snapshots_created_at", "chapter_snapshots", ["created_at"])

    with op.batch_alter_table("refine_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("base_revision", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("refine_runs", schema=None) as batch_op:
        batch_op.drop_column("base_revision")

    op.drop_index("ix_chapter_snapshots_created_at", table_name="chapter_snapshots")
    op.drop_index("ix_chapter_snapshots_chapter_id", table_name="chapter_snapshots")
    op.drop_table("chapter_snapshots")

    with op.batch_alter_table("chapters", schema=None) as batch_op:
        batch_op.drop_column("revision")
