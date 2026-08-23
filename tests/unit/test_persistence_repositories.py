"""Unit tests for SQLAlchemy repositories using async in-memory database."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.persistence.database import Base
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


@pytest_asyncio.fixture
async def async_db_session():
    """Provides an isolated in-memory SQLite database session for repository testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_workflow_repository_save_and_retrieve(async_db_session: AsyncSession):
    repo = SqlWorkflowRepository(async_db_session)
    
    task_spec = TaskSpec(
        task_key="planner_node",
        name="Planner",
        agent_id="planner_agent",
        depends_on=[],
        timeout_seconds=45,
    )
    workflow_spec = WorkflowSpec(
        name="research_pipeline",
        version=1,
        description="Research pipeline workflow",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        tasks=[task_spec],
    )

    # Save
    saved = await repo.save_workflow_spec(workflow_spec)
    await async_db_session.commit()
    assert saved.id == workflow_spec.id

    # Retrieve
    retrieved = await repo.get_workflow_spec(workflow_spec.id)
    assert retrieved is not None
    assert retrieved.name == "research_pipeline"
    assert len(retrieved.tasks) == 1
    assert retrieved.tasks[0].task_key == "planner_node"

    # List
    all_specs = await repo.list_workflow_specs()
    assert len(all_specs) >= 1
    assert any(s.id == workflow_spec.id for s in all_specs)


@pytest.mark.asyncio
async def test_execution_repository_create_and_update(async_db_session: AsyncSession):
    wf_repo = SqlWorkflowRepository(async_db_session)
    exec_repo = SqlExecutionRepository(async_db_session)

    # Create parent workflow
    wf_spec = WorkflowSpec(
        name="exec_test_wf",
        version=1,
        description="Execution Test",
        input_schema={},
        output_schema={},
        tasks=[TaskSpec(task_key="task_1", name="Task 1", agent_id="agent_1")],
    )
    await wf_repo.save_workflow_spec(wf_spec)
    await async_db_session.commit()

    # Create workflow execution
    wf_exec = WorkflowExecution(
        workflow_id=wf_spec.id,
        status=WorkflowExecutionStatus.QUEUED,
        initial_inputs={"query": "test query"},
    )
    saved_exec = await exec_repo.create_workflow_execution(wf_exec)
    await async_db_session.commit()
    assert saved_exec.id == wf_exec.id

    # Retrieve
    retrieved = await exec_repo.get_workflow_execution(wf_exec.id)
    assert retrieved is not None
    assert retrieved.status == WorkflowExecutionStatus.QUEUED
    assert retrieved.initial_inputs["query"] == "test query"

    # Update execution status
    retrieved.status = WorkflowExecutionStatus.RUNNING
    retrieved.final_outputs = {"answer": "synthesized"}
    updated = await exec_repo.update_workflow_execution(retrieved)
    await async_db_session.commit()
    assert updated.status == WorkflowExecutionStatus.RUNNING
    assert updated.final_outputs["answer"] == "synthesized"

    # Update / create task execution
    task_exec = TaskExecution(
        workflow_execution_id=wf_exec.id,
        task_key="task_1",
        agent_id="agent_1",
        status=TaskExecutionStatus.RUNNING,
        attempt_count=1,
        input_data={"param": 10},
    )
    saved_task = await exec_repo.update_task_execution(task_exec)
    await async_db_session.commit()
    assert saved_task.task_key == "task_1"
    assert saved_task.attempt_count == 1


@pytest.mark.asyncio
async def test_event_repository_append_and_list(async_db_session: AsyncSession):
    wf_repo = SqlWorkflowRepository(async_db_session)
    exec_repo = SqlExecutionRepository(async_db_session)
    event_repo = SqlEventRepository(async_db_session)

    wf = await wf_repo.save_workflow_spec(WorkflowSpec(
        name="event_wf", version=1, description="Event", input_schema={}, output_schema={},
        tasks=[TaskSpec(task_key="t1", name="T1", agent_id="a1")]
    ))
    wf_exec = await exec_repo.create_workflow_execution(WorkflowExecution(
        workflow_id=wf.id, status=WorkflowExecutionStatus.RUNNING
    ))
    await async_db_session.commit()

    evt1 = WorkflowEvent(
        workflow_execution_id=wf_exec.id,
        workflow_id=wf.id,
        task_key="t1",
        event_type=EventType.TASK_STARTED,
        payload={"msg": "started"},
    )
    evt2 = WorkflowEvent(
        workflow_execution_id=wf_exec.id,
        workflow_id=wf.id,
        task_key="t1",
        event_type=EventType.TASK_COMPLETED,
        payload={"msg": "completed"},
    )

    await event_repo.append_event(evt1)
    await event_repo.append_event(evt2)
    await async_db_session.commit()

    events = await event_repo.list_events_for_execution(wf_exec.id)
    assert len(events) == 2
    assert events[0].event_type == EventType.TASK_STARTED
    assert events[1].event_type == EventType.TASK_COMPLETED


@pytest.mark.asyncio
async def test_artifact_repository_save_and_retrieve(async_db_session: AsyncSession):
    wf_repo = SqlWorkflowRepository(async_db_session)
    exec_repo = SqlExecutionRepository(async_db_session)
    artifact_repo = SqlArtifactRepository(async_db_session)

    wf = await wf_repo.save_workflow_spec(WorkflowSpec(
        name="art_wf", version=1, description="Art", input_schema={}, output_schema={},
        tasks=[TaskSpec(task_key="t1", name="T1", agent_id="a1")]
    ))
    wf_exec = await exec_repo.create_workflow_execution(WorkflowExecution(
        workflow_id=wf.id, status=WorkflowExecutionStatus.RUNNING
    ))
    await async_db_session.commit()

    artifact = Artifact.create_from_data(
        workflow_execution_id=wf_exec.id,
        task_key="t1",
        name="analysis_report.json",
        data={"metrics": [1, 2, 3], "summary": "passed"},
        artifact_type=ArtifactType.JSON,
    )

    saved_art = await artifact_repo.save_artifact(artifact)
    await async_db_session.commit()
    assert saved_art.id == artifact.id

    retrieved = await artifact_repo.get_artifact(artifact.id)
    assert retrieved is not None
    assert retrieved.name == "analysis_report.json"
    assert retrieved.verify_integrity() is True

    arts_list = await artifact_repo.list_artifacts_for_execution(wf_exec.id)
    assert len(arts_list) == 1
    assert arts_list[0].id == artifact.id
