from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
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
        if execution.idempotency_key:
            try:
                async with self.session.begin_nested():
                    self.session.add(model)
                    await self.session.flush()
                return model.to_domain()
            except IntegrityError:
                # Concurrent race condition: another transaction committed first with this idempotency_key
                existing = await self.get_workflow_execution_by_idempotency_key(
                    execution.workflow_id, execution.idempotency_key
                )
                if existing:
                    return existing
                raise
        else:
            self.session.add(model)
            await self.session.flush()
            return model.to_domain()

    async def get_workflow_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        stmt = (
            select(WorkflowExecutionModel)
            .options(selectinload(WorkflowExecutionModel.task_executions))
            .where(WorkflowExecutionModel.id == execution_id)
            .execution_options(populate_existing=True)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_workflow_execution_by_idempotency_key(
        self, workflow_id: str, idempotency_key: str
    ) -> Optional[WorkflowExecution]:
        stmt = (
            select(WorkflowExecutionModel)
            .options(selectinload(WorkflowExecutionModel.task_executions))
            .where(
                WorkflowExecutionModel.workflow_id == workflow_id,
                WorkflowExecutionModel.idempotency_key == idempotency_key,
            )
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def list_workflow_executions(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WorkflowExecution]:
        stmt = select(WorkflowExecutionModel).options(
            selectinload(WorkflowExecutionModel.task_executions)
        )
        if workflow_id:
            stmt = stmt.where(WorkflowExecutionModel.workflow_id == workflow_id)
        if status:
            stmt = stmt.where(WorkflowExecutionModel.status == status)
        stmt = stmt.order_by(WorkflowExecutionModel.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [m.to_domain() for m in models]


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
        self,
        workflow_execution_id: str,
        task_key: str,
        lease_duration_seconds: int = 90,
        worker_id: Optional[str] = None,
    ) -> Optional[TaskExecution]:
        """
        Atomically claims a READY task for execution using database row-level locking (SELECT FOR UPDATE).
        Sets status=RUNNING, increments attempt_count, records started_at, heartbeat_at, and calculates lease_until.
        Guarantees that exactly one worker can acquire and transition the task.
        """
        from datetime import datetime, timedelta
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

        now = datetime.utcnow()
        model.status = TaskExecutionStatus.RUNNING.value
        model.attempt_count += 1
        model.started_at = now
        model.heartbeat_at = now
        model.lease_until = now + timedelta(seconds=lease_duration_seconds)
        model.leased_by = worker_id or "async_worker"

        await self.session.flush()
        return model.to_domain()

    async def renew_task_lease(
        self,
        task_id: str,
        lease_duration_seconds: int = 90,
    ) -> bool:
        """Extends the lease for a currently running task."""
        from datetime import datetime, timedelta
        stmt = (
            select(TaskExecutionModel)
            .where(
                TaskExecutionModel.id == task_id,
                TaskExecutionModel.status == TaskExecutionStatus.RUNNING.value,
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return False

        now = datetime.utcnow()
        model.heartbeat_at = now
        model.lease_until = now + timedelta(seconds=lease_duration_seconds)
        await self.session.flush()
        return True

    async def find_and_lock_stale_tasks(
        self,
        now: Optional[datetime] = None,
        limit: int = 50,
    ) -> list[TaskExecutionModel]:
        """
        Finds and locks RUNNING tasks whose lease has expired using SELECT FOR UPDATE SKIP LOCKED.
        Safe for concurrent invocation across multiple worker processes.
        """
        from datetime import datetime
        cutoff = now or datetime.utcnow()
        stmt = (
            select(TaskExecutionModel)
            .where(
                TaskExecutionModel.status == TaskExecutionStatus.RUNNING.value,
                TaskExecutionModel.lease_until.is_not(None),
                TaskExecutionModel.lease_until < cutoff,
            )
            .order_by(TaskExecutionModel.lease_until.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_workflow_execution_ids(self) -> list[str]:
        """Returns IDs of workflows currently in QUEUED or RUNNING states."""
        stmt = select(WorkflowExecutionModel.id).where(
            WorkflowExecutionModel.status.in_([
                WorkflowExecutionStatus.QUEUED.value,
                WorkflowExecutionStatus.RUNNING.value,
            ])
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


