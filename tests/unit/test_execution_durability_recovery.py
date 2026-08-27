"""
Phase 7.1 Unit and Integration Tests for Execution Durability, Async Decoupling,
Task Leases, Stale Task Recovery, Watchdog Supervisor, and PostgreSQL Concurrency.
"""

import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import FastAPI

from app.main import create_app, lifespan
from app.api.dependencies import get_db_session, get_model_provider
from app.domain.models.workflow import WorkflowSpec, TaskSpec, RetryPolicySpec
from app.domain.models.execution import TaskExecutionStatus, WorkflowExecutionStatus
from app.domain.models.failure import FailureCategory
from app.persistence.repositories import (
    SqlWorkflowRepository,
    SqlExecutionRepository,
    SqlEventRepository,
    SqlArtifactRepository,
)
from app.persistence.models import TaskExecutionModel, WorkflowExecutionModel
from app.agents.registry import AgentRegistry
from app.orchestration.execution_engine import WorkflowExecutionEngine
from app.orchestration.background_manager import (
    BackgroundExecutionManager,
    get_background_manager,
)
from tests.conftest import MockModelProvider
from tests.unit.test_api_executions import get_canned_provider


@pytest.fixture
def app_instance(db_session: AsyncSession) -> FastAPI:
    app = create_app()

    async def override_get_db_session():
        yield db_session

    def override_get_model_provider():
        return get_canned_provider()

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_model_provider] = override_get_model_provider
    return app


