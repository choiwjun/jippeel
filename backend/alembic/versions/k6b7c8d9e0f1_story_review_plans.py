"""Separate planned foreshadow payoff and append-only review decisions."""
import sqlalchemy as sa
from alembic import op

revision = "k6b7c8d9e0f1"
down_revision = "j5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("foreshadows", recreate="always",
                              table_kwargs={"sqlite_autoincrement": True}) as batch:
        batch.add_column(sa.Column("planned_resolution_chapter_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
        batch.create_foreign_key("fk_foreshadow_planned_chapter", "chapters", ["planned_resolution_chapter_id"], ["id"])
    op.create_table(
        "story_review_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_key", sa.String(64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("evidence_token", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("proposal", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "item_key", "sequence", name="uq_story_review_sequence"),
        sa.CheckConstraint("decision IN ('adopt','hold','discard')", name="ck_story_review_decision"),
        sa.CheckConstraint("sequence >= 1", name="ck_story_review_sequence"),
    )
    op.create_index("ix_story_review_decisions_project_id", "story_review_decisions", ["project_id"])


def downgrade():
    op.drop_table("story_review_decisions")
    with op.batch_alter_table("foreshadows") as batch:
        batch.drop_constraint("fk_foreshadow_planned_chapter", type_="foreignkey")
        batch.drop_column("planned_resolution_chapter_id")
        batch.drop_column("revision")
