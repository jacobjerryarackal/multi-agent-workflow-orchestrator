"""Initial PostgreSQL schema for multi-agent workflow orchestration

Revision ID: v001_initial_schema
Revises: 
Create Date: 2026-08-23 11:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "v001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. workflows table
    op.create_table(
        "workflows",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=False),
        sa.Column("max_workflow_duration_seconds", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("max_parallel_tasks", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_workflow_name_version"),
    )
    op.create_index("ix_workflows_name", "workflows", ["name"])

    # 2. workflow_tasks table
    op.create_table(
        "workflow_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("workflow_id", sa.String(length=36), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_key", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("agent_id", sa.String(length=128), nullable=False),
        sa.Column("depends_on", sa.JSON(), nullable=False),
        sa.Column("input_mappings", sa.JSON(), nullable=False),
        sa.Column("static_inputs", sa.JSON(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("retry_policy", sa.JSON(), nullable=False),
        sa.Column("approval_gate", sa.JSON(), nullable=False),
        sa.Column("evaluation_gate", sa.JSON(), nullable=False),
        sa.UniqueConstraint("workflow_id", "task_key", name="uq_workflow_task_key"),
    )
    op.create_index("ix_workflow_tasks_workflow_id", "workflow_tasks", ["workflow_id"])

    # 3. workflow_executions table
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("workflow_id", sa.String(length=36), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="QUEUED"),
        sa.Column("trigger_type", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("initial_inputs", sa.JSON(), nullable=False),
        sa.Column("final_outputs", sa.JSON(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("execution_duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_workflow_executions_status", "workflow_executions", ["status"])
    op.create_index("ix_workflow_executions_workflow_id", "workflow_executions", ["workflow_id"])
    op.create_index("ix_workflow_executions_idempotency", "workflow_executions", ["workflow_id", "idempotency_key"])

    # 4. task_executions table
    op.create_table(
        "task_executions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("workflow_execution_id", sa.String(length=36), sa.ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_key", sa.String(length=128), nullable=False),
        sa.Column("agent_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("output_data", sa.JSON(), nullable=False),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("execution_duration_ms", sa.Integer(), nullable=True),
        sa.Column("token_usage", sa.JSON(), nullable=False),
        sa.UniqueConstraint("workflow_execution_id", "task_key", name="uq_execution_task_key"),
    )
    op.create_index("ix_task_executions_status", "task_executions", ["status"])
    op.create_index("ix_task_executions_exec_id", "task_executions", ["workflow_execution_id"])

    # 5. workflow_events table
    op.create_table(
        "workflow_events",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("workflow_execution_id", sa.String(length=36), sa.ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("task_execution_id", sa.String(length=36), nullable=True),
        sa.Column("task_key", sa.String(length=128), nullable=True),
        sa.Column("agent_id", sa.String(length=128), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False, server_default="system"),
    )
    op.create_index("ix_workflow_events_exec_id", "workflow_events", ["workflow_execution_id"])
    op.create_index("ix_workflow_events_timestamp", "workflow_events", ["timestamp"])
    op.create_index("ix_workflow_events_type", "workflow_events", ["event_type"])

    # 6. artifacts table
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("workflow_execution_id", sa.String(length=36), sa.ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_key", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("artifact_type", sa.String(length=32), nullable=False, server_default="json"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("artifact_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_artifacts_exec_id", "artifacts", ["workflow_execution_id"])
    op.create_index("ix_artifacts_task_key", "artifacts", ["task_key"])
    op.create_index("ix_artifacts_checksum", "artifacts", ["checksum_sha256"])


def downgrade() -> None:
    op.drop_table("artifacts")
    op.drop_table("workflow_events")
    op.drop_table("task_executions")
    op.drop_table("workflow_executions")
    op.drop_table("workflow_tasks")
    op.drop_table("workflows")
