"""Comprehensive unit tests for the WorkflowExecutionEngine."""

import pytest
from app.orchestration.execution_engine import WorkflowExecutionEngine
from app.agents.registry import AgentRegistry
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
)
from app.persistence.repositories import (
    SqlWorkflowRepository,
    SqlExecutionRepository,
    SqlEventRepository,
    SqlArtifactRepository,
)
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


@pytest.mark.asyncio
async def test_end_to_end_5_agent_pipeline_execution(db_session, agent_registry):
    """Executes a full 5-agent sequential DAG workflow to completion."""
    wf_repo = SqlWorkflowRepository(db_session)
    exec_repo = SqlExecutionRepository(db_session)
    event_repo = SqlEventRepository(db_session)
    artifact_repo = SqlArtifactRepository(db_session)

    engine = WorkflowExecutionEngine(
        workflow_repo=wf_repo,
        execution_repo=exec_repo,
        event_repo=event_repo,
        artifact_repo=artifact_repo,
        agent_registry=agent_registry,
    )

    # Define 5-step workflow DAG
    tasks = [
        TaskSpec(task_key="plan", name="Plan", agent_id="planner_agent", depends_on=[]),
        TaskSpec(
            task_key="research",
            name="Research",
            agent_id="researcher_agent",
            depends_on=["plan"],
            input_mappings={"objective": "plan.plan_summary"},
        ),
        TaskSpec(
            task_key="analyst",
            name="Analyze",
            agent_id="analyst_agent",
            depends_on=["research"],
            input_mappings={"research_findings": "research.findings"},
        ),
        TaskSpec(
            task_key="review",
            name="Review",
            agent_id="reviewer_agent",
            depends_on=["analyst"],
            input_mappings={"target_content": "analyst"},
        ),
        TaskSpec(
            task_key="synthesizer",
            name="Synthesize",
            agent_id="synthesizer_agent",
            depends_on=["review"],
            input_mappings={"review_decision": "review.decision"},
        ),
    ]
    wf_spec = WorkflowSpec(
        name="full_5_agent_wf",
        version=1,
        description="Full 5 Agent End-to-End Pipeline",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        tasks=tasks,
    )
    saved_wf = await wf_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    # Submit workflow
    execution = await engine.submit_workflow(
        workflow_id=saved_wf.id,
        initial_inputs={"objective": "Design next-gen orchestrator"},
        idempotency_key="unique-exec-101",
    )
    await db_session.commit()

    assert execution.status == WorkflowExecutionStatus.QUEUED
    assert len(execution.tasks) == 5

    # Run workflow to completion
    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.COMPLETED
    for task_key in ["plan", "research", "analyst", "review", "synthesizer"]:
        assert final_exec.tasks[task_key].status == TaskExecutionStatus.COMPLETED
        assert final_exec.tasks[task_key].output_data is not None

    # Verify produced artifacts
    artifacts = await artifact_repo.list_artifacts_for_execution(final_exec.id)
    assert len(artifacts) >= 5

    # Verify event trail
    events = await event_repo.list_events_for_execution(final_exec.id)
    assert len(events) >= 10


@pytest.mark.asyncio
async def test_parallel_branch_execution(db_session, agent_registry):
    """Executes parallel DAG branches: A -> [B, C] -> D."""
    wf_repo = SqlWorkflowRepository(db_session)
    exec_repo = SqlExecutionRepository(db_session)
    event_repo = SqlEventRepository(db_session)
    artifact_repo = SqlArtifactRepository(db_session)

    engine = WorkflowExecutionEngine(
        workflow_repo=wf_repo,
        execution_repo=exec_repo,
        event_repo=event_repo,
        artifact_repo=artifact_repo,
        agent_registry=agent_registry,
    )

    tasks = [
        TaskSpec(task_key="planner", name="Plan", agent_id="planner_agent", depends_on=[]),
        TaskSpec(task_key="branch_1", name="Branch 1", agent_id="researcher_agent", depends_on=["planner"]),
        TaskSpec(task_key="branch_2", name="Branch 2", agent_id="researcher_agent", depends_on=["planner"]),
        TaskSpec(task_key="join_node", name="Join", agent_id="synthesizer_agent", depends_on=["branch_1", "branch_2"]),
    ]
    wf_spec = WorkflowSpec(
        name="parallel_wf",
        version=1,
        description="Parallel branches",
        input_schema={},
        output_schema={},
        tasks=tasks,
    )
    saved_wf = await wf_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(
        workflow_id=saved_wf.id,
        initial_inputs={"objective": "Parallel Research"},
    )
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.COMPLETED
    assert final_exec.tasks["branch_1"].status == TaskExecutionStatus.COMPLETED
    assert final_exec.tasks["branch_2"].status == TaskExecutionStatus.COMPLETED
    assert final_exec.tasks["join_node"].status == TaskExecutionStatus.COMPLETED


