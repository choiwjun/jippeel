"""improvement_rules (E4) — 작품별 개선 규칙 + 승인 생명주기

Revision ID: c04b5d6e7f81
Revises: bf3a4c5d6e70
Create Date: 2026-09-14

제안(proposed)은 시스템 분석·작가 작성 모두 가능하지만 다음 생성에 적용되는
것은 작가 승인(approved) 규칙뿐이다. rejected·retired는 종결, 규칙 본문은
승인 후 불변 — 수정은 retire + 새 proposed로 처리한다. status_events_json은
append-only 전이 이력. project 삭제 시 CASCADE — 작품별 완전 분리.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c04b5d6e7f81"
down_revision: Union[str, Sequence[str], None] = "bf3a4c5d6e70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "improvement_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("rule_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="proposed"),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="author_written"),
        sa.Column("evidence_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("status_events_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "category IN ('style','deleted_expression','character_voice',"
            "'pacing','length','recurring_error','canon_gap','long_arc')",
            name="ck_improvement_rule_category",
        ),
        sa.CheckConstraint(
            "status IN ('proposed','approved','rejected','retired')",
            name="ck_improvement_rule_status",
        ),
        sa.CheckConstraint(
            "source IN ('author_written','system_proposal')",
            name="ck_improvement_rule_source",
        ),
    )
    op.create_index("ix_improvement_rules_project_id", "improvement_rules", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_improvement_rules_project_id", table_name="improvement_rules")
    op.drop_table("improvement_rules")
