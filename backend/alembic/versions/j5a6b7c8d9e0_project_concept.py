"""add structured story concept to projects."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "i4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 컨셉은 선택 입력이다. 기존 프로젝트를 임의의 장르·톤·서사로 backfill하지 않는다.
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("concept", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    sqlite = bind.dialect.name == "sqlite"
    if sqlite:
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        with op.batch_alter_table("projects", schema=None) as batch_op:
            batch_op.drop_column("concept")
    finally:
        if sqlite:
            bind.exec_driver_sql("PRAGMA foreign_keys=ON")
