"""Abstract interface protocol for all specialized agents."""

from typing import Protocol, Type
from pydantic import BaseModel
from ..models.agent import AgentExecutionContext, AgentMetadata, AgentResult


class BaseAgent(Protocol):
    """Protocol defining the required interface for all specialized agents."""

    @property
    def metadata(self) -> AgentMetadata:
        """Returns the static metadata defining this agent."""
        ...

    @property
    def input_schema(self) -> Type[BaseModel]:
        """Returns the Pydantic schema model defining this agent's required input payload."""
        ...

    @property
    def output_schema(self) -> Type[BaseModel]:
        """Returns the Pydantic schema model defining this agent's structured output payload."""
        ...

    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        """Executes the agent's core task logic asynchronously within the supplied execution context."""
        ...
