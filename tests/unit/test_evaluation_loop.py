"""Unit tests for the Quality Evaluation and Bounded Revision Loop in WorkflowExecutionEngine."""

import pytest
from app.orchestration.execution_engine import WorkflowExecutionEngine
from app.agents.registry import AgentRegistry
from app.agents.base import AbstractAgent
from app.domain.models import (
    WorkflowSpec,
    TaskSpec,
    WorkflowExecutionStatus,
    TaskExecutionStatus,
    EvaluationGateSpec,
    AgentMetadata,
    AgentCapability,
    AgentResult,
    ProducedArtifact,
    EvaluationRequest,
    EvaluationResult,
    EvaluationVerdict,
)
from app.persistence.repositories import (
    SqlWorkflowRepository,
    SqlExecutionRepository,
    SqlEventRepository,
    SqlArtifactRepository,
)


class MockEvaluator:
    """Mock evaluator with controllable verdict progression across revisions."""
    def __init__(self, verdicts_sequence):
        self.verdicts_sequence = list(verdicts_sequence)
        self.requests = []

    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        self.requests.append(request)
        verdict, score, rationale = (
            self.verdicts_sequence.pop(0)
            if self.verdicts_sequence
            else (EvaluationVerdict.PASS, 1.0, "Default Pass")
        )
        return EvaluationResult(
            verdict=verdict,
            score=score,
            rationale=rationale,
            passed_checks=["check_1"],
            failed_checks=["check_2"] if verdict != EvaluationVerdict.PASS else [],
            actionable_feedback="Improve detail" if verdict == EvaluationVerdict.REQUIRES_REVISION else None,
            required_changes=["Fix check_2"] if verdict == EvaluationVerdict.REQUIRES_REVISION else [],
            evaluation_duration_ms=10,
        )


class MockRevisionAwareAgent(AbstractAgent):
    """Agent that produces revised output when _revision_context is present in its input."""
    def __init__(self):
        self._metadata = AgentMetadata(
            agent_id="revision_aware_agent",
            name="Revision Aware Agent",
            version="1.0.0",
            description="Agent that responds to revision context",
            capabilities=[AgentCapability.TRANSFORMATION],
            system_instruction="",
        )
        self.execution_count = 0

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
        self.execution_count += 1
        rev_ctx = context.input_payload.get("_revision_context")
        if rev_ctx:
            return AgentResult(
                success=True,
                structured_data={"content": "High quality revised output", "revised": True},
            )
        return AgentResult(
            success=True,
            structured_data={"content": "Initial rough draft"},
        )


# =============================================================================
# 1. EVALUATION PASS & ADVANCEMENT
# =============================================================================

