"""Unit tests for AbstractAgent base runner behaviors."""

import pytest
from pydantic import BaseModel, Field
from app.agents.base import AbstractAgent
from app.domain.models import (
    AgentCapability,
    AgentExecutionContext,
    AgentMetadata,
    ProducedArtifact,
)
from app.domain.models.failure import FailureCategory
from tests.conftest import MockModelProvider


class DummyInput(BaseModel):
    query: str = Field(..., min_length=3)


class DummyOutput(BaseModel):
    answer: str


class DummyAgent(AbstractAgent):
    def __init__(self, model_provider):
        super().__init__(model_provider)
        self._metadata = AgentMetadata(
            agent_id="dummy_agent",
            name="Dummy Agent",
            version="1.0.0",
            description="Dummy for testing base runner",
            capabilities=[AgentCapability.TRANSFORMATION],
            system_instruction="You are dummy.",
        )

    @property
    def metadata(self) -> AgentMetadata:
        return self._metadata

    @property
    def input_schema(self):
        return DummyInput

    @property
    def output_schema(self):
        return DummyOutput

    def build_prompt(self, context, validated_input):
        inp: DummyInput = validated_input  # type: ignore
        return f"Prompt for: {inp.query}"

    def produce_artifacts(self, output, context):
        return [
            ProducedArtifact(
                name="dummy_artifact.txt",
                artifact_type="text",
                content_or_uri="artifact content",
                checksum_sha256="dummyhash",
            )
        ]


@pytest.mark.asyncio
async def test_abstract_agent_successful_execution():
    mock_provider = MockModelProvider(
        canned_responses={"DummyOutput": {"answer": "processed answer"}}
    )
    agent = DummyAgent(mock_provider)
    context = AgentExecutionContext(
        workflow_execution_id="exec-1",
        workflow_id="wf-1",
        task_key="dummy_task",
        input_payload={"query": "valid query"},
    )

    result = await agent.execute(context)
    assert result.success is True
    assert result.structured_data["answer"] == "processed answer"
    assert len(result.artifacts) == 1
    assert result.artifacts[0].name == "dummy_artifact.txt"
    assert result.token_metrics.total_tokens == 100
    assert result.execution_duration_ms >= 0


@pytest.mark.asyncio
async def test_abstract_agent_input_validation_failure():
    mock_provider = MockModelProvider()
    agent = DummyAgent(mock_provider)
    
    # Missing required 'query'
    context = AgentExecutionContext(
        workflow_execution_id="exec-1",
        workflow_id="wf-1",
        task_key="dummy_task",
        input_payload={},
    )

    result = await agent.execute(context)
    assert result.success is False
    assert "Input contract validation failed" in (result.error_message or "")
    assert result.error_category == FailureCategory.CONTRACT_VALIDATION_FAILURE.value
