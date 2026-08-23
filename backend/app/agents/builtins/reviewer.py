"""Reviewer specialized agent for critical evaluation, audit, and quality gating."""

from enum import Enum
from typing import Any, Dict, List, Type
from pydantic import BaseModel, Field

from ..base import AbstractAgent
from ...domain.interfaces.model_provider import ModelProvider
from ...domain.models.agent import (
    AgentCapability,
    AgentExecutionContext,
    AgentMetadata,
    ProducedArtifact,
)


class ReviewDecision(str, Enum):
    """Verdict decision of the review evaluation."""
    PASS = "PASS"
    FAIL = "FAIL"
    REQUIRES_REVISION = "REQUIRES_REVISION"


class ReviewIssue(BaseModel):
    """An identified flaw, inconsistency, or gap in the evaluated content."""
    description: str = Field(..., description="Explanation of the issue or inconsistency")
    severity: str = Field(default="MEDIUM", description="'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'")


class ReviewInput(BaseModel):
    """Input payload accepted by the ReviewerAgent."""
    target_content: Dict[str, Any] = Field(..., description="Proposed findings, plan, or analysis to evaluate")
    quality_standards: List[str] = Field(default_factory=list, description="Explicit criteria or compliance rules")
    context: Dict[str, Any] = Field(default_factory=dict, description="Contextual constraints or guidelines")


class ReviewOutput(BaseModel):
    """Structured audit verdict produced by the ReviewerAgent."""
    decision: ReviewDecision = Field(..., description="'PASS', 'FAIL', or 'REQUIRES_REVISION'")
    passed_checks: List[str] = Field(default_factory=list, description="Verified standards that passed successfully")
    failed_checks: List[str] = Field(default_factory=list, description="Standards that failed verification")
    issues: List[ReviewIssue] = Field(default_factory=list, description="Detailed list of identified issues")
    required_changes: List[str] = Field(default_factory=list, description="Required revisions if not PASS")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="Evaluator confidence in review decision")


class ReviewerAgent(AbstractAgent):
    """
    Specialized agent responsible for adversarial auditing, fact-checking, and quality gating.
    Emits explicit PASS, FAIL, or REQUIRES_REVISION verdicts.
    """

    def __init__(self, model_provider: ModelProvider):
        super().__init__(model_provider)
        self._metadata = AgentMetadata(
            agent_id="reviewer_agent",
            name="Quality & Verification Auditor",
            version="1.0.0",
            description="Audits task outputs against quality standards and flags contradictions or defects.",
            capabilities=[AgentCapability.CRITIQUE, AgentCapability.VALIDATION],
            system_instruction=(
                "You are an adversarial Quality and Audit Specialist. Your responsibility is to critically "
                "evaluate proposed outputs against strict quality standards. Never give rubber-stamp approvals. "
                "Check for logical contradictions, missing evidence, unverified assumptions, and adherence to constraints. "
                "Return valid JSON strictly matching the ReviewOutput schema."
            ),
            default_model="gemini-2.5-flash",
            temperature=0.1,
        )

    @property
    def metadata(self) -> AgentMetadata:
        return self._metadata

    @property
    def input_schema(self) -> Type[BaseModel]:
        return ReviewInput

    @property
    def output_schema(self) -> Type[BaseModel]:
        return ReviewOutput

    def build_prompt(self, context: AgentExecutionContext, validated_input: BaseModel) -> str:
        inp: ReviewInput = validated_input  # type: ignore
        standards_str = "\n".join(f"- {s}" for s in inp.quality_standards) if inp.quality_standards else "Check for factuality, logical consistency, completeness, and clarity."
        return (
            f"Content to Audit:\n{inp.target_content}\n\n"
            f"Quality Standards:\n{standards_str}\n\n"
            f"Operational Context:\n{inp.context}\n\n"
            "Evaluate rigorously. If defects exist, specify them with severity and state decision as FAIL or REQUIRES_REVISION."
        )

    def produce_artifacts(self, output: BaseModel, context: AgentExecutionContext) -> List[ProducedArtifact]:
        rev: ReviewOutput = output  # type: ignore
        import hashlib
        import json
        content = json.dumps(rev.model_dump(), sort_keys=True)
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return [
            ProducedArtifact(
                name="audit_report.json",
                artifact_type="json",
                content_or_uri=content,
                checksum_sha256=checksum,
                metadata={"decision": rev.decision.value, "issue_count": len(rev.issues)},
            )
        ]
