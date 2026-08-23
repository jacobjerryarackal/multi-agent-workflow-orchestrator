"""Abstract interface protocol for Quality Evaluators (EvalForge integration)."""

from enum import Enum
from typing import Any, Dict, Protocol
from pydantic import BaseModel, Field


class EvaluationVerdict(str, Enum):
    """Verdict result returned by an evaluator for a task output."""
    PASS = "PASS"
    FAIL = "FAIL"
    RETRY = "RETRY"
    ESCALATE = "ESCALATE"


class EvaluationResult(BaseModel):
    """Structured evaluation output scoring a task execution."""
    verdict: EvaluationVerdict
    score: float = Field(..., ge=0.0, le=1.0, description="Normalized quality score between 0.0 and 1.0")
    rationale: str = Field(..., description="Explanation of why the output passed or failed")
    feedback: str | None = Field(default=None, description="Actionable revision guidance for retries")


class EvaluationProvider(Protocol):
    """Protocol for scoring task outputs against quality criteria."""

    async def evaluate_task_output(
        self,
        task_key: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        criteria: Dict[str, Any],
    ) -> EvaluationResult:
        """Evaluates a task output against specified criteria."""
        ...
