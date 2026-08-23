"""Domain models for Workflow specifications, tasks, policies, and gates."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class RetryPolicySpec(BaseModel):
    """Configuration for automated task retry behaviors."""
    max_attempts: int = Field(default=3, ge=0, le=5, description="Maximum number of retry attempts")
    initial_interval_seconds: float = Field(default=2.0, ge=0.1, le=60.0, description="Initial backoff delay in seconds")
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=5.0, description="Multiplier for exponential backoff")
    jitter: bool = Field(default=True, description="Whether to apply randomized decorrelated jitter")
    retryable_categories: List[str] = Field(
        default_factory=lambda: [
            "INFRASTRUCTURE_PROVIDER_FAILURE",
            "TEMPORAL_FAILURE",
            "CONTRACT_VALIDATION_FAILURE"
        ],
        description="List of failure categories eligible for retry"
    )


class ApprovalGateSpec(BaseModel):
    """Configuration for human-in-the-loop approval requirements."""
    required: bool = Field(default=False, description="Whether this task requires human signoff before advancing")
    approver_roles: List[str] = Field(default_factory=lambda: ["operator", "admin"])
    timeout_seconds: int = Field(default=86400, ge=60, description="SLA window for human approval")
    auto_action_on_timeout: str = Field(default="ESCALATE", description="'ESCALATE' or 'FAILED'")


class EvaluationGateSpec(BaseModel):
    """Configuration for automated quality evaluation gates."""
    enabled: bool = Field(default=False, description="Whether this task output requires quality evaluation")
    evaluator_name: str = Field(default="composite_quality_evaluator", description="Target evaluator name")
    min_pass_score: float = Field(default=0.8, ge=0.0, le=1.0, description="Minimum acceptable quality threshold [0.0, 1.0]")
    max_revisions: int = Field(default=2, ge=0, le=4, description="Maximum allowed evaluation revision cycles [0, 4]")
    deterministic_rules: List[str] = Field(default_factory=list, description="List of deterministic rule IDs to enforce")
    criteria: Dict[str, Any] = Field(default_factory=dict, description="Semantic criteria evaluated by LLM judge")
    rejection_policy: str = Field(default="FAIL", description="'FAIL', 'ESCALATE', or 'RETRY' upon revision exhaustion")


class TaskSpec(BaseModel):
    """Specification of an individual task node in the workflow DAG."""
    task_key: str = Field(..., description="Unique alphanumeric identifier for the task within the workflow")
    name: str = Field(..., description="Human-readable display name for the task")
    agent_id: str = Field(..., description="Identifier of the specialized agent executing this task")
    depends_on: List[str] = Field(default_factory=list, description="Keys of upstream tasks that must succeed first")
    input_mappings: Dict[str, str] = Field(
        default_factory=dict,
        description="JSONPath expressions mapping workflow inputs or upstream task outputs to this task's inputs"
    )
    static_inputs: Dict[str, Any] = Field(default_factory=dict, description="Static parameters passed directly to agent")
    timeout_seconds: int = Field(default=60, ge=5, le=300, description="Wall-clock timeout in seconds")
    retry_policy: RetryPolicySpec = Field(default_factory=RetryPolicySpec)
    approval_gate: ApprovalGateSpec = Field(default_factory=ApprovalGateSpec)
    evaluation_gate: EvaluationGateSpec = Field(default_factory=EvaluationGateSpec)


class WorkflowSpec(BaseModel):
    """Complete specification of a multi-agent workflow DAG."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique workflow specification ID")
    name: str = Field(..., description="Unique slug identifier for the workflow, e.g. 'deep_research'")
    version: int = Field(default=1, ge=1, description="Integer version number")
    description: str = Field(..., description="Concise description of the workflow capability")
    input_schema: Dict[str, Any] = Field(..., description="JSON Schema for initial workflow input validation")
    output_schema: Dict[str, Any] = Field(..., description="JSON Schema for final workflow output validation")
    tasks: List[TaskSpec] = Field(..., min_length=1, description="List of task nodes forming the DAG")
    max_workflow_duration_seconds: int = Field(default=600, ge=30, le=3600)
    max_parallel_tasks: int = Field(default=5, ge=1, le=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)
