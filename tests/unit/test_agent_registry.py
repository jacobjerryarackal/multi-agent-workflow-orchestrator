"""Unit tests for the AgentRegistry."""

import pytest
from app.agents.registry import AgentRegistry
from app.agents.builtins import (
    PlannerAgent,
    ResearcherAgent,
    AnalystAgent,
    ReviewerAgent,
    SynthesizerAgent,
)
from app.domain.models import AgentCapability
from app.core.exceptions import AgentNotFoundError


def test_agent_registry_registration_and_lookup(mock_model_provider):
    registry = AgentRegistry()
    planner = PlannerAgent(mock_model_provider)
    
    registry.register(planner)
    assert registry.has("planner_agent") is True
    
    retrieved = registry.get("planner_agent")
    assert retrieved.metadata.agent_id == "planner_agent"
    assert retrieved.metadata.name == "Workflow Planner"


def test_agent_registry_duplicate_registration_rejected(mock_model_provider):
    registry = AgentRegistry()
    planner = PlannerAgent(mock_model_provider)
    registry.register(planner)
    
    with pytest.raises(ValueError, match="already registered"):
        registry.register(planner)


def test_agent_registry_unknown_agent_lookup_raises():
    registry = AgentRegistry()
    with pytest.raises(AgentNotFoundError, match="is not registered"):
        registry.get("non_existent_agent")


def test_agent_registry_list_and_capability_filtering(mock_model_provider):
    registry = AgentRegistry()
    registry.register(PlannerAgent(mock_model_provider))
    registry.register(ResearcherAgent(mock_model_provider))
    registry.register(AnalystAgent(mock_model_provider))
    registry.register(ReviewerAgent(mock_model_provider))
    registry.register(SynthesizerAgent(mock_model_provider))

    # List all
    agents_list = registry.list_agents()
    assert len(agents_list) == 5

    # Capability filter
    planners = registry.get_by_capability(AgentCapability.PLANNING)
    assert len(planners) == 1
    assert planners[0].metadata.agent_id == "planner_agent"

    researchers = registry.get_by_capability(AgentCapability.RESEARCH)
    assert len(researchers) == 1
    assert researchers[0].metadata.agent_id == "researcher_agent"

    analysts = registry.get_by_capability(AgentCapability.DATA_ANALYSIS)
    assert len(analysts) == 1
    assert analysts[0].metadata.agent_id == "analyst_agent"