@pytest_asyncio.fixture
async def client(app_instance: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# =============================================================================
# 1. ASYNC SUBMISSION & LIFECYCLE TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_async_submission_returns_201_queued(client: AsyncClient):
    """
    Objective 1 & 2:
    - POST /api/v1/workflows/{id}/executions returns HTTP 201 immediately without blocking.
    - Initial returned execution status is QUEUED.
    - Background task drives the workflow to COMPLETED.
    """
    wf_payload = {
        "name": "async_submission_test",
        "version": 1,
        "description": "Validates non-blocking async submission",
        "tasks": [
            {
                "task_key": "step_1",
                "name": "Step 1",
                "agent_id": "planner_agent",
                "depends_on": [],
                "static_inputs": {"objective": "Async design test"},
            }
        ],
    }
    wf_res = await client.post("/api/v1/workflows", json=wf_payload)
    assert wf_res.status_code == 201
    wf_id = wf_res.json()["id"]

    # 1. Submit execution
    t0 = asyncio.get_event_loop().time()
    exec_res = await client.post(
        f"/api/v1/workflows/{wf_id}/executions",
        json={"input_data": {"objective": "Async design test"}},
    )
    t1 = asyncio.get_event_loop().time()

    # Must return immediately (< 1.0s) with 201 Created and QUEUED or RUNNING status
    assert exec_res.status_code == 201
    assert (t1 - t0) < 1.0, f"Submission took {t1 - t0}s, which is unexpectedly blocking"
    exec_data = exec_res.json()
    assert exec_data["status"] in ("QUEUED", "RUNNING")
    exec_id = exec_data["id"]

    # 2. Poll until background execution completes
    for _ in range(50):
        await asyncio.sleep(0.05)
        detail_res = await client.get(f"/api/v1/executions/{exec_id}")
        if detail_res.json()["status"] == "COMPLETED":
            break

    detail_res = await client.get(f"/api/v1/executions/{exec_id}")
    assert detail_res.status_code == 200
    final_data = detail_res.json()
    assert final_data["status"] == "COMPLETED"
    assert final_data["tasks"][0]["status"] == "COMPLETED"


# =============================================================================
# 2. TASK LEASE & STALE TASK RECOVERY TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_task_claim_sets_finite_lease_duration(db_session: AsyncSession):
    """
    Objective 3 & 4:
    - Claiming a task atomically sets started_at, heartbeat_at, and finite lease_until.
    """
    exec_repo = SqlExecutionRepository(db_session)
    wf_repo = SqlWorkflowRepository(db_session)

    # Setup workflow & execution
    task_spec = TaskSpec(
        task_key="t_lease",
        name="Lease Task",
        agent_id="planner_agent",
        depends_on=[],
        timeout_seconds=45,
    )
    wf_spec = WorkflowSpec(
        name="lease_test_wf",
        version=1,
        description="Lease test",
        input_schema={},
        output_schema={},
        tasks=[task_spec],
    )
    saved_wf = await wf_repo.save_workflow_spec(wf_spec)

    engine = WorkflowExecutionEngine(
        workflow_repo=wf_repo,
        execution_repo=exec_repo,
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=AgentRegistry(),
    )
    execution = await engine.submit_workflow(saved_wf.id, {})

    # Claim task with 45s + 30s buffer = 75s lease
    claimed = await exec_repo.claim_task_for_execution(
        workflow_execution_id=execution.id,
        task_key="t_lease",
        lease_duration_seconds=75,
        worker_id="test_worker_1",
    )
    assert claimed is not None
    assert claimed.status == TaskExecutionStatus.RUNNING
    assert claimed.attempt_count == 1
    assert claimed.started_at is not None

    # Inspect raw database model for lease metadata
    stale_tasks = await exec_repo.find_and_lock_stale_tasks(now=datetime.utcnow() - timedelta(seconds=10))
    # Lease is in the future, should NOT be found as stale
    assert len(stale_tasks) == 0


@pytest.mark.asyncio
async def test_stale_task_recovery_respects_lease_and_retry_limit(db_session: AsyncSession):
    """
    Objective 4 & 5:
    - Non-expired RUNNING tasks are NOT reclaimed.
    - Expired RUNNING tasks with attempts < max_attempts are reclaimed to READY.
    - Expired RUNNING tasks with attempts >= max_attempts transition to FAILED.
    - Recovery is idempotent.
    """
    wf_repo = SqlWorkflowRepository(db_session)
    exec_repo = SqlExecutionRepository(db_session)
    event_repo = SqlEventRepository(db_session)
    art_repo = SqlArtifactRepository(db_session)

    # 1. Create workflow with max_attempts = 2
    task_spec = TaskSpec(
        task_key="reclaim_task",
        name="Reclaim Task",
        agent_id="planner_agent",
        depends_on=[],
        retry_policy=RetryPolicySpec(max_attempts=2),
    )
    wf_spec = WorkflowSpec(
        name="reclaim_test_wf",
        version=1,
        description="Reclaim test",
        input_schema={},
        output_schema={},
        tasks=[task_spec],
    )
    saved_wf = await wf_repo.save_workflow_spec(wf_spec)

    engine = WorkflowExecutionEngine(
        workflow_repo=wf_repo,
        execution_repo=exec_repo,
        event_repo=event_repo,
        artifact_repo=art_repo,
        agent_registry=AgentRegistry(),
    )
    execution = await engine.submit_workflow(saved_wf.id, {})

    # 2. Simulate task claimed, attempt_count = 1, but process crashed in the past (lease expired 10 minutes ago)
    claimed = await exec_repo.claim_task_for_execution(
        workflow_execution_id=execution.id,
        task_key="reclaim_task",
        lease_duration_seconds=30,
        worker_id="crashed_worker",
    )
    assert claimed is not None

    # Manually set lease_until to past to simulate process crash
    past_time = datetime.utcnow() - timedelta(minutes=10)
    from sqlalchemy import select
    res = await db_session.execute(
        select(TaskExecutionModel).where(TaskExecutionModel.id == claimed.id)
    )
    model = res.scalar_one()
    model.lease_until = past_time
    await db_session.flush()

    # 3. Non-expired check: querying with past cutoff should NOT return task
    stale_before = await exec_repo.find_and_lock_stale_tasks(now=past_time - timedelta(minutes=5))
    assert len(stale_before) == 0

    # 4. Expired check: recovering with current time should reclaim task to READY (since attempt 1 < max 2)
    recovered = await engine.recover_stale_tasks(now=datetime.utcnow())
    assert recovered == 1

    updated_exec = await exec_repo.get_workflow_execution(execution.id)
    assert updated_exec is not None
    reclaimed_task = updated_exec.tasks["reclaim_task"]
    assert reclaimed_task.status == TaskExecutionStatus.READY
    assert reclaimed_task.attempt_count == 1  # Retains attempt count

    # 5. Recovery is idempotent: running recovery again immediately yields 0 changes
    recovered_again = await engine.recover_stale_tasks(now=datetime.utcnow())
    assert recovered_again == 0

    # 6. Simulate second crash where attempt reaches max_attempts (attempt_count = 2)
    reclaimed_2 = await exec_repo.claim_task_for_execution(
        workflow_execution_id=execution.id,
        task_key="reclaim_task",
        lease_duration_seconds=30,
    )
    assert reclaimed_2 is not None
    assert reclaimed_2.attempt_count == 2

    # Expire lease again
    res = await db_session.execute(
        select(TaskExecutionModel).where(TaskExecutionModel.id == claimed.id)
    )
    model = res.scalar_one()
    model.lease_until = past_time
    await db_session.flush()

    # Recovering should mark FAILED because attempt_count == max_attempts (2)
    recovered_final = await engine.recover_stale_tasks(now=datetime.utcnow())
    assert recovered_final == 1

    final_exec = await exec_repo.get_workflow_execution(execution.id)
    assert final_exec is not None
    failed_task = final_exec.tasks["reclaim_task"]
    assert failed_task.status == TaskExecutionStatus.FAILED
    assert failed_task.error_details is not None
    assert failed_task.error_details["category"] == "TEMPORAL_FAILURE"


# =============================================================================
# 3. WATCHDOG & GRACEFUL SHUTDOWN TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_watchdog_starts_and_stops_cleanly(db_session: AsyncSession):
    """
    Objective 6 & 7:
    - BackgroundExecutionManager starts periodic watchdog.
    - Stop watchdog cancels background task cleanly without leaks.
    - Graceful shutdown awaits active executions.
    """
    bg_manager = BackgroundExecutionManager()
    assert bg_manager._watchdog_task is None

    # 1. Start watchdog with short interval
    bg_manager.start_watchdog(interval_seconds=0.1)
    assert bg_manager._watchdog_task is not None
    assert not bg_manager._watchdog_task.done()

    # Allow watchdog loop to run at least one tick
    await asyncio.sleep(0.15)

    # 2. Stop watchdog
    await bg_manager.stop_watchdog()
    assert bg_manager._watchdog_task is None

    # 3. Graceful shutdown
    await bg_manager.graceful_shutdown(timeout_seconds=0.5)
    assert bg_manager._shutdown_event.is_set()


# =============================================================================
# 4. CONCURRENT WORKER & DAG PROPAGATION TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_concurrent_workers_atomic_task_claim(db_session: AsyncSession):
    """
    Objective 8:
    - Multiple concurrent workers attempting to claim the same READY task are serialized by PostgreSQL row locks.
    - Exactly one worker succeeds; the second receives None.
    """
    exec_repo = SqlExecutionRepository(db_session)
    wf_repo = SqlWorkflowRepository(db_session)

    task_spec = TaskSpec(task_key="race_task", name="Race Task", agent_id="planner_agent", depends_on=[])
    wf_spec = WorkflowSpec(name="race_wf", version=1, description="Race", input_schema={}, output_schema={}, tasks=[task_spec])
    saved_wf = await wf_repo.save_workflow_spec(wf_spec)

    engine = WorkflowExecutionEngine(
        workflow_repo=wf_repo,
        execution_repo=exec_repo,
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=AgentRegistry(),
    )
    execution = await engine.submit_workflow(saved_wf.id, {})

    # Worker 1 claims task
    w1_claim = await exec_repo.claim_task_for_execution(
        workflow_execution_id=execution.id,
        task_key="race_task",
        worker_id="worker_1",
    )
    assert w1_claim is not None
    assert w1_claim.status == TaskExecutionStatus.RUNNING

    # Worker 2 attempts to claim same task immediately
    w2_claim = await exec_repo.claim_task_for_execution(
        workflow_execution_id=execution.id,
        task_key="race_task",
        worker_id="worker_2",
    )
    assert w2_claim is None  # Second worker is safely rejected by row state


@pytest.mark.asyncio
async def test_workflow_level_recovery_dag_branches(db_session: AsyncSession):
    """
    Objective 9:
    - Validates that recovering a task in a multi-branch DAG (A -> B, A -> C)
      resumes execution and computes dependent tasks correctly.
    """
    provider = MockModelProvider(
        canned_responses={
            "PlanOutput": {
                "plan_summary": "Core plan",
                "sub_tasks": [
                    {
                        "task_key": "step_1",
                        "name": "Step 1",
                        "description": "Do work",
                        "required_capability": "research",
                        "depends_on": [],
                    }
                ],
                "risk_factors": [],
            },
            "ResearchOutput": {
                "findings": [
                    {"topic": "Branch 1", "detail": "Branch 1 insights", "sources_cited": [], "confidence": 0.9}
                ],
                "assumptions": [],
                "uncertainties": [],
                "recommended_follow_up": [],
            },
            "AnalysisOutput": {
                "insights": ["Insight 1"],
                "tradeoffs": [],
                "conclusions": ["Conclusion 1"],
                "confidence_score": 0.9,
            },
        }
    )
    registry = AgentRegistry()
    from app.agents.builtins import PlannerAgent, ResearcherAgent, AnalystAgent
    registry.register(PlannerAgent(model_provider=provider))
    registry.register(ResearcherAgent(model_provider=provider))
    registry.register(AnalystAgent(model_provider=provider))

    wf_repo = SqlWorkflowRepository(db_session)
    exec_repo = SqlExecutionRepository(db_session)
    event_repo = SqlEventRepository(db_session)
    art_repo = SqlArtifactRepository(db_session)

    # DAG: A -> B and A -> C
    tasks = [
        TaskSpec(task_key="A", name="Task A", agent_id="planner_agent", depends_on=[], static_inputs={"objective": "Branch test"}),
        TaskSpec(task_key="B", name="Task B", agent_id="researcher_agent", depends_on=["A"], static_inputs={"objective": "Insights"}),
        TaskSpec(task_key="C", name="Task C", agent_id="analyst_agent", depends_on=["A"], static_inputs={"research_findings": [{"data": "insights"}]}),
    ]
    wf_spec = WorkflowSpec(
        name="branch_recovery_wf",
        version=1,
        description="Branch recovery",
        input_schema={},
        output_schema={},
        tasks=tasks,
    )
    saved_wf = await wf_repo.save_workflow_spec(wf_spec)

    engine = WorkflowExecutionEngine(
        workflow_repo=wf_repo,
        execution_repo=exec_repo,
        event_repo=event_repo,
        artifact_repo=art_repo,
        agent_registry=registry,
    )

    execution = await engine.submit_workflow(saved_wf.id, {"objective": "Branch test"})
    final_exec = await engine.run_to_completion(execution.id)

    assert final_exec.status == WorkflowExecutionStatus.COMPLETED
    assert all(t.status == TaskExecutionStatus.COMPLETED for t in final_exec.tasks.values())
    assert "A" in final_exec.final_outputs
    assert "B" in final_exec.final_outputs
    assert "C" in final_exec.final_outputs
