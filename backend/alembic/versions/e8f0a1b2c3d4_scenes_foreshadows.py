"""고도화 v1 — scenes(장면)·foreshadows(복선) 테이블 추가

G-010: 회차 → 장면 계층(장면 단위 AI 생성/재작성용)
G-020: 복선 설치/회수 상태 관리(미회수 복선 자동 주입용)

Revision ID: e8f0a1b2c3d4
Revises: d7e8f9a0b1c2
Create Date: 2026-09-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e8f0a1b2c3d4'
down_revision: Union[str, Sequence[str], None] = 'd7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scenes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chapter_id', sa.Integer(),
                  sa.ForeignKey('chapters.id'), nullable=False),
        sa.Column('sort_order', sa.Float(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('content_md', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_scenes_chapter_id', 'scenes', ['chapter_id'])

    op.create_table(
        'foreshadows',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(),
                  sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('planted_chapter_id', sa.Integer(),
                  sa.ForeignKey('chapters.id'), nullable=True),
        sa.Column('resolved_chapter_id', sa.Integer(),
                  sa.ForeignKey('chapters.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('설치','회수','보류')", name='ck_foreshadow_status'),
    )
    op.create_index('ix_foreshadows_project_id', 'foreshadows', ['project_id'])


def downgrade() -> None:
    op.drop_index('ix_foreshadows_project_id', table_name='foreshadows')
    op.drop_table('foreshadows')
    op.drop_index('ix_scenes_chapter_id', table_name='scenes')
    op.drop_table('scenes')
