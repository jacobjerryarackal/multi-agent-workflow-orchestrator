"""Abstract interface protocol for Quality Evaluators."""

from typing import Protocol
from ..models.evaluation import EvaluationRequest, EvaluationResult, EvaluationVerdict


class EvaluationProvider(Protocol):
    """Protocol for scoring and validating task outputs against quality criteria."""

    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        """Evaluates a task output request and returns a structured EvaluationResult."""
        ...
