"""Domain models for runtime Workflow Execution and Task Execution instances."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class WorkflowExecutionStatus(str, Enum):
    """Lifecycle states for overall workflow execution."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


class TaskExecutionStatus(str, Enum):
    """Lifecycle states for individual task executions in the DAG."""
    PENDING = "PENDING"
    BLOCKED = "BLOCKED"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    ESCALATED = "ESCALATED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


class TaskExecution(BaseModel):
    """Runtime instance and execution state of a specific task within a workflow run."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_execution_id: str
    task_key: str
    agent_id: str
    status: TaskExecutionStatus = TaskExecutionStatus.PENDING
    attempt_count: int = 0
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    error_details: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_duration_ms: Optional[int] = None
    token_usage: Dict[str, int] = Field(default_factory=dict)


class WorkflowExecution(BaseModel):
    """Runtime execution instance of a workflow."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str
    status: WorkflowExecutionStatus = WorkflowExecutionStatus.QUEUED
    trigger_type: str = Field(default="manual", description="'manual', 'api', or 'scheduled'")
    idempotency_key: Optional[str] = None
    initial_inputs: Dict[str, Any] = Field(default_factory=dict)
    final_outputs: Dict[str, Any] = Field(default_factory=dict)
    error_summary: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_duration_ms: Optional[int] = None
    tasks: Dict[str, TaskExecution] = Field(default_factory=dict)
