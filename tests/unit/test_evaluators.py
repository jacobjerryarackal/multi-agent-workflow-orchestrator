"""Unit tests for Deterministic, Semantic, and Composite Evaluators."""

import pytest
from app.domain.models.agent import TokenUsageMetrics
from app.domain.models.evaluation import (
    EvaluationRequest,
    EvaluationResult,
    EvaluationVerdict,
)
from app.evaluators.deterministic import DeterministicRuleEvaluator
from app.evaluators.gemini_evaluator import GeminiSemanticEvaluator, LLMEvaluationSchema
from app.evaluators.composite import CompositeQualityEvaluator
from app.core.exceptions import ModelProviderError


class MockProviderSuccess:
    def __init__(self, response_schema_instance):
        self.response_schema_instance = response_schema_instance

    async def generate_structured(self, prompt, system_instruction, response_schema, temperature=0.1, timeout_seconds=30.0):
        return self.response_schema_instance, TokenUsageMetrics(prompt_tokens=100, completion_tokens=50, total_tokens=150)

    async def generate_text(self, prompt, system_instruction, temperature=0.2, timeout_seconds=60.0):
        return "text", TokenUsageMetrics(total_tokens=10)


class MockProviderFailure:
    async def generate_structured(self, prompt, system_instruction, response_schema, temperature=0.1, timeout_seconds=30.0):
        raise ModelProviderError("Gemini API connection reset")

    async def generate_text(self, prompt, system_instruction, temperature=0.2, timeout_seconds=60.0):
        raise ModelProviderError("Gemini API connection reset")


# =============================================================================
# 1. DETERMINISTIC EVALUATOR TESTS
# =============================================================================

def test_deterministic_evaluator_pass_when_all_rules_met():
    evaluator = DeterministicRuleEvaluator()
    request = EvaluationRequest(
        workflow_execution_id="w-1",
        task_key="t1",
        agent_id="planner",
        output_payload={"plan": "Step 1, Step 2", "confidence": 0.95},
        evaluation_criteria={"required_fields": ["plan", "confidence"]},
    )
    result = evaluator.evaluate(request)
    assert result.verdict == EvaluationVerdict.PASS
    assert result.score == 1.0
    assert len(result.failed_checks) == 0


def test_deterministic_evaluator_missing_required_fields_fails():
    evaluator = DeterministicRuleEvaluator()
    request = EvaluationRequest(
        workflow_execution_id="w-1",
        task_key="t1",
        agent_id="planner",
        output_payload={"plan": "Incomplete"},
        evaluation_criteria={"required_fields": ["plan", "confidence"]},
        current_revision=0,
        max_revisions=2,
    )
    result = evaluator.evaluate(request)
    assert result.verdict == EvaluationVerdict.REQUIRES_REVISION
    assert "required_field_confidence" in result.failed_checks
    assert len(result.required_changes) > 0


def test_deterministic_evaluator_prohibited_terms_detected():
    evaluator = DeterministicRuleEvaluator()
    request = EvaluationRequest(
        workflow_execution_id="w-1",
        task_key="t1",
        agent_id="planner",
        output_payload={"text": "This contains TODO in production"},
        evaluation_criteria={"prohibited_terms": ["TODO"]},
        current_revision=0,
        max_revisions=1,
    )
    result = evaluator.evaluate(request)
    assert result.verdict == EvaluationVerdict.REQUIRES_REVISION
    assert "prohibited_term_TODO" in result.failed_checks


def test_deterministic_evaluator_revisions_exhausted_returns_fail():
    evaluator = DeterministicRuleEvaluator()
    request = EvaluationRequest(
        workflow_execution_id="w-1",
        task_key="t1",
        agent_id="planner",
        output_payload={},
        evaluation_criteria={"required_fields": ["plan"]},
        current_revision=2,
        max_revisions=2,  # Exhausted
    )
    result = evaluator.evaluate(request)
    assert result.verdict == EvaluationVerdict.FAIL


