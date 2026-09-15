"""D02 — 인지 상태(knowledge_states)·사건 영향(event_impacts)

Revision ID: f1a2b3c4d5e6
Revises: e2f3a4b5c6d7
Create Date: 2026-09-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_type", sa.String(20), nullable=False),
        sa.Column("character_id", sa.Integer(),
                  sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=True),
        sa.Column("target_kind", sa.String(20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("revealed_chapter_id", sa.Integer(),
                  sa.ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("effective_from_sort_order", sa.Float(), nullable=True),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("source_sha256", sa.String(64), nullable=True),
        sa.Column("generated_by", sa.String(64), nullable=True),
        sa.Column("provenance_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "subject_type IN ('author','reader','character')",
            name="ck_knowledge_state_subject",
        ),
        sa.CheckConstraint(
            "target_kind IN ('fact','foreshadow','lore','event')",
            name="ck_knowledge_state_target",
        ),
        sa.CheckConstraint(
            "status IN ('unaware','aware','false_belief','forgotten')",
            name="ck_knowledge_state_status",
        ),
        sa.CheckConstraint(
            "visibility IN ('draft','approved','retired')",
            name="ck_knowledge_state_visibility",
        ),
        sa.CheckConstraint(
            "subject_type != 'character' OR character_id IS NOT NULL",
            name="ck_knowledge_state_character_required",
        ),
        sa.CheckConstraint(
            "subject_type = 'character' OR character_id IS NULL",
            name="ck_knowledge_state_character_forbidden",
        ),
    )
    op.create_index("ix_knowledge_states_project_id", "knowledge_states", ["project_id"])
    op.create_index("ix_knowledge_states_character_id", "knowledge_states", ["character_id"])

    op.create_table(
        "event_impacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", sa.Integer(),
                  sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("character_deltas_json", sa.JSON(), nullable=True),
        sa.Column("relationship_deltas_json", sa.JSON(), nullable=True),
        sa.Column("foreshadow_deltas_json", sa.JSON(), nullable=True),
        sa.Column("state_after", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("source_sha256", sa.String(64), nullable=True),
        sa.Column("generated_by", sa.String(64), nullable=True),
        sa.Column("provenance_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "visibility IN ('draft','approved','retired')",
            name="ck_event_impact_visibility",
        ),
    )
    op.create_index("ix_event_impacts_project_id", "event_impacts", ["project_id"])
    op.create_index("ix_event_impacts_chapter_id", "event_impacts", ["chapter_id"])


def downgrade() -> None:
    op.drop_index("ix_event_impacts_chapter_id", table_name="event_impacts")
    op.drop_index("ix_event_impacts_project_id", table_name="event_impacts")
    op.drop_table("event_impacts")
    op.drop_index("ix_knowledge_states_character_id", table_name="knowledge_states")
    op.drop_index("ix_knowledge_states_project_id", table_name="knowledge_states")
    op.drop_table("knowledge_states")
