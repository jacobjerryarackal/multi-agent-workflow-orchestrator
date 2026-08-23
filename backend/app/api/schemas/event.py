"""API response schemas for Workflow audit events."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class EventResponse(BaseModel):
    id: str
    workflow_execution_id: str
    task_execution_id: Optional[str] = None
    task_key: Optional[str] = None
    event_type: str
    actor: str = "system"
    payload: Dict[str, Any]
    timestamp: datetime


class EventListResponse(BaseModel):
    items: List[EventResponse]
    total_count: int
