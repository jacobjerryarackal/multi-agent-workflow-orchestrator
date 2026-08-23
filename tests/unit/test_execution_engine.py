"""Comprehensive unit and hardening tests for the WorkflowExecutionEngine."""

import asyncio
import pytest
from app.orchestration.execution_engine import WorkflowExecutionEngine
from app.agents.registry import AgentRegistry
from app.agents.base import AbstractAgent
from app.agents.builtins import (
    PlannerAgent,
    ResearcherAgent,
    AnalystAgent,
    ReviewerAgent,
    SynthesizerAgent,
)
from app.domain.models import (
    WorkflowSpec,
    TaskSpec,
    WorkflowExecutionStatus,
    TaskExecutionStatus,
    RetryPolicySpec,
    ApprovalGateSpec,
    AgentMetadata,
    AgentCapability,
    AgentExecutionContext,
    AgentResult,
    ProducedArtifact,
)
from app.persistence.repositories import (
    SqlWorkflowRepository,
    SqlExecutionRepository,
    SqlEventRepository,
    SqlArtifactRepository,
)
from app.core.exceptions import WorkflowNotFoundError
from tests.conftest import MockModelProvider


@pytest.fixture
def agent_registry():
    """Sets up an AgentRegistry pre-loaded with mock-backed specialized agents."""
    canned = {
        "PlanOutput": {
            "plan_summary": "E2E Execution Plan",
            "sub_tasks": [
                {
                    "task_key": "res_1",
                    "name": "Research",
                    "description": "Gather facts",
                    "required_capability": "research",
                    "depends_on": [],
                    "expected_output_type": "json",
                }
            ],
            "risk_factors": [],
        },
        "ResearchOutput": {
            "findings": [
                {
                    "topic": "Multi-Agent Systems",
                    "detail": "Decoupled agents coordinate effectively via DAG orchestration.",
                    "sources_cited": ["Reference 2026"],
                    "confidence": 0.95,
                }
            ],
            "assumptions": [],
            "uncertainties": [],
            "recommended_follow_up": [],
        },
        "AnalysisOutput": {
            "insights": ["High architectural coherence."],
            "tradeoffs": [
                {
                    "option_name": "DAG Engine",
                    "pros": ["Deterministic"],
                    "cons": ["Scheduling complexity"],
                    "impact_score": 0.95,
                }
            ],
            "conclusions": ["Proceed with DAG orchestrator."],
            "confidence_score": 0.95,
        },
        "ReviewOutput": {
            "decision": "PASS",
            "passed_checks": ["All standards met"],
            "failed_checks": [],
            "issues": [],
            "required_changes": [],
            "confidence": 0.98,
        },
        "SynthesisOutput": {
            "title": "Final Orchestrator Strategy",
            "executive_summary": "Comprehensive validated deliverable.",
            "key_conclusions": ["Production ready multi-agent pipeline."],
            "detailed_report": "# Comprehensive Strategy\nAll tasks succeeded.",
            "review_acknowledgment": "Review audit confirmed status PASS.",
        },
    }
    provider = MockModelProvider(canned)
    registry = AgentRegistry()
    registry.register(PlannerAgent(provider))
    registry.register(ResearcherAgent(provider))
    registry.register(AnalystAgent(provider))
    registry.register(ReviewerAgent(provider))
    registry.register(SynthesizerAgent(provider))
    return registry


