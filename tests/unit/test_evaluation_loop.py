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


# =============================================================================
# 5. ADVERSARIAL INVARIANT & ISOLATION TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_attempt_count_vs_revision_count_independence(db_session):
    """
    Explicitly proves that attempt_count (retries) and revision_count (quality revisions)
    are strictly independent counters and are never incremented by the wrong subsystem.
    """
    agent = MockRevisionAwareAgent()
    registry = AgentRegistry()
    registry.register(agent)

    # Sequence: 1st eval REQUIRES_REVISION -> 2nd eval PASS
    evaluator = MockEvaluator([
        (EvaluationVerdict.REQUIRES_REVISION, 0.5, "Needs more detail"),
        (EvaluationVerdict.PASS, 0.95, "Approved"),
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
            task_key="independent_counters_task",
            name="Counter Independence Test",
            agent_id="revision_aware_agent",
            evaluation_gate=EvaluationGateSpec(enabled=True, max_revisions=2, min_pass_score=0.8),
        )
    ]
    wf_spec = WorkflowSpec(name="counter_test_wf", version=1, description="Counter Test", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    task = final_exec.tasks["independent_counters_task"]
    assert task.status == TaskExecutionStatus.COMPLETED
    # 2 execution claims: initial attempt (1) + revision attempt (2)
    assert task.attempt_count == 2
    # Exactly 1 revision requested & executed
    assert task.revision_count == 1
    assert len(task.evaluation_history) == 2


@pytest.mark.asyncio
async def test_downstream_task_isolated_during_revision_until_pass(db_session):
    """
    Verifies that a downstream task remains blocked and CANNOT receive or observe
    unapproved intermediate revisions until the upstream task receives a PASS verdict.
    """
    agent = MockRevisionAwareAgent()
    registry = AgentRegistry()
    registry.register(agent)

    evaluator = MockEvaluator([
        (EvaluationVerdict.REQUIRES_REVISION, 0.4, "Draft incomplete"),
        (EvaluationVerdict.PASS, 0.95, "Draft accepted"),
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
            task_key="upstream_author",
            name="Upstream Author",
            agent_id="revision_aware_agent",
            evaluation_gate=EvaluationGateSpec(enabled=True, max_revisions=2),
        ),
        TaskSpec(
            task_key="downstream_consumer",
            name="Downstream Consumer",
            agent_id="revision_aware_agent",
            depends_on=["upstream_author"],
            input_mappings={"upstream_content": "upstream_author.content"},
        ),
    ]
    wf_spec = WorkflowSpec(name="isolation_wf", version=1, description="Isolation Test", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.COMPLETED
    assert final_exec.tasks["upstream_author"].status == TaskExecutionStatus.COMPLETED
    assert final_exec.tasks["downstream_consumer"].status == TaskExecutionStatus.COMPLETED

    # Downstream consumer executed with the final revised content, never unapproved draft
    downstream_input = final_exec.tasks["downstream_consumer"].input_data
    assert downstream_input.get("upstream_content") == "High quality revised output"


@pytest.mark.asyncio
async def test_corrupted_artifact_integrity_blocks_evaluation_and_fails_task(db_session):
    """
    Verifies that an agent producing a corrupt/tampered artifact is aborted immediately
    due to SHA-256 verification failure BEFORE evaluation or downstream consumption.
    """
    class CorruptArtifactAgent(AbstractAgent):
        def __init__(self):
            pass

        @property
        def metadata(self):
            return AgentMetadata(
                agent_id="corrupt_artifact_agent",
                name="Corrupt Artifact Agent",
                version="1.0.0",
                description="Agent emitting bad checksum",
                capabilities=[AgentCapability.DATA_ANALYSIS],
                system_instruction="",
            )

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
            bad_artifact = ProducedArtifact(
                name="corrupted.txt",
                artifact_type="text",
                content_or_uri="Hello corrupted world",
                checksum_sha256="0000000000000000000000000000000000000000000000000000000000000000",
            )
            return AgentResult(
                success=True,
                structured_data={"status": "done"},
                artifacts=[bad_artifact],
            )

    registry = AgentRegistry()
    registry.register(CorruptArtifactAgent())

    evaluator = MockEvaluator([(EvaluationVerdict.PASS, 1.0, "Pass")])

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
            task_key="corrupt_task",
            name="Corrupt Task",
            agent_id="corrupt_artifact_agent",
            evaluation_gate=EvaluationGateSpec(enabled=True),
        )
    ]
    wf_spec = WorkflowSpec(name="corrupt_wf", version=1, description="Corrupt Test", input_schema={}, output_schema={}, tasks=tasks)
    saved_wf = await engine.workflow_repo.save_workflow_spec(wf_spec)
    await db_session.commit()

    execution = await engine.submit_workflow(saved_wf.id, {})
    await db_session.commit()

    final_exec = await engine.run_to_completion(execution.id)
    await db_session.commit()

    assert final_exec.status == WorkflowExecutionStatus.FAILED
    assert final_exec.tasks["corrupt_task"].status == TaskExecutionStatus.FAILED
    # Evaluator was NEVER called because artifact verification failed first
    assert len(evaluator.requests) == 0

