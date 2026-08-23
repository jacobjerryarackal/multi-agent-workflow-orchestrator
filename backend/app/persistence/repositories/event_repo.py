"""SQLAlchemy repository implementation for Workflow Events."""

from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...domain.models.event import WorkflowEvent
from ...domain.interfaces.repository import EventRepository
from ..models import WorkflowEventModel


class SqlEventRepository(EventRepository):
    """PostgreSQL/SQLAlchemy implementation of EventRepository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def append_event(self, event: WorkflowEvent) -> WorkflowEvent:
        model = WorkflowEventModel.from_domain(event)
        self.session.add(model)
        await self.session.flush()
        return model.to_domain()

    async def list_events_for_execution(self, execution_id: str) -> List[WorkflowEvent]:
        stmt = (
            select(WorkflowEventModel)
            .where(WorkflowEventModel.workflow_execution_id == execution_id)
            .order_by(WorkflowEventModel.timestamp.asc())
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [m.to_domain() for m in models]
