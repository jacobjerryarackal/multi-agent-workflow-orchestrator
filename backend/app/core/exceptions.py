"""Core custom domain exceptions for the Multi-Agent Workflow Orchestrator."""

from typing import Any, Dict, Optional


class OrchestratorException(Exception):
    """Base exception for all orchestrator domain errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class WorkflowValidationError(OrchestratorException):
    """Raised when a workflow specification is structurally invalid."""
    pass


class CyclicDependencyError(WorkflowValidationError):
    """Raised when a circular dependency is detected in the DAG topology."""
    pass


class AgentNotFoundError(OrchestratorException):
    """Raised when a workflow references an agent not present in the registry."""
    pass


class SchemaValidationError(OrchestratorException):
    """Raised when task input or agent output violates contract schemas."""
    pass


class StateTransitionError(OrchestratorException):
    """Raised when an illegal or guard-violating state transition is attempted."""
    pass


class TaskExecutionTimeoutError(OrchestratorException):
    """Raised when a task exceeds its configured wall-clock timeout."""
    pass


class WorkflowTimeoutError(OrchestratorException):
    """Raised when a workflow run exceeds its maximum global duration."""
    pass


class CircuitBreakerOpenError(OrchestratorException):
    """Raised when an external provider call is blocked by an open circuit breaker."""
    pass


class ArtifactIntegrityError(OrchestratorException):
    """Raised when an artifact is missing or fails SHA-256 checksum verification."""
    pass


class ApprovalGateError(OrchestratorException):
    """Raised when an invalid approval action is attempted or approval SLA expires."""
    pass
