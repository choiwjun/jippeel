"""chapter flow stage (D03-1) — flow_stage column + append-only transition events

Revision ID: 3d4e5f6a7b81
Revises: 2c3d4e5f6a70
Create Date: 2026-09-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "3d4e5f6a7b81"
down_revision: Union[str, Sequence[str], None] = "2c3d4e5f6a70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # chapters 재작성(batch)은 자식 테이블 FK와 충돌하므로 전체 upgrade 구간 동안
    # FK를 끈다 — 트랜잭션 안에서는 PRAGMA OFF가 무시되므로 문장 실행 전에 끈다.
    bind = op.get_bind()
    sqlite = bind.dialect.name == "sqlite"
    if sqlite:
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        with op.batch_alter_table("chapters", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("flow_stage", sa.String(20), nullable=False, server_default="planning")
            )
        # 기존 행 근사 매핑 — status는 그대로 유지한다.
        op.execute(
            sa.text(
                """
                UPDATE chapters SET flow_stage = CASE
                    WHEN status = '완료' THEN 'confirmed'
                    WHEN status = '수정중' THEN 'revising'
                    WHEN status = '초고' AND TRIM(content_md) = '' THEN 'planning'
                    ELSE 'writing'
                END
                """
            )
        )
        with op.batch_alter_table("chapters", schema=None) as batch_op:
            batch_op.create_check_constraint(
                "ck_chapter_flow_stage",
                "flow_stage IN ('planning','writing','revising','confirmed')",
            )
    finally:
        if sqlite:
            bind.exec_driver_sql("PRAGMA foreign_keys=ON")

    op.create_table(
        "chapter_flow_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_stage", sa.String(20), nullable=False),
        sa.Column("to_stage", sa.String(20), nullable=False),
        sa.Column("goal_version", sa.Integer(), nullable=True),
        sa.Column("manuscript_revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "from_stage IN ('planning','writing','revising','confirmed')",
            name="ck_flow_event_from_stage",
        ),
        sa.CheckConstraint(
            "to_stage IN ('planning','writing','revising','confirmed')",
            name="ck_flow_event_to_stage",
        ),
    )
    op.create_index("ix_chapter_flow_events_chapter_id", "chapter_flow_events", ["chapter_id"])
    op.create_index("ix_chapter_flow_events_created_at", "chapter_flow_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_chapter_flow_events_created_at", table_name="chapter_flow_events")
    op.drop_index("ix_chapter_flow_events_chapter_id", table_name="chapter_flow_events")
    op.drop_table("chapter_flow_events")

    bind = op.get_bind()
    sqlite = bind.dialect.name == "sqlite"
    if sqlite:
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        with op.batch_alter_table("chapters", schema=None) as batch_op:
            batch_op.drop_constraint("ck_chapter_flow_stage", type_="check")
            batch_op.drop_column("flow_stage")
    finally:
        if sqlite:
            bind.exec_driver_sql("PRAGMA foreign_keys=ON")
