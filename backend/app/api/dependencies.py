"""FastAPI dependency injection providers for database, repositories, and domain services."""

from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..domain.interfaces.repository import (
    WorkflowRepository,
    ExecutionRepository,
    EventRepository,
    ArtifactRepository,
)
from ..domain.interfaces.model_provider import ModelProvider
from ..domain.interfaces.evaluation_provider import EvaluationProvider
from ..persistence.database import async_session_factory
from ..persistence.repositories import (
    SqlWorkflowRepository,
    SqlExecutionRepository,
    SqlEventRepository,
    SqlArtifactRepository,
)
from ..agents.registry import AgentRegistry
from ..agents.builtins import (
    PlannerAgent,
    ResearcherAgent,
    AnalystAgent,
    ReviewerAgent,
    SynthesizerAgent,
)
from ..providers.gemini import GeminiModelProvider
from ..evaluators.composite import CompositeQualityEvaluator

# Global singleton instances for agent registry and model provider
_global_registry: AgentRegistry | None = None
_global_provider: ModelProvider | None = None
_global_evaluator: EvaluationProvider | None = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields a managed async database session for the request lifecycle."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_workflow_repo(session: AsyncSession = Depends(get_db_session)) -> WorkflowRepository:
    """Provides workflow repository instance bound to request DB session."""
    return SqlWorkflowRepository(session)


def get_execution_repo(session: AsyncSession = Depends(get_db_session)) -> ExecutionRepository:
    """Provides execution repository instance bound to request DB session."""
    return SqlExecutionRepository(session)


def get_event_repo(session: AsyncSession = Depends(get_db_session)) -> EventRepository:
    """Provides audit event repository instance bound to request DB session."""
    return SqlEventRepository(session)


def get_artifact_repo(session: AsyncSession = Depends(get_db_session)) -> ArtifactRepository:
    """Provides artifact repository instance bound to request DB session."""
    return SqlArtifactRepository(session)


def get_model_provider() -> ModelProvider:
    """Provides singleton ModelProvider instance."""
    global _global_provider
    if _global_provider is None:
        _global_provider = GeminiModelProvider(api_key=settings.GEMINI_API_KEY)
    return _global_provider


def get_agent_registry() -> AgentRegistry:
    """Provides singleton AgentRegistry initialized with all 5 specialized agents."""
    global _global_registry
    if _global_registry is None:
        registry = AgentRegistry()
        provider = get_model_provider()
        registry.register(PlannerAgent(model_provider=provider))
        registry.register(ResearcherAgent(model_provider=provider))
        registry.register(AnalystAgent(model_provider=provider))
        registry.register(ReviewerAgent(model_provider=provider))
        registry.register(SynthesizerAgent(model_provider=provider))
        _global_registry = registry
    return _global_registry


def get_evaluator() -> EvaluationProvider:
    """Provides CompositeQualityEvaluator combining Layer 1 deterministic & Layer 2 LLM judge."""
    global _global_evaluator
    if _global_evaluator is None:
        provider = get_model_provider()
        _global_evaluator = CompositeQualityEvaluator(model_provider=provider)
    return _global_evaluator
