"""Add task lease metadata and index for durable crash recovery

Revision ID: v003_task_leases
Revises: v002_evaluation_support
Create Date: 2026-08-27 12:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "v003_task_leases"
down_revision: Union[str, None] = "v002_evaluation_support"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "task_executions",
        sa.Column("lease_until", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "task_executions",
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "task_executions",
        sa.Column("leased_by", sa.String(128), nullable=True),
    )
    op.create_index(
        "ix_task_executions_lease",
        "task_executions",
        ["status", "lease_until"],
    )


def downgrade() -> None:
    op.drop_index("ix_task_executions_lease", table_name="task_executions")
    op.drop_column("task_executions", "leased_by")
    op.drop_column("task_executions", "heartbeat_at")
    op.drop_column("task_executions", "lease_until")
