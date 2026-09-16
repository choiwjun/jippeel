"""add project-scoped trend packs."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "i4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "h3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_trend_packs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=32), server_default="trend-pack-v1", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("source", sa.String(length=20), server_default="author", nullable=False),
        sa.Column("as_of", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft','approved','retired')", name="ck_project_trend_pack_status"),
        sa.CheckConstraint("source IN ('author','research','imported')", name="ck_project_trend_pack_source"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_project_trend_pack_project"),
    )
    op.create_index("ix_project_trend_packs_project_id", "project_trend_packs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_trend_packs_project_id", table_name="project_trend_packs")
    op.drop_table("project_trend_packs")