# =============================================================================
# 1. BASIC & SEQUENTIAL EXECUTION TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_single_task_workflow_execution(db_session, agent_registry):
    """Executes a simple single-task workflow to completion."""
    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=agent_registry,
    )
    wf_spec = WorkflowSpec(
        name="single_task_wf",
        version=1,
        description="Single task",
        input_schema={},
        output_schema={},
        tasks=[TaskSpec(task_key="step_1", name="Step 1", agent_id="planner_agent")],
    )
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    exec_record = await engine.submit_workflow(saved_wf.id, {"objective": "Single step"})
    await db_session.commit()

    final_exec = await engine.run_to_completion(exec_record.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.COMPLETED
    assert final_exec.tasks["step_1"].status == TaskExecutionStatus.COMPLETED


@pytest.mark.asyncio
async def test_sequential_3_agent_dag_execution(db_session, agent_registry):
    """Executes sequential DAG: Planner -> Researcher -> Analyst."""
    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=agent_registry,
    )
    tasks = [
        TaskSpec(task_key="p", name="Plan", agent_id="planner_agent", depends_on=[]),
        TaskSpec(task_key="r", name="Research", agent_id="researcher_agent", depends_on=["p"], input_mappings={"objective": "p.plan_summary"}),
        TaskSpec(task_key="a", name="Analyze", agent_id="analyst_agent", depends_on=["r"], input_mappings={"research_findings": "r.findings"}),
    ]
    wf_spec = WorkflowSpec(name="seq_3_wf", version=1, description="Sequential 3", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    exec_record = await engine.submit_workflow(saved_wf.id, {"objective": "Sequential Analysis"})
    await db_session.commit()

    final_exec = await engine.run_to_completion(exec_record.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.COMPLETED
    assert final_exec.tasks["p"].status == TaskExecutionStatus.COMPLETED
    assert final_exec.tasks["r"].status == TaskExecutionStatus.COMPLETED
    assert final_exec.tasks["a"].status == TaskExecutionStatus.COMPLETED


@pytest.mark.asyncio
async def test_end_to_end_5_agent_pipeline_execution(db_session, agent_registry):
    """Executes a full 5-agent sequential DAG workflow to completion."""
    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=agent_registry,
    )

    tasks = [
        TaskSpec(task_key="plan", name="Plan", agent_id="planner_agent", depends_on=[]),
        TaskSpec(task_key="research", name="Research", agent_id="researcher_agent", depends_on=["plan"], input_mappings={"objective": "plan.plan_summary"}),
        TaskSpec(task_key="analyst", name="Analyze", agent_id="analyst_agent", depends_on=["research"], input_mappings={"research_findings": "research.findings"}),
        TaskSpec(task_key="review", name="Review", agent_id="reviewer_agent", depends_on=["analyst"], input_mappings={"target_content": "analyst"}),
        TaskSpec(task_key="synthesizer", name="Synthesize", agent_id="synthesizer_agent", depends_on=["review"], input_mappings={"review_decision": "review.decision"}),
    ]
    wf_spec = WorkflowSpec(name="full_5_agent_wf", version=1, description="Full 5 Agent Pipeline", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {"objective": "Design next-gen orchestrator"}, idempotency_key="unique-exec-101")
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.COMPLETED
    for task_key in ["plan", "research", "analyst", "review", "synthesizer"]:
        assert final_exec.tasks[task_key].status == TaskExecutionStatus.COMPLETED

    artifacts = await engine.artifact_repo.list_artifacts_for_execution(final_exec.id)
    assert len(artifacts) >= 5

    events = await engine.event_repo.list_events_for_execution(final_exec.id)
    assert len(events) >= 10


# =============================================================================
# 2. PARALLELISM & CONCURRENCY LIMIT TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_parallel_branch_execution(db_session, agent_registry):
    """Executes parallel DAG branches: Planner -> [Branch 1, Branch 2] -> Join."""
    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=agent_registry,
    )

    tasks = [
        TaskSpec(task_key="planner", name="Plan", agent_id="planner_agent", depends_on=[]),
        TaskSpec(task_key="branch_1", name="Branch 1", agent_id="researcher_agent", depends_on=["planner"]),
        TaskSpec(task_key="branch_2", name="Branch 2", agent_id="researcher_agent", depends_on=["planner"]),
        TaskSpec(task_key="join_node", name="Join", agent_id="synthesizer_agent", depends_on=["branch_1", "branch_2"]),
    ]
    wf_spec = WorkflowSpec(name="parallel_wf", version=1, description="Parallel branches", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {"objective": "Parallel Research"})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.COMPLETED
    assert final_exec.tasks["branch_1"].status == TaskExecutionStatus.COMPLETED
    assert final_exec.tasks["branch_2"].status == TaskExecutionStatus.COMPLETED
    assert final_exec.tasks["join_node"].status == TaskExecutionStatus.COMPLETED


