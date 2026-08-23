"""SQLAlchemy repository implementation for Workflow specifications."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from ...domain.models.workflow import WorkflowSpec
from ...domain.interfaces.repository import WorkflowRepository
from ..models import WorkflowModel


class SqlWorkflowRepository(WorkflowRepository):
    """PostgreSQL/SQLAlchemy implementation of WorkflowRepository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_workflow_spec(self, spec: WorkflowSpec) -> WorkflowSpec:
        model = WorkflowModel.from_domain(spec)
        self.session.add(model)
        await self.session.flush()
        return model.to_domain()

    async def get_workflow_spec(self, workflow_id: str) -> Optional[WorkflowSpec]:
        stmt = (
            select(WorkflowModel)
            .options(selectinload(WorkflowModel.tasks))
            .where(WorkflowModel.id == workflow_id)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def list_workflow_specs(self, limit: int = 50, offset: int = 0) -> List[WorkflowSpec]:
        stmt = (
            select(WorkflowModel)
            .options(selectinload(WorkflowModel.tasks))
            .order_by(WorkflowModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

