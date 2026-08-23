"""Researcher specialized agent for structured investigation and evidence synthesis."""

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


class ResearchFinding(BaseModel):
    """An individual research finding with confidence and citations."""
    topic: str = Field(..., description="The thematic topic of the finding")
    detail: str = Field(..., description="Detailed factual explanation and evidence")
    sources_cited: List[str] = Field(default_factory=list, description="References, documents, or data sources cited")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0, description="Confidence score in finding accuracy")


class ResearchInput(BaseModel):
    """Input payload accepted by the ResearcherAgent."""
    objective: str = Field(..., description="Core subject or question to research")
    questions: List[str] = Field(default_factory=list, description="Specific sub-questions to investigate")
    scope: str = Field(default="general", description="Inquiry scope: 'brief', 'technical', 'market', 'exhaustive'")
    context: Dict[str, Any] = Field(default_factory=dict, description="Context from upstream tasks or domain")


class ResearchOutput(BaseModel):
    """Structured research findings produced by the ResearcherAgent."""
    findings: List[ResearchFinding] = Field(..., min_length=1, description="List of structured factual findings")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made during research")
    uncertainties: List[str] = Field(default_factory=list, description="Known gaps or areas of uncertainty")
    recommended_follow_up: List[str] = Field(default_factory=list, description="Recommended downstream investigations")


class ResearcherAgent(AbstractAgent):
    """
    Specialized agent responsible for structured investigation, evidence gathering,
    and factual inquiry.
    """

    def __init__(self, model_provider: ModelProvider):
        super().__init__(model_provider)
        self._metadata = AgentMetadata(
            agent_id="researcher_agent",
            name="Research Specialist",
            version="1.0.0",
            description="Conducts multi-perspective research and structures verifiable findings.",
            capabilities=[AgentCapability.RESEARCH],
            system_instruction=(
                "You are an expert Research Specialist. Your responsibility is to conduct thorough, "
                "objective investigation based on provided questions and context. You must clearly "
                "distinguish verified findings from assumptions and uncertainties. Never present "
                "unsupported conjecture as fact."
            ),
            default_model="gemini-2.5-flash",
            temperature=0.2,
        )

    @property
    def metadata(self) -> AgentMetadata:
        return self._metadata

    @property
    def input_schema(self) -> Type[BaseModel]:
        return ResearchInput

    @property
    def output_schema(self) -> Type[BaseModel]:
        return ResearchOutput

    def build_prompt(self, context: AgentExecutionContext, validated_input: BaseModel) -> str:
        inp: ResearchInput = validated_input  # type: ignore
        questions_str = "\n".join(f"- {q}" for q in inp.questions) if inp.questions else "Analyze the main objective."
        return (
            f"Research Objective:\n{inp.objective}\n\n"
            f"Scope: {inp.scope}\n\n"
            f"Specific Inquiries:\n{questions_str}\n\n"
            f"Context & Upstream Data:\n{inp.context}\n\n"
            "Produce structured findings matching the ResearchOutput schema."
        )

    def produce_artifacts(self, output: BaseModel, context: AgentExecutionContext) -> List[ProducedArtifact]:
        res: ResearchOutput = output  # type: ignore
        import hashlib
        import json
        content = json.dumps(res.model_dump(), sort_keys=True)
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return [
            ProducedArtifact(
                name="research_findings.json",
                artifact_type="json",
                content_or_uri=content,
                checksum_sha256=checksum,
                metadata={"findings_count": len(res.findings)},
            )
        ]
