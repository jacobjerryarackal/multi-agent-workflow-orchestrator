"""Add PostgreSQL partial unique index on workflow executions for idempotency

Revision ID: v004_idempotency_constraint
Revises: v003_task_leases
Create Date: 2026-08-27 12:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "v004_idempotency_constraint"
down_revision: Union[str, None] = "v003_task_leases"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop existing non-unique index if present
    op.drop_index("ix_workflow_executions_idempotency", table_name="workflow_executions", if_exists=True)

    # 2. Create partial unique index on (workflow_id, idempotency_key) where idempotency_key IS NOT NULL
    op.create_index(
        "uq_workflow_executions_idempotency",
        "workflow_executions",
        ["workflow_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
        if_not_exists=True,
    )


def downgrade() -> None:
    # 1. Drop partial unique index
    op.drop_index("uq_workflow_executions_idempotency", table_name="workflow_executions", if_exists=True)

    # 2. Recreate original non-unique index
    op.create_index(
        "ix_workflow_executions_idempotency",
        "workflow_executions",
        ["workflow_id", "idempotency_key"],
        unique=False,
        if_not_exists=True,
    )
