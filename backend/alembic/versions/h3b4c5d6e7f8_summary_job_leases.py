"""summary job leases for multi-process workers.

Adds a compare-and-swap lease owner/token and expiry. Existing jobs remain
claimable because lease fields are nullable.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "h3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "g2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("summary_jobs") as batch:
        batch.add_column(sa.Column("lease_owner", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("lease_token", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("lease_expires_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("summary_jobs") as batch:
        batch.drop_column("lease_expires_at")
        batch.drop_column("lease_token")
        batch.drop_column("lease_owner")
