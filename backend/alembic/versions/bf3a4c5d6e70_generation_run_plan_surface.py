"""expand generation_runs surface — plan + assistant_generate

Revision ID: bf3a4c5d6e70
Revises: ae1f2b3c4d58
Create Date: 2026-09-14

계획→승인→집필 흐름(P1)은 /ai/plan surface를, 원클릭 집필(assistant)은
assistant_generate surface를 이력에 기록한다. SQLite는 CHECK 제약을 ALTER할
수 없으므로 batch 모드로 테이블을 재생성한다. 데이터는 보존된다.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "bf3a4c5d6e70"
down_revision: Union[str, Sequence[str], None] = "ae1f2b3c4d58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EXPANDED = "surface IN ('generate','generate_parallel','review','plan','assistant_generate')"
_ORIGINAL = "surface IN ('generate','generate_parallel','review')"


def upgrade() -> None:
    with op.batch_alter_table("generation_runs") as batch:
        batch.drop_constraint("ck_generation_run_surface", type_="check")
        batch.create_check_constraint("ck_generation_run_surface", _EXPANDED)


def downgrade() -> None:
    with op.batch_alter_table("generation_runs") as batch:
        batch.drop_constraint("ck_generation_run_surface", type_="check")
        batch.create_check_constraint("ck_generation_run_surface", _ORIGINAL)
