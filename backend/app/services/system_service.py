"""Application service for System inspection and Agent discovery."""

from typing import List
from ..agents.registry import AgentRegistry
from ..core.exceptions import AgentNotFoundError
from ..api.schemas.agent import AgentSummaryResponse


class SystemService:
    """Provides system discovery and registered agent capabilities."""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    def list_agents(self) -> List[AgentSummaryResponse]:
        """Lists all registered built-in and dynamic specialized agents with JSON schemas."""
        results = []
        for agent in self.registry._agents.values():
            meta = agent.metadata
            input_schema = (
                agent.input_schema.model_json_schema()
                if hasattr(agent, "input_schema")
                else {}
            )
            output_schema = (
                agent.output_schema.model_json_schema()
                if hasattr(agent, "output_schema")
                else {}
            )
            results.append(
                AgentSummaryResponse(
                    agent_id=meta.agent_id,
                    name=meta.name,
                    description=meta.description,
                    version=meta.version,
                    capabilities=[
                        c.value if hasattr(c, "value") else str(c)
                        for c in meta.capabilities
                    ],
                    input_schema=input_schema,
                    output_schema=output_schema,
                )
            )
        return results

    def get_agent(self, agent_id: str) -> AgentSummaryResponse:
        """Retrieves metadata and input/output contracts for a specific agent."""
        if not self.registry.has(agent_id):
            raise AgentNotFoundError(f"Specialized Agent '{agent_id}' is not registered in system.")
        agent = self.registry.get(agent_id)
        meta = agent.metadata
        input_schema = (
            agent.input_schema.model_json_schema()
            if hasattr(agent, "input_schema")
            else {}
        )
        output_schema = (
            agent.output_schema.model_json_schema()
            if hasattr(agent, "output_schema")
            else {}
        )
        return AgentSummaryResponse(
            agent_id=meta.agent_id,
            name=meta.name,
            description=meta.description,
            version=meta.version,
            capabilities=[
                c.value if hasattr(c, "value") else str(c)
                for c in meta.capabilities
            ],
            input_schema=input_schema,
            output_schema=output_schema,
        )
