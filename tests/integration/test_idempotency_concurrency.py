"""
PostgreSQL integration tests verifying concurrent idempotency database guarantees.
Ensures simultaneous submissions with identical (workflow_id, idempotency_key) resolve to
exactly ONE logical execution without race conditions or unhandled IntegrityErrors.
"""

import asyncio
import uuid
import pytest
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.domain.models.workflow import WorkflowSpec, TaskSpec
from app.domain.models.event import EventType
from app.persistence.repositories.workflow_repo import SqlWorkflowRepository
from app.persistence.repositories.execution_repo import SqlExecutionRepository
from app.persistence.repositories.event_repo import SqlEventRepository
from app.persistence.repositories.artifact_repo import SqlArtifactRepository
from app.orchestration.execution_engine import WorkflowExecutionEngine
from app.agents.registry import AgentRegistry
from app.evaluators.deterministic import DeterministicRuleEvaluator
from app.services.execution_service import ExecutionService
from app.persistence.models import WorkflowExecutionModel, WorkflowEventModel

POSTGRES_TEST_URL = "postgresql+asyncpg://postgres:12345678@localhost:5432/orchestrator_test_db"


@pytest.mark.asyncio
async def test_concurrent_idempotency_postgres_guarantee():
    """
    Submits 5 concurrent requests with the identical (workflow_id, idempotency_key) to PostgreSQL.
    Verifies:
    1. Exactly ONE workflow_execution is created in PostgreSQL.
    2. All 5 concurrent callers return the same execution ID.
    3. Exactly ONE WORKFLOW_STARTED event is appended.
    4. No unhandled IntegrityError or 500 escapes.
    """
    engine = create_async_engine(POSTGRES_TEST_URL, echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Setup sample workflow
    workflow_id = f"wf-idemp-{uuid.uuid4().hex[:8]}"
    spec = WorkflowSpec(
        id=workflow_id,
        name=f"Concurrent Idempotency Workflow {uuid.uuid4().hex[:8]}",
        version=1,
        description="Testing concurrent idempotency",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        tasks=[
            TaskSpec(
                task_key="step_1",
                name="Step 1",
                agent_id="planner_agent",
                depends_on=[],
                timeout_seconds=30,
            )
        ],
    )

    async with session_factory() as session:
        wf_repo = SqlWorkflowRepository(session)
        await wf_repo.save_workflow_spec(spec)
        await session.commit()

    idempotency_key = f"race-key-{uuid.uuid4().hex}"

    # 2. Function simulating an incoming API request with its own dedicated DB session
    async def submit_request(caller_id: int):
        async with session_factory() as req_session:
            wf_r = SqlWorkflowRepository(req_session)
            ex_r = SqlExecutionRepository(req_session)
            ev_r = SqlEventRepository(req_session)
            ar_r = SqlArtifactRepository(req_session)
            reg = AgentRegistry()
            evl = DeterministicRuleEvaluator()
            eng = WorkflowExecutionEngine(
                workflow_repo=wf_r,
                execution_repo=ex_r,
                event_repo=ev_r,
                artifact_repo=ar_r,
                agent_registry=reg,
                evaluator=evl,  # type: ignore
            )
            svc = ExecutionService(
                workflow_repo=wf_r,
                execution_repo=ex_r,
                event_repo=ev_r,
                artifact_repo=ar_r,
                engine=eng,
            )

            # Submit without synchronous completion
            res = await svc.submit_execution(
                workflow_id=workflow_id,
                input_data={"caller": caller_id},
                idempotency_key=idempotency_key,
                run_to_completion=False,
            )
            await req_session.commit()
            return res

    # 3. Fire 5 concurrent submissions simultaneously
    results = await asyncio.gather(*[submit_request(i) for i in range(5)], return_exceptions=False)

    # 4. Verify all callers received the exact same execution ID
    assert len(results) == 5
    first_id = results[0].id
    for res in results:
        assert res.id == first_id, f"Execution ID mismatch: expected {first_id}, got {res.id}"
        assert res.idempotency_key == idempotency_key

    # 5. Verify PostgreSQL database state: exactly 1 execution record exists
    async with session_factory() as verify_session:
        count_res = await verify_session.execute(
            text(
                "SELECT COUNT(*) FROM workflow_executions WHERE workflow_id = :wid AND idempotency_key = :ikey"
            ),
            {"wid": workflow_id, "ikey": idempotency_key},
        )
        total_executions = count_res.scalar_one()
        assert total_executions == 1, f"Expected 1 execution, found {total_executions}"

        # Check event log: exactly 1 WORKFLOW_STARTED event exists for this execution
        events_res = await verify_session.execute(
            select(WorkflowEventModel).where(
                WorkflowEventModel.workflow_execution_id == first_id,
                WorkflowEventModel.event_type == EventType.WORKFLOW_STARTED.value,
            )
        )
        started_events = events_res.scalars().all()
        assert len(started_events) == 1, f"Expected 1 WORKFLOW_STARTED event, found {len(started_events)}"

    await engine.dispose()


@pytest.mark.asyncio
async def test_null_idempotency_key_allows_multiple_executions():
    """
    Submits multiple executions with idempotency_key=None.
    Verifies that the partial unique index correctly ignores NULL idempotency keys and allows distinct executions.
    """
    engine = create_async_engine(POSTGRES_TEST_URL, echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    workflow_id = f"wf-null-{uuid.uuid4().hex[:8]}"
    spec = WorkflowSpec(
        id=workflow_id,
        name=f"Null Idempotency Workflow {uuid.uuid4().hex[:8]}",
        version=1,
        description="Testing null idempotency key",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        tasks=[
            TaskSpec(
                task_key="step_1",
                name="Step 1",
                agent_id="planner_agent",
                depends_on=[],
                timeout_seconds=30,
            )
        ],
    )

    async with session_factory() as session:
        wf_repo = SqlWorkflowRepository(session)
        await wf_repo.save_workflow_spec(spec)
        await session.commit()

    async def submit_null_request():
        async with session_factory() as req_session:
            wf_r = SqlWorkflowRepository(req_session)
            ex_r = SqlExecutionRepository(req_session)
            ev_r = SqlEventRepository(req_session)
            ar_r = SqlArtifactRepository(req_session)
            reg = AgentRegistry()
            evl = DeterministicRuleEvaluator()
            eng = WorkflowExecutionEngine(
                workflow_repo=wf_r,
                execution_repo=ex_r,
                event_repo=ev_r,
                artifact_repo=ar_r,
                agent_registry=reg,
                evaluator=evl,  # type: ignore
            )
            svc = ExecutionService(
                workflow_repo=wf_r,
                execution_repo=ex_r,
                event_repo=ev_r,
                artifact_repo=ar_r,
                engine=eng,
            )
            res = await svc.submit_execution(
                workflow_id=workflow_id,
                input_data={},
                idempotency_key=None,
                run_to_completion=False,
            )
            await req_session.commit()
            return res

    res1, res2 = await asyncio.gather(submit_null_request(), submit_null_request())

    # Two distinct executions should be created
    assert res1.id != res2.id
    assert res1.idempotency_key is None
    assert res2.idempotency_key is None

    async with session_factory() as verify_session:
        count_res = await verify_session.execute(
            text("SELECT COUNT(*) FROM workflow_executions WHERE workflow_id = :wid"),
            {"wid": workflow_id},
        )
        total = count_res.scalar_one()
        assert total == 2

    await engine.dispose()
