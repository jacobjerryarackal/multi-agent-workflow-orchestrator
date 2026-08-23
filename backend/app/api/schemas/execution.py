"""API request and response schemas for Workflow and Task Executions."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SubmitExecutionRequest(BaseModel):
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Input parameters passed into workflow root tasks")
    idempotency_key: Optional[str] = Field(default=None, max_length=128, description="Optional client idempotency key")
    trigger_type: str = Field(default="api", description="'api', 'manual', or 'scheduled'")


class TaskApproveRequest(BaseModel):
    approver: str = Field(default="admin", min_length=1, description="Identity of operator granting approval")
    comment: Optional[str] = Field(default=None, description="Optional approval comments")


class TaskRejectRequest(BaseModel):
    rejector: str = Field(default="admin", min_length=1, description="Identity of operator rejecting task")
    reason: str = Field(..., min_length=1, description="Required justification for rejection")


class TaskExecutionSummaryResponse(BaseModel):
    id: str
    workflow_execution_id: str
    task_key: str
    agent_id: str
    status: str
    attempt_count: int
    revision_count: int
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    evaluation_history: List[Dict[str, Any]]
    error_details: Optional[Dict[str, Any]]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    execution_duration_ms: Optional[int]
    token_usage: Dict[str, int]


class WorkflowExecutionSummaryResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    trigger_type: str
    idempotency_key: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    execution_duration_ms: Optional[int]
    error_summary: Optional[str]


class WorkflowExecutionDetailResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    trigger_type: str
    idempotency_key: Optional[str]
    initial_inputs: Dict[str, Any]
    final_outputs: Dict[str, Any]
    error_summary: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    execution_duration_ms: Optional[int]
    tasks: List[TaskExecutionSummaryResponse] = Field(default_factory=list)


class ExecutionListResponse(BaseModel):
    items: List[WorkflowExecutionSummaryResponse]
    total_count: int
