"""Composite Quality Evaluator coordinating Layer 1 (Deterministic) and Layer 2 (Semantic LLM)."""

import time
from typing import Optional
import structlog

from ..domain.interfaces.model_provider import ModelProvider
from ..domain.models.evaluation import (
    EvaluationRequest,
    EvaluationResult,
    EvaluationVerdict,
)
from .deterministic import DeterministicRuleEvaluator
from .gemini_evaluator import GeminiSemanticEvaluator

logger = structlog.get_logger(__name__)


class CompositeQualityEvaluator:
    """
    Two-layer quality evaluation pipeline:
    Layer 1: Fast deterministic rule/schema check.
    Layer 2: Gemini LLM semantic quality judge (invoked only if Layer 1 passes).
    """

    def __init__(
        self,
        model_provider: Optional[ModelProvider] = None,
        deterministic_evaluator: Optional[DeterministicRuleEvaluator] = None,
    ):
        self.deterministic_evaluator = deterministic_evaluator or DeterministicRuleEvaluator()
        self.semantic_evaluator = (
            GeminiSemanticEvaluator(model_provider) if model_provider else None
        )

    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        start_time = time.perf_counter()

        # 1. Execute Layer 1 Deterministic Evaluation
        deterministic_result = self.deterministic_evaluator.evaluate(request)
        if deterministic_result.verdict != EvaluationVerdict.PASS:
            logger.info(
                "Deterministic evaluation gate failed; skipping LLM judge",
                task_key=request.task_key,
                verdict=deterministic_result.verdict,
                failed_checks=deterministic_result.failed_checks,
            )
            return deterministic_result

        # 2. Check if Layer 2 Semantic Evaluation is configured
        has_semantic_criteria = bool(request.evaluation_criteria.get("semantic_criteria") or request.evaluation_criteria.get("description"))
        if not self.semantic_evaluator or not has_semantic_criteria:
            # Only deterministic checks were requested and they passed
            return deterministic_result

        # 3. Execute Layer 2 Semantic Evaluation
        logger.info(
            "Deterministic checks passed; invoking Layer 2 semantic evaluator",
            task_key=request.task_key,
        )
        semantic_result = await self.semantic_evaluator.evaluate(request)
        
        # Merge Layer 1 passed checks into Layer 2 result
        all_passed = list(set(deterministic_result.passed_checks + semantic_result.passed_checks))
        semantic_result.passed_checks = all_passed
        return semantic_result
