"""API endpoints for Workflow Executions, task DAG progression, and human-in-the-loop gates."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status

from ..dependencies import get_execution_service
from ...services.execution_service import ExecutionService
from ..schemas.execution import (
    SubmitExecutionRequest,
    TaskApproveRequest,
    TaskRejectRequest,
    TaskExecutionSummaryResponse,
    WorkflowExecutionSummaryResponse,
    WorkflowExecutionDetailResponse,
    ExecutionListResponse,
)

executions_router = APIRouter(tags=["Executions"])


def _map_task_to_response(task) -> TaskExecutionSummaryResponse:
    """Helper mapping domain TaskExecution to summary response DTO."""
    return TaskExecutionSummaryResponse(
        id=task.id,
        workflow_execution_id=task.workflow_execution_id,
        task_key=task.task_key,
        agent_id=task.agent_id,
        status=task.status.value if hasattr(task.status, "value") else str(task.status),
        attempt_count=task.attempt_count,
        revision_count=task.revision_count,
        input_data=task.input_data,
        output_data=task.output_data,
        evaluation_history=task.evaluation_history,
        error_details=task.error_details,
        started_at=task.started_at,
        completed_at=task.completed_at,
        execution_duration_ms=task.execution_duration_ms,
        token_usage=task.token_usage,
    )


def _map_execution_to_summary(execution) -> WorkflowExecutionSummaryResponse:
    """Helper mapping domain WorkflowExecution to summary DTO."""
    return WorkflowExecutionSummaryResponse(
        id=execution.id,
        workflow_id=execution.workflow_id,
        status=execution.status.value if hasattr(execution.status, "value") else str(execution.status),
        trigger_type=execution.trigger_type,
        idempotency_key=execution.idempotency_key,
        created_at=execution.created_at,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        execution_duration_ms=execution.execution_duration_ms,
        error_summary=execution.error_summary,
    )


def _map_execution_to_detail(execution) -> WorkflowExecutionDetailResponse:
    """Helper mapping domain WorkflowExecution and its task states to detail response DTO."""
    task_responses = [_map_task_to_response(t) for t in execution.tasks.values()]
    return WorkflowExecutionDetailResponse(
        id=execution.id,
        workflow_id=execution.workflow_id,
        status=execution.status.value if hasattr(execution.status, "value") else str(execution.status),
        trigger_type=execution.trigger_type,
        idempotency_key=execution.idempotency_key,
        initial_inputs=execution.initial_inputs,
        final_outputs=execution.final_outputs,
        error_summary=execution.error_summary,
        created_at=execution.created_at,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        execution_duration_ms=execution.execution_duration_ms,
        tasks=task_responses,
    )


@executions_router.post(
    "/workflows/{workflow_id}/executions",
    response_model=WorkflowExecutionDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit and execute a workflow instance",
)
async def submit_execution(
    workflow_id: str,
    request: SubmitExecutionRequest,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowExecutionDetailResponse:
    """Submits a workflow DAG for execution, performs idempotency checks, and executes tasks."""
    execution = await service.submit_execution(
        workflow_id=workflow_id,
        input_data=request.input_data,
        idempotency_key=request.idempotency_key,
        trigger_type=request.trigger_type,
        run_to_completion=True,
    )
    return _map_execution_to_detail(execution)


@executions_router.get(
    "/executions",
    response_model=ExecutionListResponse,
    summary="List workflow execution instances",
)
async def list_executions(
    workflow_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionListResponse:
    """Lists workflow execution instances with filtering and pagination."""
    executions = await service.list_executions(
        workflow_id=workflow_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    items = [_map_execution_to_summary(e) for e in executions]
    return ExecutionListResponse(items=items, total_count=len(items))


@executions_router.get(
    "/executions/{execution_id}",
    response_model=WorkflowExecutionDetailResponse,
    summary="Retrieve execution details and task DAG status",
)
async def get_execution_detail(
    execution_id: str,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowExecutionDetailResponse:
    """Retrieves full runtime state, task execution progression, and final outputs."""
    execution = await service.get_execution(execution_id)
    return _map_execution_to_detail(execution)


@executions_router.post(
    "/executions/{execution_id}/cancel",
    response_model=WorkflowExecutionDetailResponse,
    summary="Cancel an active workflow execution",
)
async def cancel_execution(
    execution_id: str,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowExecutionDetailResponse:
    """Transitions an active or queued workflow to CANCELLED state."""
    execution = await service.cancel_execution(execution_id)
    return _map_execution_to_detail(execution)


@executions_router.post(
    "/executions/{execution_id}/tasks/{task_key}/approve",
    response_model=TaskExecutionSummaryResponse,
    summary="Grant human approval for a paused task",
)
async def approve_task(
    execution_id: str,
    task_key: str,
    request: TaskApproveRequest,
    service: ExecutionService = Depends(get_execution_service),
) -> TaskExecutionSummaryResponse:
    """Approves a task in WAITING_APPROVAL or ESCALATED state, allowing DAG to resume."""
    task = await service.approve_task(
        execution_id=execution_id,
        task_key=task_key,
        approver=request.approver,
        comment=request.comment,
    )
    return _map_task_to_response(task)


@executions_router.post(
    "/executions/{execution_id}/tasks/{task_key}/reject",
    response_model=TaskExecutionSummaryResponse,
    summary="Reject task output and escalate",
)
async def reject_task(
    execution_id: str,
    task_key: str,
    request: TaskRejectRequest,
    service: ExecutionService = Depends(get_execution_service),
) -> TaskExecutionSummaryResponse:
    """Rejects task output in WAITING_APPROVAL state, escalating to human operator review."""
    task = await service.reject_task(
        execution_id=execution_id,
        task_key=task_key,
        rejector=request.rejector,
        reason=request.reason,
    )
    return _map_task_to_response(task)
