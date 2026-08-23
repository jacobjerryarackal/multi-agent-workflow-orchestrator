"""API endpoints for immutable audit telemetry events."""

from fastapi import APIRouter, Depends

from ..dependencies import get_execution_service
from ...services.execution_service import ExecutionService
from ..schemas.event import EventResponse, EventListResponse

events_router = APIRouter(prefix="/executions/{execution_id}/events", tags=["Audit Events"])


@events_router.get(
    "",
    response_model=EventListResponse,
    summary="List chronological audit events for an execution",
)
async def list_events(
    execution_id: str,
    service: ExecutionService = Depends(get_execution_service),
) -> EventListResponse:
    """Retrieves immutable audit telemetry events for an execution."""
    events = await service.list_events(execution_id)
    items = [
        EventResponse(
            id=e.id,
            workflow_execution_id=e.workflow_execution_id,
            task_execution_id=e.task_execution_id,
            task_key=e.task_key,
            event_type=e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
            actor=e.actor,
            payload=e.payload,
            timestamp=e.timestamp,
        )
        for e in events
    ]
    return EventListResponse(items=items, total_count=len(items))
