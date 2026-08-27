"""Global Pytest fixtures and mock setups."""

import pytest
import pytest_asyncio
from typing import Any, Dict, Type, Tuple
from pydantic import BaseModel
from app.domain.models import (
    WorkflowSpec,
    TaskSpec,
    AgentMetadata,
    AgentCapability,
    TokenUsageMetrics,
)
from app.domain.interfaces import ModelProvider


class MockModelProvider:
    """Deterministic, zero-cost mock model provider for unit tests."""

    def __init__(self, canned_responses: Dict[str, Any] | None = None):
        self.canned_responses = canned_responses or {}
        self.call_history: list[Dict[str, Any]] = []

    async def generate_structured(
        self,
        prompt: str,
        system_instruction: str,
        response_schema: Type[BaseModel],
        temperature: float = 0.2,
        timeout_seconds: float = 60.0,
    ) -> Tuple[BaseModel, TokenUsageMetrics]:
        self.call_history.append({
            "prompt": prompt,
            "system_instruction": system_instruction,
            "schema_name": response_schema.__name__,
        })
        schema_name = response_schema.__name__
        if schema_name in self.canned_responses:
            data = self.canned_responses[schema_name]
            instance = response_schema.model_validate(data)
            metrics = TokenUsageMetrics(prompt_tokens=40, completion_tokens=60, total_tokens=100)
            return instance, metrics

        # Fallback dummy instance
        try:
            return response_schema(), TokenUsageMetrics(prompt_tokens=10, completion_tokens=10, total_tokens=20)
        except Exception:
            raise ValueError(f"No mock response configured for schema {schema_name}")

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float = 0.2,
        timeout_seconds: float = 60.0,
    ) -> Tuple[str, TokenUsageMetrics]:
        self.call_history.append({"prompt": prompt, "system_instruction": system_instruction})
        return "Mock generated text response", TokenUsageMetrics(prompt_tokens=20, completion_tokens=20, total_tokens=40)


@pytest.fixture
def mock_model_provider() -> MockModelProvider:
    return MockModelProvider()


@pytest.fixture
def sample_task_spec() -> TaskSpec:
    return TaskSpec(
        task_key="test_task",
        name="Test Task",
        agent_id="planner_agent",
        depends_on=[],
        timeout_seconds=30,
    )


@pytest.fixture
def sample_workflow_spec(sample_task_spec: TaskSpec) -> WorkflowSpec:
    return WorkflowSpec(
        name="sample_workflow",
        version=1,
        description="Sample test workflow",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
        tasks=[sample_task_spec],
    )


@pytest_asyncio.fixture
async def db_session():
    """Provides an isolated in-memory SQLite database session for unit and engine tests."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.pool import StaticPool
    from app.persistence.database import Base
    from app.orchestration.background_manager import get_background_manager

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    bg_manager = get_background_manager()
    bg_manager._shutdown_event.clear()
    old_factory = bg_manager._session_factory
    bg_manager._session_factory = session_factory

    async with session_factory() as session:
        yield session

    bg_manager._session_factory = old_factory
    bg_manager._shutdown_event.clear()
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def ensure_postgres_schema_migrated():
    """Ensures that the PostgreSQL test database is migrated to Alembic head before test execution."""
    import subprocess
    try:
        subprocess.run(["alembic", "upgrade", "head"], cwd="backend", capture_output=True, check=False)
    except Exception:
        pass

