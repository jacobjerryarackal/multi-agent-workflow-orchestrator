"""Domain interfaces package aggregation."""

from .agent import BaseAgent
from .model_provider import ModelProvider
from .context_provider import ContextProvider
from .evaluation_provider import (
    EvaluationProvider,
    EvaluationResult,
    EvaluationVerdict,
)
from .repository import (
    WorkflowRepository,
    ExecutionRepository,
    EventRepository,
    ArtifactRepository,
)

__all__ = [
    "BaseAgent",
    "ModelProvider",
    "ContextProvider",
    "EvaluationProvider",
    "EvaluationResult",
    "EvaluationVerdict",
    "WorkflowRepository",
    "ExecutionRepository",
    "EventRepository",
    "ArtifactRepository",
]
