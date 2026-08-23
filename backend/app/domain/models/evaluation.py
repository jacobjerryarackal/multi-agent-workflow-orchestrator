"""Domain models for Quality Evaluation, verdicts, requests, results, and revision context."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvaluationVerdict(str, Enum):
    """Explicit verdict decision emitted by an evaluator."""
    PASS = "PASS"                           # Quality meets/exceeds criteria; proceed to completion
    REQUIRES_REVISION = "REQUIRES_REVISION" # Quality sub-par; actionable revision possible within budget
    FAIL = "FAIL"                           # Unrecoverable defect; fail task
    ESCALATE = "ESCALATE"                   # Ambiguous or high-risk; requires human operator signoff


class RevisionContext(BaseModel):
    """Bounded revision feedback injected into an agent during re-execution."""
    revision_number: int = Field(..., ge=1, description="1-based current revision cycle")
    evaluator_verdict: EvaluationVerdict = Field(default=EvaluationVerdict.REQUIRES_REVISION)
    score: float = Field(..., ge=0.0, le=1.0)
    failed_checks: List[str] = Field(default_factory=list)
    required_changes: List[str] = Field(default_factory=list)
    actionable_feedback: Optional[str] = None


class EvaluationRequest(BaseModel):
    """Structured request payload dispatched to an EvaluationProvider."""
    workflow_execution_id: str
    task_key: str
    agent_id: str
    input_payload: Dict[str, Any] = Field(default_factory=dict)
    output_payload: Dict[str, Any] = Field(default_factory=dict)
    produced_artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    evaluation_criteria: Dict[str, Any] = Field(default_factory=dict)
    min_pass_score: float = Field(default=0.8, ge=0.0, le=1.0)
    current_revision: int = Field(default=0, ge=0)
    max_revisions: int = Field(default=2, ge=0, le=4)


class EvaluationResult(BaseModel):
    """Structured evaluation output scoring a task execution."""
    verdict: EvaluationVerdict
    score: float = Field(..., ge=0.0, le=1.0, description="Normalized quality score between 0.0 and 1.0")
    rationale: str = Field(..., description="Explanation of why the output received this verdict")
    passed_checks: List[str] = Field(default_factory=list)
    failed_checks: List[str] = Field(default_factory=list)
    actionable_feedback: Optional[str] = None
    required_changes: List[str] = Field(default_factory=list)
    evaluator_metadata: Dict[str, Any] = Field(default_factory=dict)
    evaluation_duration_ms: int = Field(default=0, ge=0)
    token_usage: Dict[str, int] = Field(default_factory=dict)
