"""LLM-based semantic evaluator using ModelProvider abstraction."""

import json
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import structlog

from ..core.exceptions import EvaluatorError, ModelProviderError
from ..domain.interfaces.model_provider import ModelProvider
from ..domain.models.evaluation import (
    EvaluationRequest,
    EvaluationResult,
    EvaluationVerdict,
)

logger = structlog.get_logger(__name__)


class LLMEvaluationSchema(BaseModel):
    """Structured Pydantic schema enforced on LLM evaluator responses."""
    verdict: EvaluationVerdict = Field(..., description="Verdict: PASS, REQUIRES_REVISION, FAIL, or ESCALATE")
    score: float = Field(..., ge=0.0, le=1.0, description="Quality score from 0.0 to 1.0")
    rationale: str = Field(..., description="Detailed explanation for the verdict and score")
    passed_checks: List[str] = Field(default_factory=list, description="Specific criteria that passed")
    failed_checks: List[str] = Field(default_factory=list, description="Specific criteria that failed")
    actionable_feedback: Optional[str] = Field(default=None, description="Clear, actionable guidance for revision")
    required_changes: List[str] = Field(default_factory=list, description="Exact list of required modifications")


class GeminiSemanticEvaluator:
    """
    Semantic Quality Evaluator powered by a ModelProvider (Gemini gateway).
    Evaluates task outputs against qualitative criteria and enforces Pydantic structured output validation.
    """

    def __init__(self, model_provider: ModelProvider, model_name: str = "gemini-2.5-pro"):
        self.model_provider = model_provider
        self.model_name = model_name

    def _build_prompt(self, request: EvaluationRequest) -> str:
        """Constructs a bounded evaluation prompt with task context, criteria, and outputs."""
        prompt_data = {
            "task_key": request.task_key,
            "agent_id": request.agent_id,
            "min_pass_score": request.min_pass_score,
            "current_revision": request.current_revision,
            "max_revisions": request.max_revisions,
            "evaluation_criteria": request.evaluation_criteria,
            "input_payload": request.input_payload,
            "output_payload": request.output_payload,
            "produced_artifacts_summary": [
                {"name": a.get("name"), "type": a.get("artifact_type")}
                for a in request.produced_artifacts
            ],
        }
        return (
            "You are an expert AI Quality Evaluator. Rigorously evaluate the following task output against the specified criteria.\n\n"
            f"EVALUATION CONTEXT:\n```json\n{json.dumps(prompt_data, indent=2, default=str)}\n```\n\n"
            "EVALUATION RULES:\n"
            "1. If score >= min_pass_score and all required checks pass, verdict MUST be 'PASS'.\n"
            "2. If the output has fixable quality defects and current_revision < max_revisions, verdict MUST be 'REQUIRES_REVISION'.\n"
            "3. If the output is completely wrong, hallucinated, or unrecoverable, verdict MUST be 'FAIL'.\n"
            "4. If the output requires human judgment or presents critical risks, verdict MUST be 'ESCALATE'.\n"
            "5. Provide actionable_feedback and required_changes whenever verdict is REQUIRES_REVISION."
        )

    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        """Runs semantic evaluation through the ModelProvider and returns structured EvaluationResult."""
        system_instruction = (
            "You are an objective, rigorous AI Quality Evaluator in a multi-agent orchestration engine. "
            "Evaluate the provided agent outputs strictly against criteria. Return your evaluation strictly structured."
        )
        prompt = self._build_prompt(request)
        start_time = time.perf_counter()

        try:
            structured_res, token_metrics = await self.model_provider.generate_structured(
                prompt=prompt,
                system_instruction=system_instruction,
                response_schema=LLMEvaluationSchema,
                temperature=0.1,
                timeout_seconds=30.0,
            )
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            if not isinstance(structured_res, LLMEvaluationSchema):
                raise EvaluatorError("Evaluator did not return an instance of LLMEvaluationSchema")

            # Final verdict gate: if score < min_pass_score and verdict is PASS, correct to REQUIRES_REVISION / FAIL
            verdict = structured_res.verdict
            if verdict == EvaluationVerdict.PASS and structured_res.score < request.min_pass_score:
                verdict = (
                    EvaluationVerdict.REQUIRES_REVISION
                    if request.current_revision < request.max_revisions
                    else EvaluationVerdict.FAIL
                )

            return EvaluationResult(
                verdict=verdict,
                score=structured_res.score,
                rationale=structured_res.rationale,
                passed_checks=structured_res.passed_checks,
                failed_checks=structured_res.failed_checks,
                actionable_feedback=structured_res.actionable_feedback,
                required_changes=structured_res.required_changes,
                evaluator_metadata={"evaluator_type": "gemini_semantic", "model": self.model_name},
                evaluation_duration_ms=duration_ms,
                token_usage=token_metrics.model_dump(),
            )

        except (ModelProviderError, Exception) as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error("Evaluator provider failure", error=str(exc), task_key=request.task_key)
            # NEVER silently pass on evaluator infrastructure failure
            return EvaluationResult(
                verdict=EvaluationVerdict.FAIL,
                score=0.0,
                rationale=f"Evaluator infrastructure failure: {str(exc)}",
                failed_checks=["evaluator_infrastructure_available"],
                evaluator_metadata={"error": str(exc), "category": "evaluator_infrastructure_failure"},
                evaluation_duration_ms=duration_ms,
            )
