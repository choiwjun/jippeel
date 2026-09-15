"""캐릭터 라이프사이클 first-class 필드 — 감사 잔여 우선순위 1

- characters.lifecycle_status: active|departed|deceased|retired
- characters.lifecycle_chapter_id: 퇴장·사망 발생 회차
- characters.lifecycle_note: 사유 메모
- characters.volume_roles: 권별 역할 JSON [{volume, role}]

Revision ID: g2a3b4c5d6e7
Revises: f1a2b3c4d5e6
Create Date: 2026-09-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    sqlite = bind.dialect.name == "sqlite"
    if sqlite:
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        with op.batch_alter_table("characters") as batch_op:
            batch_op.add_column(
                sa.Column("lifecycle_status", sa.String(20), nullable=False, server_default="active"),
            )
            batch_op.add_column(
                sa.Column("lifecycle_chapter_id", sa.Integer, nullable=True),
            )
            batch_op.create_foreign_key(
                "fk_characters_lifecycle_chapter_id_chapters",
                "chapters",
                ["lifecycle_chapter_id"],
                ["id"],
            )
            batch_op.add_column(
                sa.Column("lifecycle_note", sa.Text, nullable=True),
            )
            batch_op.add_column(
                sa.Column("volume_roles", sa.JSON, nullable=True),
            )
            batch_op.create_check_constraint(
                "ck_character_lifecycle_status",
                "lifecycle_status IN ('active','departed','deceased','retired')",
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
        with op.batch_alter_table("characters") as batch_op:
            batch_op.drop_constraint("ck_character_lifecycle_status", type_="check")
            batch_op.drop_constraint(
                "fk_characters_lifecycle_chapter_id_chapters", type_="foreignkey"
            )
            batch_op.drop_column("volume_roles")
            batch_op.drop_column("lifecycle_note")
            batch_op.drop_column("lifecycle_chapter_id")
            batch_op.drop_column("lifecycle_status")
    finally:
        if sqlite:
            bind.exec_driver_sql("PRAGMA foreign_keys=ON")
