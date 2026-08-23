"""BaseAgent abstract runner implementing the domain BaseAgent protocol."""

from abc import ABC, abstractmethod
import time
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, ValidationError

from ..domain.interfaces.agent import BaseAgent
from ..domain.interfaces.model_provider import ModelProvider
from ..domain.models.agent import (
    AgentExecutionContext,
    AgentMetadata,
    AgentResult,
    ProducedArtifact,
    TokenUsageMetrics,
)
from ..domain.models.failure import FailureCategory
from ..core.exceptions import SchemaValidationError


class AbstractAgent(ABC):
    """
    Abstract base class providing standard execution, contract validation,
    latency tracking, and failure normalization for all specialized agents.
    """

    def __init__(self, model_provider: ModelProvider):
        self.model_provider = model_provider

    @property
    @abstractmethod
    def metadata(self) -> AgentMetadata:
        """Returns metadata defining this agent."""
        ...

    @property
    @abstractmethod
    def input_schema(self) -> Type[BaseModel]:
        """Pydantic schema defining required input payload."""
        ...

    @property
    @abstractmethod
    def output_schema(self) -> Type[BaseModel]:
        """Pydantic schema defining structured output payload."""
        ...

    @abstractmethod
    def build_prompt(self, context: AgentExecutionContext, validated_input: BaseModel) -> str:
        """Constructs the prompt sent to the model provider using input and scoped context."""
        ...

    def produce_artifacts(
        self,
        output: BaseModel,
        context: AgentExecutionContext,
    ) -> List[ProducedArtifact]:
        """Optional hook for agents to emit structured artifacts downstream. Defaults to empty list."""
        return []

    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        """
        Executes the agent's reasoning cycle with strict contract enforcement:
        1. Validate input_payload against input_schema.
        2. Format prompt via build_prompt.
        3. Call model_provider.generate_structured.
        4. Validate output and generate artifacts.
        5. Return standardized AgentResult with latency and token metrics.
        """
        start_time = time.perf_counter()

        # Step 1: Validate input payload
        try:
            validated_input = self.input_schema.model_validate(context.input_payload)
        except ValidationError as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return AgentResult(
                success=False,
                error_message=f"Input contract validation failed for agent '{self.metadata.agent_id}': {exc}",
                error_category=FailureCategory.CONTRACT_VALIDATION_FAILURE.value,
                execution_duration_ms=duration_ms,
            )

        # Step 2: Build prompt
        prompt = self.build_prompt(context, validated_input)

        # Step 3: Invoke model provider
        try:
            output_model, token_metrics = await self.model_provider.generate_structured(
                prompt=prompt,
                system_instruction=self.metadata.system_instruction,
                response_schema=self.output_schema,
                temperature=self.metadata.temperature,
                timeout_seconds=float(context.timeout_seconds),
            )
        except SchemaValidationError as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return AgentResult(
                success=False,
                error_message=str(exc),
                error_category=FailureCategory.CONTRACT_VALIDATION_FAILURE.value,
                execution_duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return AgentResult(
                success=False,
                error_message=f"Agent '{self.metadata.agent_id}' execution failed: {exc}",
                error_category=FailureCategory.INFRASTRUCTURE_PROVIDER_FAILURE.value,
                execution_duration_ms=duration_ms,
            )

        # Step 4: Produce artifacts
        artifacts = self.produce_artifacts(output_model, context)
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Step 5: Return successful AgentResult
        return AgentResult(
            success=True,
            structured_data=output_model.model_dump(),
            artifacts=artifacts,
            execution_duration_ms=duration_ms,
            token_metrics=token_metrics,
            metadata={
                "agent_id": self.metadata.agent_id,
                "version": self.metadata.version,
            },
        )
