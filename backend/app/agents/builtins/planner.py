"""Planner specialized agent for workflow goal decomposition and DAG task formulation."""

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


class PlannedTask(BaseModel):
    """Specification of an individual task generated in a plan."""
    task_key: str = Field(..., description="Unique alphanumeric identifier for task (e.g., 'research_market')")
    name: str = Field(..., description="Human-readable task label")
    description: str = Field(..., description="Objective and instructions for this task")
    required_capability: str = Field(..., description="Target capability (e.g., 'research', 'data_analysis', 'critique')")
    depends_on: List[str] = Field(default_factory=list, description="Keys of prerequisite tasks")
    expected_output_type: str = Field(default="json", description="Expected output format: json, markdown, text")


class PlanInput(BaseModel):
    """Input payload accepted by the PlannerAgent."""
    objective: str = Field(..., description="High-level goal or problem statement to decompose")
    constraints: List[str] = Field(default_factory=list, description="Operational boundaries or guidelines")
    context: Dict[str, Any] = Field(default_factory=dict, description="Supplementary context parameters")


class PlanOutput(BaseModel):
    """Structured plan output produced by the PlannerAgent."""
    plan_summary: str = Field(..., description="Executive summary of the execution strategy")
    sub_tasks: List[PlannedTask] = Field(..., min_length=1, description="List of decomposed DAG tasks")
    risk_factors: List[str] = Field(default_factory=list, description="Identified failure risks or unknowns")


class PlannerAgent(AbstractAgent):
    """
    Specialized agent responsible for decomposing user requests into structured,
    dependency-aware execution plans.
    """

    def __init__(self, model_provider: ModelProvider):
        super().__init__(model_provider)
        self._metadata = AgentMetadata(
            agent_id="planner_agent",
            name="Workflow Planner",
            version="1.0.0",
            description="Decomposes user objectives into ordered, dependency-aware task graphs.",
            capabilities=[AgentCapability.PLANNING],
            system_instruction=(
                "You are an expert AI Workflow Architect. Your responsibility is to analyze high-level "
                "objectives and decompose them into distinct, structured tasks with explicit dependencies. "
                "You must output valid JSON matching the PlanOutput schema. Do not execute tasks directly."
            ),
            default_model="gemini-2.5-flash",
            temperature=0.2,
        )

    @property
    def metadata(self) -> AgentMetadata:
        return self._metadata

    @property
    def input_schema(self) -> Type[BaseModel]:
        return PlanInput

    @property
    def output_schema(self) -> Type[BaseModel]:
        return PlanOutput

    def build_prompt(self, context: AgentExecutionContext, validated_input: BaseModel) -> str:
        inp: PlanInput = validated_input  # type: ignore
        constraints_str = "\n".join(f"- {c}" for c in inp.constraints) if inp.constraints else "None"
        return (
            f"Objective:\n{inp.objective}\n\n"
            f"Constraints:\n{constraints_str}\n\n"
            f"Context Variables:\n{inp.context}\n\n"
            "Produce a complete, structured decomposition plan with explicit sub_tasks and dependencies."
        )

    def produce_artifacts(self, output: BaseModel, context: AgentExecutionContext) -> List[ProducedArtifact]:
        plan: PlanOutput = output  # type: ignore
        import hashlib
        import json
        content = json.dumps(plan.model_dump(), sort_keys=True)
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return [
            ProducedArtifact(
                name="execution_plan.json",
                artifact_type="json",
                content_or_uri=content,
                checksum_sha256=checksum,
                metadata={"task_count": len(plan.sub_tasks)},
            )
        ]
