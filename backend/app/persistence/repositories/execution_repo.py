"""SQLAlchemy repository implementation for Workflow and Task Executions."""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...domain.models.execution import (
    WorkflowExecution,
    WorkflowExecutionStatus,
    TaskExecution,
    TaskExecutionStatus,
)
from ...domain.interfaces.repository import ExecutionRepository
from ..models import WorkflowExecutionModel, TaskExecutionModel


class SqlExecutionRepository(ExecutionRepository):
    """PostgreSQL/SQLAlchemy implementation of ExecutionRepository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_workflow_execution(self, execution: WorkflowExecution) -> WorkflowExecution:
        model = WorkflowExecutionModel.from_domain(execution)
        self.session.add(model)
        await self.session.flush()
        return model.to_domain()

    async def get_workflow_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        stmt = (
            select(WorkflowExecutionModel)
            .where(WorkflowExecutionModel.id == execution_id)
            .execution_options(populate_existing=True)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_workflow_execution_by_idempotency_key(
        self, workflow_id: str, idempotency_key: str
    ) -> Optional[WorkflowExecution]:
        stmt = select(WorkflowExecutionModel).where(
            WorkflowExecutionModel.workflow_id == workflow_id,
            WorkflowExecutionModel.idempotency_key == idempotency_key,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def update_workflow_execution(self, execution: WorkflowExecution) -> WorkflowExecution:
        stmt = select(WorkflowExecutionModel).where(WorkflowExecutionModel.id == execution.id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"WorkflowExecution '{execution.id}' not found.")

        model.status = execution.status.value
        model.initial_inputs = execution.initial_inputs
        model.final_outputs = execution.final_outputs
        model.error_summary = execution.error_summary
        model.started_at = execution.started_at
        model.completed_at = execution.completed_at
        model.execution_duration_ms = execution.execution_duration_ms

        await self.session.flush()
        return model.to_domain()

    async def update_task_execution(self, task_exec: TaskExecution) -> TaskExecution:
        stmt = select(TaskExecutionModel).where(TaskExecutionModel.id == task_exec.id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            # Create if not exists
            model = TaskExecutionModel.from_domain(task_exec)
            self.session.add(model)
        else:
            model.status = task_exec.status.value
            model.attempt_count = task_exec.attempt_count
            model.revision_count = task_exec.revision_count
            model.input_data = task_exec.input_data
            model.output_data = task_exec.output_data
            model.evaluation_history = task_exec.evaluation_history
            model.error_details = task_exec.error_details
            model.started_at = task_exec.started_at
            model.completed_at = task_exec.completed_at
            model.execution_duration_ms = task_exec.execution_duration_ms
            model.token_usage = task_exec.token_usage

        await self.session.flush()
        return model.to_domain()

    async def claim_task_for_execution(
        self, workflow_execution_id: str, task_key: str
    ) -> Optional[TaskExecution]:
        """
        Atomically claims a READY task for execution using database row-level locking (SELECT FOR UPDATE).
        Guarantees that exactly one worker can acquire and transition the task to RUNNING.
        """
        stmt = (
            select(TaskExecutionModel)
            .where(
                TaskExecutionModel.workflow_execution_id == workflow_execution_id,
                TaskExecutionModel.task_key == task_key,
                TaskExecutionModel.status == TaskExecutionStatus.READY.value,
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None

        from datetime import datetime
        model.status = TaskExecutionStatus.RUNNING.value
        model.attempt_count += 1
        model.started_at = datetime.utcnow()

        await self.session.flush()
        return model.to_domain()

