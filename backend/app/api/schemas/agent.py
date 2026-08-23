"""API response schemas for Specialized Agent inspection."""

from typing import Any, Dict, List
from pydantic import BaseModel


class AgentSummaryResponse(BaseModel):
    agent_id: str
    name: str
    description: str
    version: str
    capabilities: List[str]
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]


class AgentListResponse(BaseModel):
    items: List[AgentSummaryResponse]
    total_count: int
