"""T-002 chapter.volume nullable 전환 (기술설계 §4.2 변경 1 — Q1 결정안)

권 없는 평면 회차 지원: chapters.volume NOT NULL → NULL 허용.
SQLite이므로 batch mode로 테이블 재생성.

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-08-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('chapters', schema=None) as batch_op:
        batch_op.alter_column('volume', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # 되돌릴 때는 권 없는(NULL) 평면 회차를 1권으로 귀속한 뒤 NOT NULL 재전환
    op.execute("UPDATE chapters SET volume = 1 WHERE volume IS NULL")
    with op.batch_alter_table('chapters', schema=None) as batch_op:
        batch_op.alter_column('volume', existing_type=sa.Integer(), nullable=False)