@pytest.mark.asyncio
async def test_bounded_parallelism_concurrency_limit(db_session):
    """Verifies that max_parallel_tasks strictly limits concurrent execution."""
    concurrency_tracker = {"current": 0, "max_seen": 0}

    class ConcurrencyTrackingAgent(AbstractAgent):
        def __init__(self):
            self._metadata = AgentMetadata(
                agent_id="concurrency_agent",
                name="Concurrency Agent",
                version="1.0.0",
                description="Tracks concurrency",
                capabilities=[AgentCapability.TRANSFORMATION],
                system_instruction="",
            )

        @property
        def metadata(self):
            return self._metadata

        @property
        def input_schema(self):
            from pydantic import BaseModel
            return BaseModel

        @property
        def output_schema(self):
            from pydantic import BaseModel
            return BaseModel

        def build_prompt(self, context, validated_input):
            return ""

        async def execute(self, context):
            concurrency_tracker["current"] += 1
            if concurrency_tracker["current"] > concurrency_tracker["max_seen"]:
                concurrency_tracker["max_seen"] = concurrency_tracker["current"]
            await asyncio.sleep(0.02)
            concurrency_tracker["current"] -= 1
            return AgentResult(success=True, structured_data={"done": True})

    registry = AgentRegistry()
    registry.register(ConcurrencyTrackingAgent())

    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=registry,
    )

    # 4 independent parallel tasks with max_parallel_tasks = 2
    tasks = [
        TaskSpec(task_key=f"t_{i}", name=f"Task {i}", agent_id="concurrency_agent", depends_on=[])
        for i in range(4)
    ]
    wf_spec = WorkflowSpec(
        name="bounded_parallel_wf",
        version=1,
        description="Bounded Concurrency Test",
        input_schema={},
        output_schema={},
        max_parallel_tasks=2,  # Bounded to 2
        tasks=tasks,
    )
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.COMPLETED
    assert concurrency_tracker["max_seen"] <= 2


