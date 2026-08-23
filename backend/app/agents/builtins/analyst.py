"""Analyst specialized agent for comparative evaluation, tradeoff analysis, and reasoning."""

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


class Tradeoff(BaseModel):
    """An evaluated option with pros, cons, and normalized impact score."""
    option_name: str = Field(..., description="Name of option or architectural path")
    pros: List[str] = Field(..., min_length=1, description="Advantages and positive impacts")
    cons: List[str] = Field(..., min_length=1, description="Disadvantages and costs/risks")
    impact_score: float = Field(default=0.8, ge=0.0, le=1.0, description="Overall viability score (0.0 to 1.0)")


class AnalysisInput(BaseModel):
    """Input payload accepted by the AnalystAgent."""
    research_findings: List[Dict[str, Any]] = Field(..., min_length=1, description="Data points and research findings to analyze")
    evaluation_criteria: List[str] = Field(default_factory=list, description="Criteria against which to evaluate options")
    context: Dict[str, Any] = Field(default_factory=dict, description="Operational constraints or business goals")


class AnalysisOutput(BaseModel):
    """Structured analytical conclusions produced by the AnalystAgent."""
    insights: List[str] = Field(..., min_length=1, description="Key analytical insights derived from data")
    tradeoffs: List[Tradeoff] = Field(default_factory=list, description="Comparative tradeoffs across evaluated alternatives")
    conclusions: List[str] = Field(..., min_length=1, description="Definitive conclusions and recommendations")
    confidence_score: float = Field(default=0.85, ge=0.0, le=1.0, description="Confidence in analytical assessment")


class AnalystAgent(AbstractAgent):
    """
    Specialized agent responsible for deep qualitative and quantitative reasoning,
    tradeoff modeling, and strategic deductions.
    """

    def __init__(self, model_provider: ModelProvider):
        super().__init__(model_provider)
        self._metadata = AgentMetadata(
            agent_id="analyst_agent",
            name="Data & Systems Analyst",
            version="1.0.0",
            description="Consumes research findings and performs deep comparative analysis and tradeoff modeling.",
            capabilities=[AgentCapability.DATA_ANALYSIS],
            system_instruction=(
                "You are an expert Systems and Strategic Analyst. Your responsibility is to analyze "
                "data points, identify underlying patterns, evaluate comparative tradeoffs, and derive "
                "evidence-backed conclusions. You must return valid JSON matching the AnalysisOutput schema."
            ),
            default_model="gemini-2.5-flash",
            temperature=0.2,
        )

    @property
    def metadata(self) -> AgentMetadata:
        return self._metadata

    @property
    def input_schema(self) -> Type[BaseModel]:
        return AnalysisInput

    @property
    def output_schema(self) -> Type[BaseModel]:
        return AnalysisOutput

    def build_prompt(self, context: AgentExecutionContext, validated_input: BaseModel) -> str:
        inp: AnalysisInput = validated_input  # type: ignore
        criteria_str = "\n".join(f"- {c}" for c in inp.evaluation_criteria) if inp.evaluation_criteria else "Evaluate feasibility, reliability, and cost."
        return (
            f"Research Findings to Analyze:\n{inp.research_findings}\n\n"
            f"Evaluation Criteria:\n{criteria_str}\n\n"
            f"Context Constraints:\n{inp.context}\n\n"
            "Perform rigorous analysis and generate structured insights, tradeoffs, and recommendations."
        )

    def produce_artifacts(self, output: BaseModel, context: AgentExecutionContext) -> List[ProducedArtifact]:
        analysis: AnalysisOutput = output  # type: ignore
        import hashlib
        import json
        content = json.dumps(analysis.model_dump(), sort_keys=True)
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return [
            ProducedArtifact(
                name="analysis_report.json",
                artifact_type="json",
                content_or_uri=content,
                checksum_sha256=checksum,
                metadata={"tradeoff_count": len(analysis.tradeoffs), "confidence": analysis.confidence_score},
            )
        ]
