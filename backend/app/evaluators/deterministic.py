"""Deterministic rule-based quality evaluator (Layer 1 Gate)."""

import time
from typing import Any, Dict, List, Optional
import structlog

from ..domain.models.evaluation import (
    EvaluationRequest,
    EvaluationResult,
    EvaluationVerdict,
)

logger = structlog.get_logger(__name__)


class DeterministicRuleEvaluator:
    """
    Deterministic rule-based quality evaluator (Layer 1 Gate).
    Executes fast, zero-cost, deterministic checks before any LLM evaluation:
    - Output presence and non-emptiness
    - Required field presence based on task criteria
    - Artifact presence and format validation
    - Configured deterministic rule checks
    """

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        start_time = time.perf_counter()
        passed_checks: List[str] = []
        failed_checks: List[str] = []
        required_changes: List[str] = []

        output = request.output_payload

        # 1. Output Presence Check
        if not output or not isinstance(output, dict):
            failed_checks.append("output_payload_present")
            required_changes.append("Task execution must produce a non-empty dictionary output_payload.")
        else:
            passed_checks.append("output_payload_present")

        # 2. Required Fields Check (from criteria.get('required_fields', []))
        required_fields: List[str] = request.evaluation_criteria.get("required_fields", [])
        for field_name in required_fields:
            if field_name not in output or output[field_name] is None:
                failed_checks.append(f"required_field_{field_name}")
                required_changes.append(f"Missing mandatory field '{field_name}' in output.")
            else:
                passed_checks.append(f"required_field_{field_name}")

        # 3. Minimum Content Length Checks (if specified)
        min_length_rules: Dict[str, int] = request.evaluation_criteria.get("min_lengths", {})
        for field_name, min_len in min_length_rules.items():
            if field_name in output:
                val = output[field_name]
                actual_len = len(val) if hasattr(val, "__len__") else 0
                if actual_len < min_len:
                    failed_checks.append(f"min_length_{field_name}")
                    required_changes.append(
                        f"Field '{field_name}' length {actual_len} is below required minimum {min_len}."
                    )
                else:
                    passed_checks.append(f"min_length_{field_name}")

        # 4. Prohibited Substrings / Null Values (if specified)
        prohibited_terms: List[str] = request.evaluation_criteria.get("prohibited_terms", [])
        for term in prohibited_terms:
            output_str = str(output).lower()
            if term.lower() in output_str:
                failed_checks.append(f"prohibited_term_{term}")
                required_changes.append(f"Output contains prohibited term '{term}'.")
            else:
                passed_checks.append(f"prohibited_term_{term}")

        # Determine Verdict
        total_checks = len(passed_checks) + len(failed_checks)
        score = len(passed_checks) / total_checks if total_checks > 0 else 1.0
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        if failed_checks:
            # If revision budget remains, request revision; otherwise FAIL
            verdict = (
                EvaluationVerdict.REQUIRES_REVISION
                if request.current_revision < request.max_revisions
                else EvaluationVerdict.FAIL
            )
            return EvaluationResult(
                verdict=verdict,
                score=score,
                rationale=f"Deterministic rule check failed: {', '.join(failed_checks)}",
                passed_checks=passed_checks,
                failed_checks=failed_checks,
                actionable_feedback="Resolve all missing or invalid fields specified in required_changes.",
                required_changes=required_changes,
                evaluator_metadata={"evaluator_type": "deterministic_layer_1"},
                evaluation_duration_ms=duration_ms,
            )

        return EvaluationResult(
            verdict=EvaluationVerdict.PASS,
            score=1.0,
            rationale="All deterministic schema and rule validations passed successfully.",
            passed_checks=passed_checks,
            failed_checks=[],
            evaluator_metadata={"evaluator_type": "deterministic_layer_1"},
            evaluation_duration_ms=duration_ms,
        )
