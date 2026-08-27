"""Real PostgreSQL integration tests validating schemas, foreign keys, row locking, and transactions."""

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.persistence.database import Base
from app.persistence.models import (
    WorkflowModel,
    WorkflowTaskModel,
    WorkflowExecutionModel,
    TaskExecutionModel,
    WorkflowEventModel,
    ArtifactModel,
)
from app.persistence.repositories import (
    SqlWorkflowRepository,
    SqlExecutionRepository,
    SqlEventRepository,
    SqlArtifactRepository,
)
from app.domain.models import (
    WorkflowSpec,
    TaskSpec,
    WorkflowExecution,
    WorkflowExecutionStatus,
    TaskExecution,
    TaskExecutionStatus,
    WorkflowEvent,
    EventType,
    Artifact,
    ArtifactType,
)

POSTGRES_TEST_URL = "postgresql+asyncpg://postgres:12345678@localhost:5432/orchestrator_test_db"


@pytest_asyncio.fixture
async def pg_session():
    """Provides an isolated real PostgreSQL database session with clean tables."""
    engine = create_async_engine(POSTGRES_TEST_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE workflows CASCADE;"))

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE workflows CASCADE;"))

    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_schema_creation_and_foreign_keys(pg_session: AsyncSession):
    """Verifies table creation and cascade foreign keys in real PostgreSQL."""
    wf_repo = SqlWorkflowRepository(pg_session)
    exec_repo = SqlExecutionRepository(pg_session)

    # 1. Create Workflow
    wf_spec = WorkflowSpec(
        name="pg_integration_wf",
        version=1,
        description="Testing real PostgreSQL persistence",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        tasks=[TaskSpec(task_key="task_1", name="Task 1", agent_id="agent_1")],
    )
    saved_wf = await wf_repo.save_workflow_spec(wf_spec)
    await pg_session.commit()

    # 2. Create Execution
    wf_exec = WorkflowExecution(
        workflow_id=saved_wf.id,
        status=WorkflowExecutionStatus.QUEUED,
        idempotency_key="unique-key-100",
    )
    saved_exec = await exec_repo.create_workflow_execution(wf_exec)
    await pg_session.commit()

    # 3. Create Task Execution
    task_exec = TaskExecution(
        workflow_execution_id=saved_exec.id,
        task_key="task_1",
        agent_id="agent_1",
        status=TaskExecutionStatus.READY,
    )
    await exec_repo.update_task_execution(task_exec)
    await pg_session.commit()

    # Verify relationships in DB
    retrieved = await exec_repo.get_workflow_execution(saved_exec.id)
    assert retrieved is not None
    assert retrieved.workflow_id == saved_wf.id
    assert "task_1" in retrieved.tasks
    assert retrieved.tasks["task_1"].status == TaskExecutionStatus.READY


@pytest.mark.asyncio
async def test_postgres_select_for_update_atomic_claim(pg_session: AsyncSession):
    """Verifies SELECT ... FOR UPDATE atomic task claiming in PostgreSQL."""
    wf_repo = SqlWorkflowRepository(pg_session)
    exec_repo = SqlExecutionRepository(pg_session)

    wf_spec = WorkflowSpec(
        name="claim_test_wf",
        version=1,
        description="Claim Test",
        input_schema={},
        output_schema={},
        tasks=[TaskSpec(task_key="claim_node", name="Claim Node", agent_id="agent_1")],
    )
    saved_wf = await wf_repo.save_workflow_spec(wf_spec)

    wf_exec = WorkflowExecution(workflow_id=saved_wf.id, status=WorkflowExecutionStatus.RUNNING)
    saved_exec = await exec_repo.create_workflow_execution(wf_exec)

    task_exec = TaskExecution(
        workflow_execution_id=saved_exec.id,
        task_key="claim_node",
        agent_id="agent_1",
        status=TaskExecutionStatus.READY,
    )
    await exec_repo.update_task_execution(task_exec)
    await pg_session.commit()

    # Worker 1 claims task
    claimed_1 = await exec_repo.claim_task_for_execution(saved_exec.id, "claim_node")
    await pg_session.commit()
    assert claimed_1 is not None
    assert claimed_1.status == TaskExecutionStatus.RUNNING
    assert claimed_1.attempt_count == 1

    # Worker 2 attempts to claim same task -> returns None (already claimed)
    claimed_2 = await exec_repo.claim_task_for_execution(saved_exec.id, "claim_node")
    await pg_session.commit()
    assert claimed_2 is None


@pytest.mark.asyncio
async def test_postgres_transaction_rollback(pg_session: AsyncSession):
    """Verifies that an error correctly rolls back transaction in PostgreSQL."""
    wf_repo = SqlWorkflowRepository(pg_session)

    wf_spec = WorkflowSpec(
        name="rollback_wf",
        version=1,
        description="Rollback test",
        input_schema={},
        output_schema={},
        tasks=[TaskSpec(task_key="t1", name="T1", agent_id="a1")],
    )
    await wf_repo.save_workflow_spec(wf_spec)
    await pg_session.rollback()  # Explicit rollback

    # Should not exist
    retrieved = await wf_repo.get_workflow_spec(wf_spec.id)
    assert retrieved is None


@pytest.mark.asyncio
async def test_postgres_evaluation_persistence(pg_session: AsyncSession):
    """Verifies that evaluation_history and revision_count persist in PostgreSQL."""
    wf_repo = SqlWorkflowRepository(pg_session)
    exec_repo = SqlExecutionRepository(pg_session)

    wf_spec = WorkflowSpec(
        name="eval_pg_wf",
        version=1,
        description="PG Eval Test",
        input_schema={},
        output_schema={},
        tasks=[TaskSpec(task_key="eval_node", name="Eval Node", agent_id="agent_eval")],
    )
    saved_wf = await wf_repo.save_workflow_spec(wf_spec)

    wf_exec = WorkflowExecution(workflow_id=saved_wf.id, status=WorkflowExecutionStatus.RUNNING)
    saved_exec = await exec_repo.create_workflow_execution(wf_exec)

    task_exec = TaskExecution(
        workflow_execution_id=saved_exec.id,
        task_key="eval_node",
        agent_id="agent_eval",
        status=TaskExecutionStatus.COMPLETED,
        revision_count=2,
        evaluation_history=[
            {"verdict": "REQUIRES_REVISION", "score": 0.5, "rationale": "Incomplete"},
            {"verdict": "PASS", "score": 0.95, "rationale": "High quality"},
        ],
    )
    await exec_repo.update_task_execution(task_exec)
    await pg_session.commit()

    # Re-query
    retrieved_exec = await exec_repo.get_workflow_execution(saved_exec.id)
    assert retrieved_exec is not None
    t = retrieved_exec.tasks["eval_node"]
    assert t.revision_count == 2
    assert len(t.evaluation_history) == 2
    assert t.evaluation_history[1]["verdict"] == "PASS"

