"""FastAPI dependency injection providers for database, repositories, and domain services."""

from typing import AsyncGenerator, TYPE_CHECKING
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from ..services.workflow_service import WorkflowService
    from ..services.execution_service import ExecutionService
    from ..services.system_service import SystemService

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


def get_agent_registry(
    provider: ModelProvider = Depends(get_model_provider),
) -> AgentRegistry:
    """Provides AgentRegistry initialized with all 5 specialized agents bound to model provider."""
    registry = AgentRegistry()
    registry.register(PlannerAgent(model_provider=provider))
    registry.register(ResearcherAgent(model_provider=provider))
    registry.register(AnalystAgent(model_provider=provider))
    registry.register(ReviewerAgent(model_provider=provider))
    registry.register(SynthesizerAgent(model_provider=provider))
    return registry


def get_evaluator(
    provider: ModelProvider = Depends(get_model_provider),
) -> EvaluationProvider:
    """Provides CompositeQualityEvaluator combining Layer 1 deterministic & Layer 2 LLM judge."""
    return CompositeQualityEvaluator(model_provider=provider)


def get_workflow_service(
    workflow_repo: WorkflowRepository = Depends(get_workflow_repo),
) -> "WorkflowService":
    """Provides WorkflowService bound to request repository."""
    from ..services.workflow_service import WorkflowService
    return WorkflowService(workflow_repo=workflow_repo)


def get_execution_service(
    workflow_repo: WorkflowRepository = Depends(get_workflow_repo),
    execution_repo: ExecutionRepository = Depends(get_execution_repo),
    event_repo: EventRepository = Depends(get_event_repo),
    artifact_repo: ArtifactRepository = Depends(get_artifact_repo),
    registry: AgentRegistry = Depends(get_agent_registry),
    evaluator: EvaluationProvider = Depends(get_evaluator),
) -> "ExecutionService":
    """Provides ExecutionService with instantiated WorkflowExecutionEngine."""
    from ..services.execution_service import ExecutionService
    from ..orchestration.execution_engine import WorkflowExecutionEngine

    engine = WorkflowExecutionEngine(
        workflow_repo=workflow_repo,
        execution_repo=execution_repo,
        event_repo=event_repo,
        artifact_repo=artifact_repo,
        agent_registry=registry,
        evaluator=evaluator,
    )
    return ExecutionService(
        workflow_repo=workflow_repo,
        execution_repo=execution_repo,
        event_repo=event_repo,
        artifact_repo=artifact_repo,
        engine=engine,
    )


def get_system_service(
    registry: AgentRegistry = Depends(get_agent_registry),
) -> "SystemService":
    """Provides SystemService bound to singleton AgentRegistry."""
    from ..services.system_service import SystemService
    return SystemService(registry=registry)

