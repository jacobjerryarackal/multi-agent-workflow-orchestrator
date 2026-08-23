"""Synthesizer specialized agent for aggregating multi-agent findings into cohesive deliverables."""

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


class SynthesisInput(BaseModel):
    """Input payload accepted by the SynthesizerAgent."""
    planner_summary: str = Field(default="", description="Original plan summary")
    research_findings: List[Dict[str, Any]] = Field(default_factory=list, description="Findings collected by research branches")
    analysis_insights: List[str] = Field(default_factory=list, description="Analytical insights and tradeoffs")
    review_decision: str = Field(default="PASS", description="Audit verdict from Reviewer: 'PASS', 'FAIL', 'REQUIRES_REVISION'")
    review_issues: List[str] = Field(default_factory=list, description="Issues raised by reviewer if any")
    target_format: str = Field(default="markdown", description="'markdown', 'json', 'executive_brief'")
    context: Dict[str, Any] = Field(default_factory=dict, description="Supplementary context parameters")


class SynthesisOutput(BaseModel):
    """Structured final deliverable produced by the SynthesizerAgent."""
    title: str = Field(..., description="Document or report title")
    executive_summary: str = Field(..., description="High-level synthesis of findings and recommendations")
    key_conclusions: List[str] = Field(..., min_length=1, description="Actionable summary takeaways")
    detailed_report: str = Field(..., description="Full comprehensive synthesized deliverable")
    review_acknowledgment: str = Field(..., description="Statement reflecting review status and unresolved caveats")


class SynthesizerAgent(AbstractAgent):
    """
    Specialized agent responsible for assembling all multi-branch findings, analyses,
    and audit evaluations into an integrated final deliverable.
    """

    def __init__(self, model_provider: ModelProvider):
        super().__init__(model_provider)
        self._metadata = AgentMetadata(
            agent_id="synthesizer_agent",
            name="Executive Synthesizer",
            version="1.0.0",
            description="Aggregates and synthesizes multi-branch research, analysis, and reviews into a cohesive deliverable.",
            capabilities=[AgentCapability.SYNTHESIS],
            system_instruction=(
                "You are an expert Executive Synthesizer. Your responsibility is to integrate multiple upstream "
                "data streams (research findings, comparative analysis, review audits) into an authoritative, "
                "well-structured deliverable. If the audit review indicates FAIL or REQUIRES_REVISION, you must "
                "explicitly incorporate those warnings in the review_acknowledgment section. Never ignore upstream defects."
            ),
            default_model="gemini-2.5-flash",
            temperature=0.2,
        )

    @property
    def metadata(self) -> AgentMetadata:
        return self._metadata

    @property
    def input_schema(self) -> Type[BaseModel]:
        return SynthesisInput

    @property
    def output_schema(self) -> Type[BaseModel]:
        return SynthesisOutput

    def build_prompt(self, context: AgentExecutionContext, validated_input: BaseModel) -> str:
        inp: SynthesisInput = validated_input  # type: ignore
        findings_str = str(inp.research_findings) if inp.research_findings else "None provided."
        insights_str = "\n".join(f"- {i}" for i in inp.analysis_insights) if inp.analysis_insights else "None."
        review_issues_str = "\n".join(f"- {iss}" for iss in inp.review_issues) if inp.review_issues else "None."

        return (
            f"Plan Summary:\n{inp.planner_summary}\n\n"
            f"Research Findings:\n{findings_str}\n\n"
            f"Analysis Insights:\n{insights_str}\n\n"
            f"Review Audit Status: {inp.review_decision}\n"
            f"Review Issues:\n{review_issues_str}\n\n"
            f"Target Format: {inp.target_format}\n\n"
            "Synthesize these components into a comprehensive final deliverable matching the SynthesisOutput schema."
        )

    def produce_artifacts(self, output: BaseModel, context: AgentExecutionContext) -> List[ProducedArtifact]:
        syn: SynthesisOutput = output  # type: ignore
        import hashlib
        import json
        content = json.dumps(syn.model_dump(), sort_keys=True)
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return [
            ProducedArtifact(
                name="final_synthesis.json",
                artifact_type="json",
                content_or_uri=content,
                checksum_sha256=checksum,
                metadata={"title": syn.title, "review_status": context.input_payload.get("review_decision", "PASS")},
            )
        ]