@pytest.mark.asyncio
async def test_idempotent_workflow_submission(db_session, agent_registry):
    """Submitting with identical idempotency_key returns existing execution."""
    wf_repo = SqlWorkflowRepository(db_session)
    exec_repo = SqlExecutionRepository(db_session)
    event_repo = SqlEventRepository(db_session)
    artifact_repo = SqlArtifactRepository(db_session)

    engine = WorkflowExecutionEngine(
        workflow_repo=wf_repo,
        execution_repo=exec_repo,
        event_repo=event_repo,
        artifact_repo=artifact_repo,
        agent_registry=agent_registry,
    )

    wf_spec = WorkflowSpec(
        name="idempotent_wf",
        version=1,
        description="Idempotency Test",
        input_schema={},
        output_schema={},
        tasks=[TaskSpec(task_key="t1", name="T1", agent_id="planner_agent")],
    )
    saved_wf = await wf_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    exec_1 = await engine.submit_workflow(saved_wf.id, {"k": 1}, idempotency_key="idempotent-key-42")
    await db_session.commit()

    exec_2 = await engine.submit_workflow(saved_wf.id, {"k": 1}, idempotency_key="idempotent-key-42")
    assert exec_1.id == exec_2.id


@pytest.mark.asyncio
async def test_human_approval_gating_pauses_workflow(db_session, agent_registry):
    """A task requiring human approval pauses in WAITING_APPROVAL without completing workflow."""
    wf_repo = SqlWorkflowRepository(db_session)
    exec_repo = SqlExecutionRepository(db_session)
    event_repo = SqlEventRepository(db_session)
    artifact_repo = SqlArtifactRepository(db_session)

    engine = WorkflowExecutionEngine(
        workflow_repo=wf_repo,
        execution_repo=exec_repo,
        event_repo=event_repo,
        artifact_repo=artifact_repo,
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
    saved_wf = await wf_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {"objective": "Guarded Action"})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    # Workflow is not COMPLETED yet; task is in WAITING_APPROVAL
    assert final_exec.tasks["guarded_task"].status == TaskExecutionStatus.WAITING_APPROVAL
    assert final_exec.status != WorkflowExecutionStatus.COMPLETED


@pytest.mark.asyncio
async def test_task_failure_and_workflow_failure_cascade(db_session, agent_registry):
    """When a task fails with no retries, downstream tasks cascade to BLOCKED/FAILED and workflow fails."""
    wf_repo = SqlWorkflowRepository(db_session)
    exec_repo = SqlExecutionRepository(db_session)
    event_repo = SqlEventRepository(db_session)
    artifact_repo = SqlArtifactRepository(db_session)

    engine = WorkflowExecutionEngine(
        workflow_repo=wf_repo,
        execution_repo=exec_repo,
        event_repo=event_repo,
        artifact_repo=artifact_repo,
        agent_registry=agent_registry,
    )

    # Task 1 references an unknown agent -> fails
    tasks = [
        TaskSpec(
            task_key="failing_task",
            name="Failing Task",
            agent_id="non_existent_agent",
            retry_policy=RetryPolicySpec(max_attempts=1),
        ),
        TaskSpec(
            task_key="downstream_task",
            name="Downstream",
            agent_id="planner_agent",
            depends_on=["failing_task"],
        ),
    ]
    wf_spec = WorkflowSpec(name="failure_cascade_wf", version=1, description="Cascade Test", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await wf_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.FAILED
    assert final_exec.tasks["failing_task"].status == TaskExecutionStatus.FAILED
    assert final_exec.tasks["downstream_task"].status == TaskExecutionStatus.FAILED

