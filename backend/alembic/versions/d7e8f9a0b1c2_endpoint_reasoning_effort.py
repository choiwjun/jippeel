"""F-040 ChatGPT 구독(OAuth) 대응 — ai_endpoints.reasoning_effort 컬럼 추가

Codex 계열 reasoning 모델(gpt-5.6 등)의 추론 강도를 엔드포인트별로 지정한다.
NULL = 파라미터 미전송.

Revision ID: d7e8f9a0b1c2
Revises: c5d6e7f8a9b0
Create Date: 2026-09-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, Sequence[str], None] = 'c5d6e7f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('ai_endpoints', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reasoning_effort', sa.String(32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('ai_endpoints', schema=None) as batch_op:
        batch_op.drop_column('reasoning_effort')
