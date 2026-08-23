"""Domain models for Failure Classification, recovery actions, and circuit breaker metrics."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, Field


class FailureCategory(str, Enum):
    """Categorization of failure modes across the orchestration lifecycle."""
    INFRASTRUCTURE_PROVIDER_FAILURE = "INFRASTRUCTURE_PROVIDER_FAILURE"
    CONTRACT_VALIDATION_FAILURE = "CONTRACT_VALIDATION_FAILURE"
    DEPENDENCY_TOPOLOGY_FAILURE = "DEPENDENCY_TOPOLOGY_FAILURE"
    RUNTIME_RESOURCE_FAILURE = "RUNTIME_RESOURCE_FAILURE"
    TEMPORAL_FAILURE = "TEMPORAL_FAILURE"
    INTEGRITY_ARTIFACT_FAILURE = "INTEGRITY_ARTIFACT_FAILURE"
    QUALITY_EVALUATION_FAILURE = "QUALITY_EVALUATION_FAILURE"
    CONCURRENCY_STATE_FAILURE = "CONCURRENCY_STATE_FAILURE"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"


class FailureSeverity(str, Enum):
    """Severity levels for failure occurrences."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecoveryActionType(str, Enum):
    """Determined recovery actions executed in response to a failure."""
    RETRY_WITH_BACKOFF = "RETRY_WITH_BACKOFF"
    RETRY_WITH_REFLECTION = "RETRY_WITH_REFLECTION"
    CIRCUIT_BREAKER_TRIP = "CIRCUIT_BREAKER_TRIP"
    FALLBACK_AGENT_ROUTING = "FALLBACK_AGENT_ROUTING"
    ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"
    TERMINAL_TASK_FAILURE = "TERMINAL_TASK_FAILURE"
    TERMINAL_WORKFLOW_ABORT = "TERMINAL_WORKFLOW_ABORT"


class FailureRecord(BaseModel):
    """Record of an individual failure occurrence during execution."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_execution_id: str
    task_key: Optional[str] = None
    agent_id: Optional[str] = None
    category: FailureCategory
    severity: FailureSeverity
    error_type: str
    error_message: str
    retryable: bool
    attempt_number: int = 1
    recovery_action: RecoveryActionType
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