# =============================================================================
# 2. SEMANTIC GEMINI EVALUATOR TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_gemini_semantic_evaluator_success_pass():
    schema = LLMEvaluationSchema(
        verdict=EvaluationVerdict.PASS,
        score=0.95,
        rationale="High quality research output.",
        passed_checks=["depth", "accuracy"],
        failed_checks=[],
        required_changes=[],
    )
    provider = MockProviderSuccess(schema)
    evaluator = GeminiSemanticEvaluator(provider)

    request = EvaluationRequest(
        workflow_execution_id="w-1",
        task_key="t1",
        agent_id="researcher",
        output_payload={"findings": ["Good data"]},
        evaluation_criteria={"description": "Thorough research"},
        min_pass_score=0.8,
    )
    result = await evaluator.evaluate(request)
    assert result.verdict == EvaluationVerdict.PASS
    assert result.score == 0.95
    assert result.rationale == "High quality research output."


@pytest.mark.asyncio
async def test_gemini_semantic_evaluator_low_score_overrides_pass_verdict():
    """If the LLM emits PASS but score < min_pass_score, gate overrides to REQUIRES_REVISION."""
    schema = LLMEvaluationSchema(
        verdict=EvaluationVerdict.PASS,
        score=0.65,  # Below min_pass_score=0.8
        rationale="Adequate but slightly shallow.",
        passed_checks=["basic_facts"],
        failed_checks=["in_depth_citations"],
        actionable_feedback="Include deeper citations.",
        required_changes=["Add reference links"],
    )
    provider = MockProviderSuccess(schema)
    evaluator = GeminiSemanticEvaluator(provider)

    request = EvaluationRequest(
        workflow_execution_id="w-1",
        task_key="t1",
        agent_id="researcher",
        output_payload={"findings": ["Brief data"]},
        evaluation_criteria={"description": "Thorough research"},
        min_pass_score=0.8,
        current_revision=0,
        max_revisions=2,
    )
    result = await evaluator.evaluate(request)
    assert result.verdict == EvaluationVerdict.REQUIRES_REVISION
    assert result.score == 0.65


@pytest.mark.asyncio
async def test_gemini_semantic_evaluator_provider_failure_returns_fail():
    """Evaluator infrastructure failure NEVER silently passes."""
    provider = MockProviderFailure()
    evaluator = GeminiSemanticEvaluator(provider)

    request = EvaluationRequest(
        workflow_execution_id="w-1",
        task_key="t1",
        agent_id="researcher",
        output_payload={"findings": ["Data"]},
        evaluation_criteria={"description": "Thorough research"},
    )
    result = await evaluator.evaluate(request)
    assert result.verdict == EvaluationVerdict.FAIL
    assert result.score == 0.0
    assert "Evaluator infrastructure failure" in result.rationale


# =============================================================================
# 3. COMPOSITE EVALUATOR TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_composite_evaluator_deterministic_failure_skips_llm():
    """When Layer 1 fails, Layer 2 LLM provider is never called."""
    provider = MockProviderFailure()  # Would raise if called
    evaluator = CompositeQualityEvaluator(model_provider=provider)

    request = EvaluationRequest(
        workflow_execution_id="w-1",
        task_key="t1",
        agent_id="researcher",
        output_payload={},  # Empty output fails Layer 1
        evaluation_criteria={"required_fields": ["data"], "description": "Semantic check"},
        current_revision=0,
        max_revisions=2,
    )
    result = await evaluator.evaluate(request)
    assert result.verdict == EvaluationVerdict.REQUIRES_REVISION
    assert "output_payload_present" in result.failed_checks
    assert result.evaluator_metadata["evaluator_type"] == "deterministic_layer_1"


@pytest.mark.asyncio
async def test_composite_evaluator_deterministic_pass_proceeds_to_llm():
    """When Layer 1 passes, Layer 2 LLM evaluator runs and merges passed checks."""
    schema = LLMEvaluationSchema(
        verdict=EvaluationVerdict.PASS,
        score=0.92,
        rationale="Semantic criteria met.",
        passed_checks=["semantic_depth"],
        failed_checks=[],
        required_changes=[],
    )
    provider = MockProviderSuccess(schema)
    evaluator = CompositeQualityEvaluator(model_provider=provider)

    request = EvaluationRequest(
        workflow_execution_id="w-1",
        task_key="t1",
        agent_id="researcher",
        output_payload={"data": "Valid facts"},
        evaluation_criteria={"required_fields": ["data"], "description": "Semantic check"},
        min_pass_score=0.8,
    )
    result = await evaluator.evaluate(request)
    assert result.verdict == EvaluationVerdict.PASS
    assert result.score == 0.92
    assert "required_field_data" in result.passed_checks
    assert "semantic_depth" in result.passed_checks
