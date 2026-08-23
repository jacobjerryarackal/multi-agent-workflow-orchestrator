"""Central Agent Registry managing specialized agent discovery and capabilities."""

from typing import Dict, List, Optional
from ..domain.interfaces.agent import BaseAgent
from ..domain.models.agent import AgentCapability, AgentMetadata
from ..core.exceptions import AgentNotFoundError


class AgentRegistry:
    """
    Central repository for registering, discovering, and resolving specialized agents.
    Enforces uniqueness of agent IDs and supports capability-based lookup.
    """

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """
        Registers a specialized agent instance.
        Raises ValueError if an agent with the same ID is already registered.
        """
        agent_id = agent.metadata.agent_id
        if not agent_id or not agent_id.strip():
            raise ValueError("Agent ID cannot be empty.")
        if agent_id in self._agents:
            raise ValueError(f"Agent with ID '{agent_id}' is already registered in AgentRegistry.")
        self._agents[agent_id] = agent

    def get(self, agent_id: str) -> BaseAgent:
        """
        Retrieves a registered agent by ID.
        Raises AgentNotFoundError if the agent is not found.
        """
        if agent_id not in self._agents:
            raise AgentNotFoundError(f"Agent with ID '{agent_id}' is not registered in AgentRegistry.")
        return self._agents[agent_id]

    def has(self, agent_id: str) -> bool:
        """Returns True if the agent is registered."""
        return agent_id in self._agents

    def list_agents(self) -> List[AgentMetadata]:
        """Returns a list of metadata for all registered agents."""
        return [agent.metadata for agent in self._agents.values()]

    def get_by_capability(self, capability: AgentCapability) -> List[BaseAgent]:
        """Returns all registered agents supporting the specified capability."""
        return [
            agent for agent in self._agents.values()
            if capability in agent.metadata.capabilities
        ]

    def clear(self) -> None:
        """Clears all registered agents (primarily for test isolation)."""
        self._agents.clear()


# Global default agent registry singleton
default_agent_registry = AgentRegistry()
