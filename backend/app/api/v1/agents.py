"""API endpoints for Specialized Agent discovery and contract inspection."""

from fastapi import APIRouter, Depends

from ..dependencies import get_system_service
from ...services.system_service import SystemService
from ..schemas.agent import AgentSummaryResponse, AgentListResponse

agents_router = APIRouter(prefix="/agents", tags=["Agents"])


@agents_router.get(
    "",
    response_model=AgentListResponse,
    summary="List registered specialized agents",
)
async def list_agents(
    service: SystemService = Depends(get_system_service),
) -> AgentListResponse:
    """Lists all available specialized agents with their capability tags and contracts."""
    items = service.list_agents()
    return AgentListResponse(items=items, total_count=len(items))


@agents_router.get(
    "/{agent_id}",
    response_model=AgentSummaryResponse,
    summary="Retrieve agent specification and contracts",
)
async def get_agent(
    agent_id: str,
    service: SystemService = Depends(get_system_service),
) -> AgentSummaryResponse:
    """Retrieves full specification, input schema, and output schema for an agent."""
    return service.get_agent(agent_id)
