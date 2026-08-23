"""API request and response schemas for Workflow definitions and specifications."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RetryPolicySchema(BaseModel):
    max_attempts: int = Field(default=3, ge=0, le=5)
    initial_interval_seconds: float = Field(default=2.0, ge=0.1, le=60.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=5.0)
    jitter: bool = True
    retryable_categories: List[str] = Field(
        default_factory=lambda: [
            "INFRASTRUCTURE_PROVIDER_FAILURE",
            "TEMPORAL_FAILURE",
            "CONTRACT_VALIDATION_FAILURE",
        ]
    )


class ApprovalGateSchema(BaseModel):
    required: bool = False
    approver_roles: List[str] = Field(default_factory=lambda: ["operator", "admin"])
    timeout_seconds: int = Field(default=86400, ge=60)
    auto_action_on_timeout: str = "ESCALATE"


class EvaluationGateSchema(BaseModel):
    enabled: bool = False
    evaluator_name: str = "composite_quality_evaluator"
    min_pass_score: float = Field(default=0.8, ge=0.0, le=1.0)
    max_revisions: int = Field(default=2, ge=0, le=4)
    deterministic_rules: List[str] = Field(default_factory=list)
    criteria: Dict[str, Any] = Field(default_factory=dict)
    rejection_policy: str = "FAIL"


class TaskSpecSchema(BaseModel):
    task_key: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    agent_id: str = Field(..., min_length=1, max_length=64)
    depends_on: List[str] = Field(default_factory=list)
    input_mappings: Dict[str, str] = Field(default_factory=dict)
    static_inputs: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    retry_policy: RetryPolicySchema = Field(default_factory=RetryPolicySchema)
    approval_gate: ApprovalGateSchema = Field(default_factory=ApprovalGateSchema)
    evaluation_gate: EvaluationGateSchema = Field(default_factory=EvaluationGateSchema)


class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    version: int = Field(default=1, ge=1)
    description: str = Field(..., min_length=1)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    tasks: List[TaskSpecSchema] = Field(..., min_length=1)
    max_workflow_duration_seconds: int = Field(default=600, ge=30, le=3600)
    max_parallel_tasks: int = Field(default=5, ge=1, le=20)


class WorkflowResponse(BaseModel):
    id: str
    name: str
    version: int
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    tasks: List[TaskSpecSchema]
    max_workflow_duration_seconds: int
    max_parallel_tasks: int
    created_at: datetime


class WorkflowListResponse(BaseModel):
    items: List[WorkflowResponse]
    total_count: int
