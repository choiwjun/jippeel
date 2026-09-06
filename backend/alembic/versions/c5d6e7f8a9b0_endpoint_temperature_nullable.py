"""F-040 ChatGPT 구독(OAuth) 대응 — ai_endpoints.temperature nullable 전환

Codex 계열 모델은 temperature 파라미터를 거부하므로 None(미전송)을 허용한다.
SQLite이므로 batch mode로 테이블 재생성.

Revision ID: c5d6e7f8a9b0
Revises: b3c4d5e6f7a8
Create Date: 2026-09-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('ai_endpoints', schema=None) as batch_op:
        batch_op.alter_column('temperature', existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    # 되돌릴 때는 미설정(NULL) 온도를 기본값 0.7로 귀속한 뒤 NOT NULL 재전환
    op.execute("UPDATE ai_endpoints SET temperature = 0.7 WHERE temperature IS NULL")
    with op.batch_alter_table('ai_endpoints', schema=None) as batch_op:
        batch_op.alter_column('temperature', existing_type=sa.Float(), nullable=False)
