"""arc summary kind — D02 계층 기억 1차 슬라이스

Revision ID: d1e2f3a4b5c6
Revises: c04b5d6e7f81
Create Date: 2026-09-14

500화+ 계층 기억의 두 번째 층: 회차 요약(kind=summary)을 10~20화 단위로
묶는 아크 요약. summary_jobs.kind를 ('summary','arc')로 넓히고
source_ids_json(아크 원천 MemoryEntry id 목록)을 추가한다.
memory_entries.kind에 'arc_summary'를 추가한다. SQLite는 CHECK를 ALTER할
수 없어 batch 모드로 재생성 — 데이터는 보존된다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c04b5d6e7f81"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JOB_EXPANDED = "kind IN ('summary','arc')"
_JOB_ORIGINAL = "kind = 'summary'"
_MEM_EXPANDED = (
    "kind IN ('summary','beat','decision','fact','timeline',"
    "'relationship_note','arc_summary')"
)
_MEM_ORIGINAL = (
    "kind IN ('summary','beat','decision','fact','timeline','relationship_note')"
)


def upgrade() -> None:
    with op.batch_alter_table("summary_jobs") as batch:
        batch.add_column(
            sa.Column("source_ids_json", sa.JSON(), nullable=False,
                      server_default="[]")
        )
        batch.drop_constraint("ck_summary_job_kind", type_="check")
        batch.create_check_constraint("ck_summary_job_kind", _JOB_EXPANDED)
    with op.batch_alter_table("memory_entries") as batch:
        batch.drop_constraint("ck_memory_entry_kind", type_="check")
        batch.create_check_constraint("ck_memory_entry_kind", _MEM_EXPANDED)


def downgrade() -> None:
    with op.batch_alter_table("memory_entries") as batch:
        batch.drop_constraint("ck_memory_entry_kind", type_="check")
        batch.create_check_constraint("ck_memory_entry_kind", _MEM_ORIGINAL)
    with op.batch_alter_table("summary_jobs") as batch:
        batch.drop_constraint("ck_summary_job_kind", type_="check")
        batch.create_check_constraint("ck_summary_job_kind", _JOB_ORIGINAL)
        batch.drop_column("source_ids_json")