@pytest.mark.asyncio
async def test_evaluation_gate_pass_advances_workflow(db_session):
    """When an evaluation gate evaluates output as PASS, task completes and workflow advances."""
    agent = MockRevisionAwareAgent()
    registry = AgentRegistry()
    registry.register(agent)

    evaluator = MockEvaluator([(EvaluationVerdict.PASS, 0.95, "Excellent output")])

    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=registry,
        evaluator=evaluator,
    )

    tasks = [
        TaskSpec(
            task_key="eval_task",
            name="Evaluated Task",
            agent_id="revision_aware_agent",
            evaluation_gate=EvaluationGateSpec(enabled=True, min_pass_score=0.8),
        )
    ]
    wf_spec = WorkflowSpec(name="eval_pass_wf", version=1, description="Eval Pass", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.COMPLETED
    assert final_exec.tasks["eval_task"].status == TaskExecutionStatus.COMPLETED
    assert len(final_exec.tasks["eval_task"].evaluation_history) == 1
    assert final_exec.tasks["eval_task"].evaluation_history[0]["verdict"] == "PASS"


# =============================================================================
# 2. REVISION & RECOVERY LOOP
# =============================================================================

@pytest.mark.asyncio
async def test_evaluation_gate_requires_revision_recovers_on_next_revision(db_session):
    """Task fails evaluation on revision 0, re-executes with RevisionContext, and passes on revision 1."""
    agent = MockRevisionAwareAgent()
    registry = AgentRegistry()
    registry.register(agent)

    # 1st eval: REQUIRES_REVISION -> 2nd eval: PASS
    evaluator = MockEvaluator([
        (EvaluationVerdict.REQUIRES_REVISION, 0.5, "Needs more detail"),
        (EvaluationVerdict.PASS, 0.95, "Revised output meets all criteria"),
    ])

    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=registry,
        evaluator=evaluator,
    )

    tasks = [
        TaskSpec(
            task_key="revisable_task",
            name="Revisable Task",
            agent_id="revision_aware_agent",
            evaluation_gate=EvaluationGateSpec(enabled=True, max_revisions=2, min_pass_score=0.8),
        )
    ]
    wf_spec = WorkflowSpec(name="revision_recovery_wf", version=1, description="Revision Recovery", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.COMPLETED
    task = final_exec.tasks["revisable_task"]
    assert task.status == TaskExecutionStatus.COMPLETED
    assert task.revision_count == 1
    assert task.attempt_count == 2
    assert len(task.evaluation_history) == 2
    assert task.output_data["revised"] is True


# =============================================================================
# 3. REVISION EXHAUSTION & REJECTION POLICIES
# =============================================================================

@pytest.mark.asyncio
async def test_evaluation_gate_revision_exhaustion_fails_task_and_workflow(db_session):
    """When revision budget is exhausted and rejection_policy=FAIL, task and workflow fail."""
    agent = MockRevisionAwareAgent()
    registry = AgentRegistry()
    registry.register(agent)

    # Always requests revision
    evaluator = MockEvaluator([
        (EvaluationVerdict.REQUIRES_REVISION, 0.4, "Defects persist"),
        (EvaluationVerdict.REQUIRES_REVISION, 0.4, "Defects persist"),
    ])

    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=registry,
        evaluator=evaluator,
    )

    tasks = [
        TaskSpec(
            task_key="failing_rev_task",
            name="Failing Rev Task",
            agent_id="revision_aware_agent",
            evaluation_gate=EvaluationGateSpec(
                enabled=True,
                max_revisions=1,  # Only 1 revision allowed
                rejection_policy="FAIL",
            ),
        )
    ]
    wf_spec = WorkflowSpec(name="exhaust_fail_wf", version=1, description="Exhaust Fail", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.FAILED
    task = final_exec.tasks["failing_rev_task"]
    assert task.status == TaskExecutionStatus.FAILED
    assert task.revision_count == 1
    err_details = task.error_details
    assert err_details is not None and "budget exhausted" in str(err_details.get("error", ""))


@pytest.mark.asyncio
async def test_evaluation_gate_rejection_policy_escalates_to_human(db_session):
    """When revision budget is exhausted and rejection_policy=ESCALATE, task enters ESCALATED and workflow pauses."""
    agent = MockRevisionAwareAgent()
    registry = AgentRegistry()
    registry.register(agent)

    evaluator = MockEvaluator([
        (EvaluationVerdict.REQUIRES_REVISION, 0.4, "Defects persist"),
        (EvaluationVerdict.REQUIRES_REVISION, 0.4, "Defects persist"),
    ])

    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=registry,
        evaluator=evaluator,
    )

    tasks = [
        TaskSpec(
            task_key="escalating_task",
            name="Escalating Task",
            agent_id="revision_aware_agent",
            evaluation_gate=EvaluationGateSpec(
                enabled=True,
                max_revisions=1,
                rejection_policy="ESCALATE",
            ),
        )
    ]
    wf_spec = WorkflowSpec(name="escalate_wf", version=1, description="Escalate Test", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    task = final_exec.tasks["escalating_task"]
    assert task.status == TaskExecutionStatus.ESCALATED
    assert final_exec.status != WorkflowExecutionStatus.COMPLETED
    assert final_exec.status != WorkflowExecutionStatus.FAILED


# =============================================================================
# 4. EVENT AUDIT & DOWNSTREAM CASCADE
# =============================================================================

@pytest.mark.asyncio
async def test_evaluation_failure_cascades_to_downstream_tasks(db_session):
    """When an upstream task evaluation fails, downstream dependent tasks fail."""
    agent = MockRevisionAwareAgent()
    registry = AgentRegistry()
    registry.register(agent)

    evaluator = MockEvaluator([(EvaluationVerdict.FAIL, 0.1, "Severe defect")])

    engine = WorkflowExecutionEngine(
        workflow_repo=SqlWorkflowRepository(db_session),
        execution_repo=SqlExecutionRepository(db_session),
        event_repo=SqlEventRepository(db_session),
        artifact_repo=SqlArtifactRepository(db_session),
        agent_registry=registry,
        evaluator=evaluator,
    )

    tasks = [
        TaskSpec(
            task_key="root_eval",
            name="Root Eval",
            agent_id="revision_aware_agent",
            evaluation_gate=EvaluationGateSpec(enabled=True),
        ),
        TaskSpec(
            task_key="child_task",
            name="Child Task",
            agent_id="revision_aware_agent",
            depends_on=["root_eval"],
        ),
    ]
    wf_spec = WorkflowSpec(name="cascade_eval_wf", version=1, description="Cascade Eval", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.FAILED
    assert final_exec.tasks["root_eval"].status == TaskExecutionStatus.FAILED
    assert final_exec.tasks["child_task"].status == TaskExecutionStatus.FAILED

    events = await engine.event_repo.list_events_for_execution(final_exec.id)
    event_types = [e.event_type.value for e in events]
    assert "EVALUATION_STARTED" in event_types
    assert "EVALUATION_COMPLETED" in event_types
    assert "EVALUATION_FAILED" in event_types
