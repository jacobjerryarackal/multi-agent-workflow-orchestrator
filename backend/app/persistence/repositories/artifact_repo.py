"""SQLAlchemy repository implementation for Artifacts."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...domain.models.artifact import Artifact
from ...domain.interfaces.repository import ArtifactRepository
from ..models import ArtifactModel


class SqlArtifactRepository(ArtifactRepository):
    """PostgreSQL/SQLAlchemy implementation of ArtifactRepository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_artifact(self, artifact: Artifact) -> Artifact:
        model = ArtifactModel.from_domain(artifact)
        self.session.add(model)
        await self.session.flush()
        return model.to_domain()

    async def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        stmt = select(ArtifactModel).where(ArtifactModel.id == artifact_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def list_artifacts_for_execution(self, execution_id: str) -> List[Artifact]:
        stmt = (
            select(ArtifactModel)
            .where(ArtifactModel.workflow_execution_id == execution_id)
            .order_by(ArtifactModel.created_at.asc())
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [m.to_domain() for m in models]
