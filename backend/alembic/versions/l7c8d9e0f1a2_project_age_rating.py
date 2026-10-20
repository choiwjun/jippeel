"""add age rating to projects."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "k6b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 기존 작품은 전체연령으로 남긴다 — 등급 상향은 작가의 명시적 선택이어야 한다.
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            "age_rating", sa.String(length=20), nullable=False, server_default="all"))


def downgrade() -> None:
    bind = op.get_bind()
    sqlite = bind.dialect.name == "sqlite"
    if sqlite:
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        with op.batch_alter_table("projects", schema=None) as batch_op:
            batch_op.drop_column("age_rating")
    finally:
        if sqlite:
            bind.exec_driver_sql("PRAGMA foreign_keys=ON")
