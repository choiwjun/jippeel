"""고도화 v2 — canon 이력·품질 이력·권 개요·독자 인지·문체 프로파일·AI 사용량

canon_runs(G-023 이력), quality_checks(G-031 추이), volume_notes(G-050 권 개요),
foreshadows.audience_knows(G-045 독자 인지), projects.style_profile(G-040),
ai_usage(G-060 사용량 통계)

Revision ID: f9a1b2c3d4e5
Revises: e8f0a1b2c3d4
Create Date: 2026-09-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f9a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'e8f0a1b2c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'canon_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chapter_id', sa.Integer(),
                  sa.ForeignKey('chapters.id'), nullable=False),
        sa.Column('model', sa.String(255), nullable=True),
        sa.Column('issues_json', sa.JSON(), nullable=True),
        sa.Column('context_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_canon_runs_chapter_id', 'canon_runs', ['chapter_id'])

    op.create_table(
        'quality_checks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chapter_id', sa.Integer(),
                  sa.ForeignKey('chapters.id'), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('metrics_json', sa.JSON(), nullable=True),
        sa.Column('suggestions_json', sa.JSON(), nullable=True),
        sa.Column('presets_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_quality_checks_chapter_id', 'quality_checks', ['chapter_id'])

    op.create_table(
        'volume_notes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(),
                  sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('volume', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('overview', sa.Text(), nullable=True),
        sa.Column('emotion_curve', sa.Text(), nullable=True),
        sa.Column('climax_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('volume >= 1', name='ck_volume_note_positive'),
    )
    op.create_index('ix_volume_notes_project_id', 'volume_notes', ['project_id'])

    with op.batch_alter_table('foreshadows', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'audience_knows', sa.Boolean(), nullable=False, server_default=sa.false()))

    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('style_profile', sa.Text(), nullable=True))

    op.create_table(
        'ai_usage',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('kind', sa.String(32), nullable=False),
        sa.Column('model', sa.String(255), nullable=True),
        sa.Column('endpoint_name', sa.String(255), nullable=True),
        sa.Column('prompt_chars', sa.Integer(), nullable=False),
        sa.Column('completion_chars', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_ai_usage_created_at', 'ai_usage', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_ai_usage_created_at', table_name='ai_usage')
    op.drop_table('ai_usage')
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('style_profile')
    with op.batch_alter_table('foreshadows', schema=None) as batch_op:
        batch_op.drop_column('audience_knows')
    op.drop_index('ix_volume_notes_project_id', table_name='volume_notes')
    op.drop_table('volume_notes')
    op.drop_index('ix_quality_checks_chapter_id', table_name='quality_checks')
    op.drop_table('quality_checks')
    op.drop_index('ix_canon_runs_chapter_id', table_name='canon_runs')
    op.drop_table('canon_runs')
