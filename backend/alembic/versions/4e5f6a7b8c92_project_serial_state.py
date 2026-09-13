"""project serial_state (D03-3) — 연재 상태를 회차 집필 확정과 분리

Revision ID: 4e5f6a7b8c92
Revises: 3d4e5f6a7b81
Create Date: 2026-09-13

projects.serial_state(ongoing|hiatus|completed) + serial_completed_at.
기존 행은 모두 ongoing으로 backfill(server_default).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4e5f6a7b8c92"
down_revision: Union[str, Sequence[str], None] = "3d4e5f6a7b81"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # projects 재작성(batch)은 자식 테이블(chapters 등) FK와 충돌하므로 전체 구간 동안
    # FK를 끈다 — 트랜잭션 안에서는 PRAGMA OFF가 무시되므로 문장 실행 전에 끈다.
    bind = op.get_bind()
    sqlite = bind.dialect.name == "sqlite"
    if sqlite:
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        with op.batch_alter_table("projects", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("serial_state", sa.String(20), nullable=False, server_default="ongoing")
            )
            batch_op.add_column(
                sa.Column("serial_completed_at", sa.DateTime(), nullable=True)
            )
            batch_op.create_check_constraint(
                "ck_project_serial_state",
                "serial_state IN ('ongoing','hiatus','completed')",
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
            batch_op.drop_constraint("ck_project_serial_state", type_="check")
            batch_op.drop_column("serial_completed_at")
            batch_op.drop_column("serial_state")
    finally:
        if sqlite:
            bind.exec_driver_sql("PRAGMA foreign_keys=ON")
