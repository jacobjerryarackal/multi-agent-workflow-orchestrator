"""Add evaluation revision_count and evaluation_history to task_executions

Revision ID: v002_evaluation_support
Revises: v001_initial_schema
Create Date: 2026-08-23 12:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "v002_evaluation_support"
down_revision: Union[str, None] = "v001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "task_executions",
        sa.Column("revision_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "task_executions",
        sa.Column("evaluation_history", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("task_executions", "evaluation_history")
    op.drop_column("task_executions", "revision_count")