# =============================================================================
# 3. RETRY, RECOVERY & FAILURE PROPAGATION TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_task_retry_and_recovery_flow(db_session):
    """Task fails on 1st attempt, then succeeds on 2nd attempt (retry recovery)."""
    attempt_tracker = {"count": 0}

    class FlakyAgent(AbstractAgent):
        def __init__(self):
            self._metadata = AgentMetadata(
                agent_id="flaky_agent",
                name="Flaky Agent",
                version="1.0.0",
                description="Flaky test agent",
                capabilities=[AgentCapability.TRANSFORMATION],
                system_instruction="",
            )

        @property
        def metadata(self):
            return self._metadata

        @property
        def input_schema(self):
            from pydantic import BaseModel
            return BaseModel

        @property
        def output_schema(self):
            from pydantic import BaseModel
            return BaseModel

        def build_prompt(self, context, validated_input):
            return ""

        async def execute(self, context):
            attempt_tracker["count"] += 1
            if attempt_tracker["count"] == 1:
                return AgentResult(success=False, error_message="Transient network glitch", error_category="infrastructure_provider_failure")
            return AgentResult(success=True, structured_data={"recovered": True})

    registry = AgentRegistry()
    registry.register(FlakyAgent())

    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=registry,
    )

    tasks = [
        TaskSpec(
            task_key="flaky_task",
            name="Flaky Task",
            agent_id="flaky_agent",
            retry_policy=RetryPolicySpec(max_attempts=2),  # 1 initial + 1 retry = 2 attempts
        )
    ]
    wf_spec = WorkflowSpec(name="retry_recovery_wf", version=1, description="Retry Recovery", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.COMPLETED
    assert final_exec.tasks["flaky_task"].status == TaskExecutionStatus.COMPLETED
    assert final_exec.tasks["flaky_task"].attempt_count == 2


@pytest.mark.asyncio
async def test_task_retry_exhaustion_flow(db_session):
    """Task fails on all allowed attempts and terminally transitions to FAILED."""
    class AlwaysFailingAgent(AbstractAgent):
        def __init__(self):
            self._metadata = AgentMetadata(
                agent_id="failing_agent",
                name="Failing Agent",
                version="1.0.0",
                description="Always fails",
                capabilities=[AgentCapability.TRANSFORMATION],
                system_instruction="",
            )

        @property
        def metadata(self):
            return self._metadata

        @property
        def input_schema(self):
            from pydantic import BaseModel
            return BaseModel

        @property
        def output_schema(self):
            from pydantic import BaseModel
            return BaseModel

        def build_prompt(self, context, validated_input):
            return ""

        async def execute(self, context):
            return AgentResult(success=False, error_message="Persistent failure", error_category="infrastructure_provider_failure")

    registry = AgentRegistry()
    registry.register(AlwaysFailingAgent())

    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=registry,
    )

    tasks = [
        TaskSpec(
            task_key="failing_task",
            name="Failing Task",
            agent_id="failing_agent",
            retry_policy=RetryPolicySpec(max_attempts=2),  # 2 attempts total
        )
    ]
    wf_spec = WorkflowSpec(name="retry_exhaust_wf", version=1, description="Retry Exhaust", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.FAILED
    assert final_exec.tasks["failing_task"].status == TaskExecutionStatus.FAILED
    assert final_exec.tasks["failing_task"].attempt_count == 2


@pytest.mark.asyncio
async def test_failure_cascade_and_workflow_failure(db_session, agent_registry):
    """When a prerequisite task fails, downstream dependent tasks fail and workflow terminates."""
    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=agent_registry,
    )

    tasks = [
        TaskSpec(
            task_key="root_fail",
            name="Root Fail",
            agent_id="non_existent_agent",
            retry_policy=RetryPolicySpec(max_attempts=1),
        ),
        TaskSpec(
            task_key="child_node",
            name="Child Node",
            agent_id="planner_agent",
            depends_on=["root_fail"],
        ),
    ]
    wf_spec = WorkflowSpec(name="cascade_wf", version=1, description="Cascade Test", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.FAILED
    assert final_exec.tasks["root_fail"].status == TaskExecutionStatus.FAILED
    assert final_exec.tasks["child_node"].status == TaskExecutionStatus.FAILED


# =============================================================================
# 4. GATES, TIMEOUTS, ARTIFACT INTEGRITY & IDEMPOTENCY
# =============================================================================

@pytest.mark.asyncio
async def test_human_approval_gating_pauses_workflow(db_session, agent_registry):
    """Task requiring human approval enters WAITING_APPROVAL; workflow pauses without completing."""
    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=agent_registry,
    )

    tasks = [
        TaskSpec(
            task_key="guarded_task",
            name="Guarded Task",
            agent_id="planner_agent",
            approval_gate=ApprovalGateSpec(required=True, approver_roles=["admin"]),
        )
    ]
    wf_spec = WorkflowSpec(name="approval_wf", version=1, description="Approval Test", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {"objective": "Guarded Action"})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.tasks["guarded_task"].status == TaskExecutionStatus.WAITING_APPROVAL
    assert final_exec.status != WorkflowExecutionStatus.COMPLETED


