"""API endpoints for Workflow definitions and specifications."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status

from ..dependencies import get_workflow_service
from ...services.workflow_service import WorkflowService
from ..schemas.workflow import (
    WorkflowCreateRequest,
    WorkflowResponse,
    WorkflowListResponse,
    TaskSpecSchema,
    RetryPolicySchema,
    ApprovalGateSchema,
    EvaluationGateSchema,
)

workflows_router = APIRouter(prefix="/workflows", tags=["Workflows"])


def _map_workflow_to_response(spec) -> WorkflowResponse:
    """Helper mapping domain WorkflowSpec to WorkflowResponse DTO."""
    tasks = []
    for t in spec.tasks:
        tasks.append(
            TaskSpecSchema(
                task_key=t.task_key,
                name=t.name,
                agent_id=t.agent_id,
                depends_on=t.depends_on,
                input_mappings=t.input_mappings,
                static_inputs=t.static_inputs,
                timeout_seconds=t.timeout_seconds,
                retry_policy=RetryPolicySchema(
                    max_attempts=t.retry_policy.max_attempts,
                    initial_interval_seconds=t.retry_policy.initial_interval_seconds,
                    backoff_multiplier=t.retry_policy.backoff_multiplier,
                    jitter=t.retry_policy.jitter,
                    retryable_categories=t.retry_policy.retryable_categories,
                ),
                approval_gate=ApprovalGateSchema(
                    required=t.approval_gate.required,
                    approver_roles=t.approval_gate.approver_roles,
                    timeout_seconds=t.approval_gate.timeout_seconds,
                    auto_action_on_timeout=t.approval_gate.auto_action_on_timeout,
                ),
                evaluation_gate=EvaluationGateSchema(
                    enabled=t.evaluation_gate.enabled,
                    evaluator_name=t.evaluation_gate.evaluator_name,
                    min_pass_score=t.evaluation_gate.min_pass_score,
                    max_revisions=t.evaluation_gate.max_revisions,
                    deterministic_rules=t.evaluation_gate.deterministic_rules,
                    criteria=t.evaluation_gate.criteria,
                    rejection_policy=t.evaluation_gate.rejection_policy,
                ),
            )
        )

    return WorkflowResponse(
        id=spec.id,
        name=spec.name,
        version=spec.version,
        description=spec.description,
        input_schema=spec.input_schema,
        output_schema=spec.output_schema,
        tasks=tasks,
        max_workflow_duration_seconds=spec.max_workflow_duration_seconds,
        max_parallel_tasks=spec.max_parallel_tasks,
        created_at=spec.created_at,
    )


@workflows_router.post(
    "",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new workflow specification",
)
async def create_workflow(
    request: WorkflowCreateRequest,
    service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowResponse:
    """Validates DAG structure and registers a new WorkflowSpec."""
    spec = await service.create_workflow(request)
    return _map_workflow_to_response(spec)


@workflows_router.get(
    "",
    response_model=WorkflowListResponse,
    summary="List all registered workflow specifications",
)
async def list_workflows(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowListResponse:
    """Lists registered workflow definitions with pagination."""
    specs = await service.list_workflows(limit=limit, offset=offset)
    items = [_map_workflow_to_response(s) for s in specs]
    return WorkflowListResponse(items=items, total_count=len(items))


@workflows_router.get(
    "/{workflow_id}",
    response_model=WorkflowResponse,
    summary="Retrieve workflow specification by ID",
)
async def get_workflow(
    workflow_id: str,
    service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowResponse:
    """Retrieves full workflow specification details including task DAG configuration."""
    spec = await service.get_workflow(workflow_id)
    return _map_workflow_to_response(spec)
