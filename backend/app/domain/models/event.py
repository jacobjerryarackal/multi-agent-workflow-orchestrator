"""Domain models for immutable Workflow Events, telemetry, and event stream schemas."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Enumeration of all supported orchestrator lifecycle events."""

    # Workflow Lifecycle
    WORKFLOW_SUBMITTED = "WORKFLOW_SUBMITTED"
    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_PAUSED = "WORKFLOW_PAUSED"
    WORKFLOW_RESUMED = "WORKFLOW_RESUMED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    WORKFLOW_CANCELLED = "WORKFLOW_CANCELLED"
    WORKFLOW_TIMED_OUT = "WORKFLOW_TIMED_OUT"

    # Task Lifecycle
    TASK_SCHEDULED = "TASK_SCHEDULED"
    TASK_READY = "TASK_READY"
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    TASK_RETRIED = "TASK_RETRIED"
    TASK_CANCELLED = "TASK_CANCELLED"
    TASK_TIMED_OUT = "TASK_TIMED_OUT"

    # Quality & Human-in-the-Loop Gates
    TASK_WAITING_APPROVAL = "TASK_WAITING_APPROVAL"
    APPROVAL_DECISION_RECORDED = "APPROVAL_DECISION_RECORDED"
    EVALUATION_GATE_SCORED = "EVALUATION_GATE_SCORED"
    EVALUATION_STARTED = "EVALUATION_STARTED"
    EVALUATION_COMPLETED = "EVALUATION_COMPLETED"
    EVALUATION_PASSED = "EVALUATION_PASSED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    EVALUATION_ESCALATED = "EVALUATION_ESCALATED"

    # Data & System Events
    ARTIFACT_PRODUCED = "ARTIFACT_PRODUCED"
    CIRCUIT_BREAKER_TRIGGERED = "CIRCUIT_BREAKER_TRIGGERED"
    STATE_CHECKPOINT_SAVED = "STATE_CHECKPOINT_SAVED"


class WorkflowEvent(BaseModel):
    """Immutable event record representing a discrete occurrence in the workflow lifecycle."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_execution_id: str
    workflow_id: str
    task_execution_id: Optional[str] = None
    task_key: Optional[str] = None
    agent_id: Optional[str] = None
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: Dict[str, Any] = Field(default_factory=dict)
    actor: str = Field(default="system", description="'system', 'scheduler', or user email for approvals")
