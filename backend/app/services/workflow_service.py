"""Application service for Workflow definitions and specifications."""

from typing import List, Optional
import structlog
from ..domain.models.workflow import (
    WorkflowSpec,
    TaskSpec,
    RetryPolicySpec,
    ApprovalGateSpec,
    EvaluationGateSpec,
)
from ..domain.interfaces.repository import WorkflowRepository
from ..orchestration.dependency_resolver import DependencyResolver
from ..core.exceptions import WorkflowNotFoundError, WorkflowValidationError
from ..api.schemas.workflow import WorkflowCreateRequest

logger = structlog.get_logger(__name__)


class WorkflowService:
    """Orchestrates workflow authoring, graph validation, and specification retrieval."""

    def __init__(self, workflow_repo: WorkflowRepository):
        self.workflow_repo = workflow_repo

    async def create_workflow(self, request: WorkflowCreateRequest) -> WorkflowSpec:
        """
        Validates the DAG structure and persists a new Workflow specification.
        """
        tasks: List[TaskSpec] = []
        for t in request.tasks:
            retry_pol = RetryPolicySpec(
                max_attempts=t.retry_policy.max_attempts,
                initial_interval_seconds=t.retry_policy.initial_interval_seconds,
                backoff_multiplier=t.retry_policy.backoff_multiplier,
                jitter=t.retry_policy.jitter,
                retryable_categories=t.retry_policy.retryable_categories,
            )
            approval_gt = ApprovalGateSpec(
                required=t.approval_gate.required,
                approver_roles=t.approval_gate.approver_roles,
                timeout_seconds=t.approval_gate.timeout_seconds,
                auto_action_on_timeout=t.approval_gate.auto_action_on_timeout,
            )
            eval_gt = EvaluationGateSpec(
                enabled=t.evaluation_gate.enabled,
                evaluator_name=t.evaluation_gate.evaluator_name,
                min_pass_score=t.evaluation_gate.min_pass_score,
                max_revisions=t.evaluation_gate.max_revisions,
                deterministic_rules=t.evaluation_gate.deterministic_rules,
                criteria=t.evaluation_gate.criteria,
                rejection_policy=t.evaluation_gate.rejection_policy,
            )
            tasks.append(
                TaskSpec(
                    task_key=t.task_key,
                    name=t.name,
                    agent_id=t.agent_id,
                    depends_on=t.depends_on,
                    input_mappings=t.input_mappings,
                    static_inputs=t.static_inputs,
                    timeout_seconds=t.timeout_seconds,
                    retry_policy=retry_pol,
                    approval_gate=approval_gt,
                    evaluation_gate=eval_gt,
                )
            )

        spec = WorkflowSpec(
            name=request.name,
            version=request.version,
            description=request.description,
            input_schema=request.input_schema,
            output_schema=request.output_schema,
            tasks=tasks,
            max_workflow_duration_seconds=request.max_workflow_duration_seconds,
            max_parallel_tasks=request.max_parallel_tasks,
        )

        # 1. Topological graph validation
        DependencyResolver.validate_workflow_graph(spec)

        # 2. Persist workflow specification
        saved_spec = await self.workflow_repo.save_workflow_spec(spec)
        logger.info("Workflow spec registered", workflow_id=saved_spec.id, name=saved_spec.name)
        return saved_spec

    async def get_workflow(self, workflow_id: str) -> WorkflowSpec:
        """Retrieves a specific workflow specification by ID."""
        spec = await self.workflow_repo.get_workflow_spec(workflow_id)
        if not spec:
            raise WorkflowNotFoundError(f"Workflow '{workflow_id}' does not exist.")
        return spec

    async def list_workflows(self, limit: int = 50, offset: int = 0) -> List[WorkflowSpec]:
        """Lists registered workflow specifications with pagination."""
        return await self.workflow_repo.list_workflow_specs(limit=limit, offset=offset)
