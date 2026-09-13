"""project ending fields (D03-7) — 결말 후보·잠금·변경 시각

Revision ID: 8c9d0e1f2636
Revises: 7b8c9d0e1f25
Create Date: 2026-09-13

projects.ending_intent(TEXT NULL) + ending_locked(BOOL NOT NULL DEFAULT false)
+ ending_updated_at(DATETIME NULL). 기존 행은 NULL/false로 보존.
잠금 규칙(잠긴 결말의 실제 변경 거부)은 애플리케이션 계약 — DB CHECK 없음.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8c9d0e1f2636"
down_revision: Union[str, Sequence[str], None] = "7b8c9d0e1f25"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # projects 재작성(batch)은 FK와 충돌할 수 있으므로 전체 구간 동안 끈다.
    bind = op.get_bind()
    sqlite = bind.dialect.name == "sqlite"
    if sqlite:
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        with op.batch_alter_table("projects", schema=None) as batch_op:
            batch_op.add_column(sa.Column("ending_intent", sa.Text(), nullable=True))
            batch_op.add_column(
                sa.Column(
                    "ending_locked",
                    sa.Boolean(),
                    nullable=False,
                    server_default="0",
                )
            )
            batch_op.add_column(
                sa.Column("ending_updated_at", sa.DateTime(), nullable=True)
            )
    finally:
        if sqlite:
            bind.exec_driver_sql("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    bind = op.get_bind()
    sqlite = bind.dialect.name == "sqlite"
    if sqlite:
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        with op.batch_alter_table("projects", schema=None) as batch_op:
            batch_op.drop_column("ending_updated_at")
            batch_op.drop_column("ending_locked")
            batch_op.drop_column("ending_intent")
    finally:
        if sqlite:
            bind.exec_driver_sql("PRAGMA foreign_keys=ON")