@pytest.mark.asyncio
async def test_artifact_integrity_failure_detection(db_session):
    """Corrupted artifact SHA-256 checksum fails task execution immediately."""
    class CorruptArtifactAgent(AbstractAgent):
        def __init__(self):
            self._metadata = AgentMetadata(
                agent_id="corrupt_agent",
                name="Corrupt Agent",
                version="1.0.0",
                description="Corrupt",
                capabilities=[AgentCapability.TRANSFORMATION],
                system_instruction="",
            )

        @property
        def metadata(self):
            return self._metadata

        @property
        def input_schema(self):
            from pydantic import BaseModel
            return BaseModel

        @property
        def output_schema(self):
            from pydantic import BaseModel
            return BaseModel

        def build_prompt(self, context, validated_input):
            return ""

        def produce_artifacts(self, output, context):
            return [
                ProducedArtifact(
                    name="corrupt.json",
                    artifact_type="json",
                    content_or_uri="valid content",
                    checksum_sha256="bad_corrupted_checksum_12345",  # Invalid checksum
                )
            ]

        async def execute(self, context):
            from pydantic import BaseModel

            class DummyModel(BaseModel):
                val: str = "ok"

            dummy_out = DummyModel()
            return AgentResult(
                success=True,
                structured_data={"ok": True},
                artifacts=self.produce_artifacts(dummy_out, context),
            )

    registry = AgentRegistry()
    registry.register(CorruptArtifactAgent())

    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=registry,
    )

    tasks = [TaskSpec(task_key="corrupt_task", name="Corrupt", agent_id="corrupt_agent")]
    wf_spec = WorkflowSpec(name="corrupt_wf", version=1, description="Corrupt", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.FAILED
    assert final_exec.tasks["corrupt_task"].status == TaskExecutionStatus.FAILED
    err_details = final_exec.tasks["corrupt_task"].error_details
    assert err_details is not None and "checksum mismatch" in str(err_details.get("error", ""))


@pytest.mark.asyncio
async def test_workflow_timeout_enforcement(db_session, monkeypatch):
    """Workflow exceeding max_workflow_duration_seconds transitions to TIMED_OUT."""
    class SlowAgent(AbstractAgent):
        def __init__(self):
            self._metadata = AgentMetadata(
                agent_id="slow_agent",
                name="Slow Agent",
                version="1.0.0",
                description="Slow",
                capabilities=[AgentCapability.TRANSFORMATION],
                system_instruction="",
            )

        @property
        def metadata(self):
            return self._metadata

        @property
        def input_schema(self):
            from pydantic import BaseModel
            return BaseModel

        @property
        def output_schema(self):
            from pydantic import BaseModel
            return BaseModel

        def build_prompt(self, context, validated_input):
            return ""

        async def execute(self, context):
            return AgentResult(success=True, structured_data={"done": True})

    registry = AgentRegistry()
    registry.register(SlowAgent())

    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=registry,
    )

    tasks = [TaskSpec(task_key="slow_task", name="Slow Task", agent_id="slow_agent")]
    wf_spec = WorkflowSpec(
        name="timeout_wf",
        version=1,
        description="Timeout Test",
        input_schema={},
        output_schema={},
        max_workflow_duration_seconds=30,  # Valid boundary (ge=30)
        tasks=tasks,
    )
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {})
    await db_session.commit()

    # Simulate elapsed time > 30s
    time_seq = [100.0, 100.0, 150.0, 150.0, 150.0]
    monkeypatch.setattr("time.perf_counter", lambda: time_seq.pop(0) if time_seq else 200.0)

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.TIMED_OUT


@pytest.mark.asyncio
async def test_idempotent_workflow_submission(db_session, agent_registry):
    """Submitting with identical idempotency_key returns existing execution."""
    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=agent_registry,
    )

    wf_spec = WorkflowSpec(name="idempotent_wf", version=1, description="Idempotency Test", input_schema={}, output_schema={}, tasks=[TaskSpec(task_key="t1", name="T1", agent_id="planner_agent")])
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    exec_1 = await engine.submit_workflow(saved_wf.id, {"k": 1}, idempotency_key="idempotent-key-42")
    await db_session.commit()

    exec_2 = await engine.submit_workflow(saved_wf.id, {"k": 1}, idempotency_key="idempotent-key-42")
    assert exec_1.id == exec_2.id


@pytest.mark.asyncio
async def test_submit_workflow_non_existent_id_raises(db_session, agent_registry):
    """Submitting a non-existent workflow ID raises WorkflowNotFoundError."""
    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=agent_registry,
    )
    with pytest.raises(WorkflowNotFoundError, match="does not exist"):
        await engine.submit_workflow("invalid_wf_id", {})


@pytest.mark.asyncio
async def test_run_to_completion_non_existent_execution_raises(db_session, agent_registry):
    """Running a non-existent execution ID raises WorkflowNotFoundError."""
    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=agent_registry,
    )
    with pytest.raises(WorkflowNotFoundError, match="not found"):
        await engine.run_to_completion("invalid_exec_id")
