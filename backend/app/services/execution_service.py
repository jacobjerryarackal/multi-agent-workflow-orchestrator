"""Application service for Workflow and Task Executions, approval gates, events, and artifacts."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import structlog
from ..domain.models.execution import (
    WorkflowExecution,
    WorkflowExecutionStatus,
    TaskExecution,
    TaskExecutionStatus,
)
from ..domain.models.event import WorkflowEvent, EventType
from ..domain.models.artifact import Artifact
from ..domain.interfaces.repository import (
    WorkflowRepository,
    ExecutionRepository,
    EventRepository,
    ArtifactRepository,
)
from ..orchestration.execution_engine import WorkflowExecutionEngine
from ..orchestration.state_machine import WorkflowStateMachine, WorkflowCommand, TaskCommand
from ..core.exceptions import (
    WorkflowNotFoundError,
    StateTransitionError,
    ApprovalGateError,
    ArtifactIntegrityError,
)

logger = structlog.get_logger(__name__)


class ExecutionService:
    """Orchestrates execution submission, lifecycle driving, interventions, and audit querying."""

    def __init__(
        self,
        workflow_repo: WorkflowRepository,
        execution_repo: ExecutionRepository,
        event_repo: EventRepository,
        artifact_repo: ArtifactRepository,
        engine: WorkflowExecutionEngine,
    ):
        self.workflow_repo = workflow_repo
        self.execution_repo = execution_repo
        self.event_repo = event_repo
        self.artifact_repo = artifact_repo
        self.engine = engine

    async def submit_execution(
        self,
        workflow_id: str,
        input_data: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        trigger_type: str = "api",
        run_to_completion: bool = False,
    ) -> WorkflowExecution:
        """
        Submits a workflow for execution and schedules async background execution (or synchronously completes if requested).
        """
        execution = await self.engine.submit_workflow(
            workflow_id=workflow_id,
            initial_inputs=input_data,
            idempotency_key=idempotency_key,
            trigger_type=trigger_type,
        )

        if run_to_completion and execution.status in (
            WorkflowExecutionStatus.QUEUED,
            WorkflowExecutionStatus.RUNNING,
        ):
            execution = await self.engine.run_to_completion(execution.id)
        elif not run_to_completion and execution.status in (
            WorkflowExecutionStatus.QUEUED,
            WorkflowExecutionStatus.RUNNING,
        ):
            from ..orchestration.background_manager import get_background_manager
            get_background_manager().schedule_execution(
                execution_id=execution.id,
                registry=self.engine.agent_registry,
                evaluator=self.engine.evaluator,
            )

        return execution

    async def get_execution(self, execution_id: str) -> WorkflowExecution:
        """Retrieves a WorkflowExecution record with its task states."""
        execution = await self.execution_repo.get_workflow_execution(execution_id)
        if not execution:
            raise WorkflowNotFoundError(f"Workflow execution '{execution_id}' does not exist.")
        return execution

    async def list_executions(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WorkflowExecution]:
        """Lists workflow executions filtered by workflow ID or status."""
        return await self.execution_repo.list_workflow_executions(
            workflow_id=workflow_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def cancel_execution(self, execution_id: str) -> WorkflowExecution:
        """Cancels an active or queued workflow execution."""
        execution = await self.get_execution(execution_id)
        if execution.status in (
            WorkflowExecutionStatus.COMPLETED,
            WorkflowExecutionStatus.FAILED,
            WorkflowExecutionStatus.CANCELLED,
            WorkflowExecutionStatus.TIMED_OUT,
        ):
            raise StateTransitionError(
                f"Cannot cancel execution '{execution_id}' in terminal state '{execution.status.value}'."
            )

        WorkflowStateMachine.transition_workflow(execution, WorkflowCommand.CANCEL)
        execution.completed_at = datetime.utcnow()
        execution.error_summary = "Workflow execution cancelled by user request."
        updated_exec = await self.execution_repo.update_workflow_execution(execution)

        event = WorkflowEvent(
            workflow_execution_id=execution.id,
            workflow_id=execution.workflow_id,
            event_type=EventType.WORKFLOW_CANCELLED,
            payload={"reason": "User cancelled execution"},
            actor="user",
        )
        await self.event_repo.append_event(event)
        logger.info("Workflow execution cancelled", execution_id=execution_id)
        return updated_exec

    async def approve_task(
        self,
        execution_id: str,
        task_key: str,
        approver: str = "admin",
        comment: Optional[str] = None,
    ) -> TaskExecution:
        """Grants human signoff to advance a task waiting in WAITING_APPROVAL or ESCALATED state."""
        execution = await self.get_execution(execution_id)
        if task_key not in execution.tasks:
            raise WorkflowNotFoundError(f"Task '{task_key}' not found in execution '{execution_id}'.")

        task = execution.tasks[task_key]
        if task.status not in (TaskExecutionStatus.WAITING_APPROVAL, TaskExecutionStatus.ESCALATED):
            raise ApprovalGateError(
                f"Task '{task_key}' is in status '{task.status.value}', not WAITING_APPROVAL or ESCALATED."
            )

        WorkflowStateMachine.transition_task(task, TaskCommand.APPROVE)
        task.completed_at = datetime.utcnow()
        updated_task = await self.execution_repo.update_task_execution(task)

        event = WorkflowEvent(
            workflow_execution_id=execution.id,
            workflow_id=execution.workflow_id,
            task_key=task_key,
            event_type=EventType.APPROVAL_DECISION_RECORDED,
            payload={"decision": "APPROVED", "approver": approver, "comment": comment},
            actor=approver,
        )
        await self.event_repo.append_event(event)
        logger.info("Task approved", execution_id=execution_id, task_key=task_key, approver=approver)
        return updated_task

    async def reject_task(
        self,
        execution_id: str,
        task_key: str,
        rejector: str = "admin",
        reason: str = "",
    ) -> TaskExecution:
        """Rejects task output, routing it to ESCALATED or FAILED status."""
        execution = await self.get_execution(execution_id)
        if task_key not in execution.tasks:
            raise WorkflowNotFoundError(f"Task '{task_key}' not found in execution '{execution_id}'.")

        task = execution.tasks[task_key]
        if task.status != TaskExecutionStatus.WAITING_APPROVAL:
            raise ApprovalGateError(
                f"Task '{task_key}' is in status '{task.status.value}', not WAITING_APPROVAL."
            )

        WorkflowStateMachine.transition_task(task, TaskCommand.REJECT)
        task.error_details = {"rejected_by": rejector, "rejection_reason": reason}
        updated_task = await self.execution_repo.update_task_execution(task)

        event = WorkflowEvent(
            workflow_execution_id=execution.id,
            workflow_id=execution.workflow_id,
            task_key=task_key,
            event_type=EventType.APPROVAL_DECISION_RECORDED,
            payload={"decision": "REJECTED", "rejector": rejector, "reason": reason},
            actor=rejector,
        )
        await self.event_repo.append_event(event)
        logger.info("Task rejected", execution_id=execution_id, task_key=task_key, rejector=rejector)
        return updated_task

    async def list_events(self, execution_id: str) -> List[WorkflowEvent]:
        """Retrieves audit telemetry events for an execution."""
        # Verify execution exists
        await self.get_execution(execution_id)
        return await self.event_repo.list_events_for_execution(execution_id)

    async def get_artifact(self, artifact_id: str) -> Tuple[Artifact, bool]:
        """Retrieves an artifact and verifies its SHA-256 cryptographic integrity."""
        artifact = await self.artifact_repo.get_artifact(artifact_id)
        if not artifact:
            raise WorkflowNotFoundError(f"Artifact '{artifact_id}' does not exist.")

        is_valid = artifact.verify_integrity()
        if not is_valid:
            logger.error("Artifact integrity hash mismatch", artifact_id=artifact_id)
            raise ArtifactIntegrityError(f"Artifact '{artifact_id}' failed SHA-256 integrity verification.")

        return artifact, is_valid

    async def list_artifacts(self, execution_id: str) -> List[Artifact]:
        """Lists artifacts generated by a specific workflow execution."""
        await self.get_execution(execution_id)
        return await self.artifact_repo.list_artifacts_for_execution(execution_id)
