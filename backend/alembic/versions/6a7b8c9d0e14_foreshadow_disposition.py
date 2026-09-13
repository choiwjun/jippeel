"""foreshadow disposition (D03-5) — 복선 이관 구분

Revision ID: 6a7b8c9d0e14
Revises: 5f6a7b8c9d03
Create Date: 2026-09-13

foreshadows.disposition(resolved|intentional_unresolved|side_story, NULL=미분류)
+ ck_foreshadow_disposition. 기존 행은 disposition NULL로 보존.
status='설치' + disposition non-null 금지는 애플리케이션 계약(라우터 422)이며
DB CHECK는 값 사전만 강제한다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6a7b8c9d0e14"
down_revision: Union[str, Sequence[str], None] = "5f6a7b8c9d03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # foreshadows 재작성(batch)은 FK와 충돌할 수 있으므로 전체 구간 동안 끈다 —
    # 트랜잭션 안에서는 PRAGMA OFF가 무시되므로 문장 실행 전에 끈다.
    bind = op.get_bind()
    sqlite = bind.dialect.name == "sqlite"
    if sqlite:
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        with op.batch_alter_table("foreshadows", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("disposition", sa.String(30), nullable=True)
            )
            batch_op.create_check_constraint(
                "ck_foreshadow_disposition",
                "disposition IS NULL OR disposition IN "
                "('resolved','intentional_unresolved','side_story')",
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
        with op.batch_alter_table("foreshadows", schema=None) as batch_op:
            batch_op.drop_constraint("ck_foreshadow_disposition", type_="check")
            batch_op.drop_column("disposition")
    finally:
        if sqlite:
            bind.exec_driver_sql("PRAGMA foreign_keys=ON")
