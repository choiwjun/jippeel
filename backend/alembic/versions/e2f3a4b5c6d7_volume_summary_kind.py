"""volume memory kind — D02 계층 기억 2차 슬라이스

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-09-14

500화+ 계층 기억의 세 번째 층: 승인된 아크 요약(kind=arc_summary)을 묶는
권 기억. summary_jobs.kind를 ('summary','arc','volume')로 넓히고
memory_entries.kind에 'volume_memory'를 추가한다. SQLite는 CHECK를
ALTER할 수 없어 batch 모드로 재생성 — 데이터는 보존된다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JOB_EXPANDED = "kind IN ('summary','arc','volume')"
_JOB_PREVIOUS = "kind IN ('summary','arc')"
_MEM_EXPANDED = (
    "kind IN ('summary','beat','decision','fact','timeline',"
    "'relationship_note','arc_summary','volume_memory')"
)
_MEM_PREVIOUS = (
    "kind IN ('summary','beat','decision','fact','timeline',"
    "'relationship_note','arc_summary')"
)


def upgrade() -> None:
    with op.batch_alter_table("summary_jobs") as batch:
        batch.drop_constraint("ck_summary_job_kind", type_="check")
        batch.create_check_constraint("ck_summary_job_kind", _JOB_EXPANDED)
    with op.batch_alter_table("memory_entries") as batch:
        batch.drop_constraint("ck_memory_entry_kind", type_="check")
        batch.create_check_constraint("ck_memory_entry_kind", _MEM_EXPANDED)


def downgrade() -> None:
    with op.batch_alter_table("memory_entries") as batch:
        batch.drop_constraint("ck_memory_entry_kind", type_="check")
        batch.create_check_constraint("ck_memory_entry_kind", _MEM_PREVIOUS)
    with op.batch_alter_table("summary_jobs") as batch:
        batch.drop_constraint("ck_summary_job_kind", type_="check")
        batch.create_check_constraint("ck_summary_job_kind", _JOB_PREVIOUS)
