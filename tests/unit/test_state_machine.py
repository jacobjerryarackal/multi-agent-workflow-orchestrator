"""Comprehensive unit tests verifying Workflow and Task state machine transitions, guards, and DAG validation."""

import pytest
from app.domain.models import (
    WorkflowSpec,
    TaskSpec,
    WorkflowExecution,
    WorkflowExecutionStatus,
    TaskExecution,
    TaskExecutionStatus,
    RetryPolicySpec,
    ApprovalGateSpec,
)
from app.orchestration.state_machine import (
    WorkflowStateMachine,
    WorkflowCommand,
    TaskCommand,
)
from app.orchestration.dependency_resolver import DependencyResolver
from app.core.exceptions import StateTransitionError, WorkflowValidationError, CyclicDependencyError


# =============================================================================
# 1. WORKFLOW STATE MACHINE TESTS
# =============================================================================

def test_workflow_lifecycle_success_path():
    execution = WorkflowExecution(workflow_id="wf-1", status=WorkflowExecutionStatus.QUEUED)
    
    # QUEUED -> RUNNING
    status = WorkflowStateMachine.transition_workflow(execution, WorkflowCommand.START)
    assert status == WorkflowExecutionStatus.RUNNING
    assert execution.status == WorkflowExecutionStatus.RUNNING

    # RUNNING -> COMPLETED
    status = WorkflowStateMachine.transition_workflow(execution, WorkflowCommand.COMPLETE)
    assert status == WorkflowExecutionStatus.COMPLETED
    assert execution.status == WorkflowExecutionStatus.COMPLETED


def test_workflow_pause_and_resume():
    execution = WorkflowExecution(workflow_id="wf-1", status=WorkflowExecutionStatus.QUEUED)
    WorkflowStateMachine.transition_workflow(execution, WorkflowCommand.START)
    
    # RUNNING -> PAUSED
    status = WorkflowStateMachine.transition_workflow(execution, WorkflowCommand.PAUSE)
    assert status == WorkflowExecutionStatus.PAUSED

    # PAUSED -> RUNNING
    status = WorkflowStateMachine.transition_workflow(execution, WorkflowCommand.RESUME)
    assert status == WorkflowExecutionStatus.RUNNING


def test_workflow_terminal_state_protection():
    execution = WorkflowExecution(workflow_id="wf-1", status=WorkflowExecutionStatus.QUEUED)
    WorkflowStateMachine.transition_workflow(execution, WorkflowCommand.START)
    WorkflowStateMachine.transition_workflow(execution, WorkflowCommand.COMPLETE)

    # Invariant: Terminal state cannot transition
    with pytest.raises(StateTransitionError, match="terminal state 'COMPLETED'"):
        WorkflowStateMachine.transition_workflow(execution, WorkflowCommand.START)

    with pytest.raises(StateTransitionError, match="terminal state 'COMPLETED'"):
        WorkflowStateMachine.transition_workflow(execution, WorkflowCommand.FAIL)


def test_workflow_cancellation():
    # Cancellation from QUEUED
    exec_queued = WorkflowExecution(workflow_id="wf-1", status=WorkflowExecutionStatus.QUEUED)
    WorkflowStateMachine.transition_workflow(exec_queued, WorkflowCommand.CANCEL)
    assert exec_queued.status == WorkflowExecutionStatus.CANCELLED

    # Cancellation from RUNNING
    exec_running = WorkflowExecution(workflow_id="wf-2", status=WorkflowExecutionStatus.QUEUED)
    WorkflowStateMachine.transition_workflow(exec_running, WorkflowCommand.START)
    WorkflowStateMachine.transition_workflow(exec_running, WorkflowCommand.CANCEL)
    assert exec_running.status == WorkflowExecutionStatus.CANCELLED


def test_workflow_timeout():
    execution = WorkflowExecution(workflow_id="wf-1", status=WorkflowExecutionStatus.QUEUED)
    WorkflowStateMachine.transition_workflow(execution, WorkflowCommand.START)
    WorkflowStateMachine.transition_workflow(execution, WorkflowCommand.TIMEOUT)
    assert execution.status == WorkflowExecutionStatus.TIMED_OUT


# =============================================================================
# 2. TASK STATE MACHINE TESTS
# =============================================================================

def test_task_lifecycle_happy_path():
    task = TaskExecution(workflow_execution_id="exec-1", task_key="task_a", agent_id="agent_1")
    assert task.status == TaskExecutionStatus.PENDING
    assert task.attempt_count == 0

    # PENDING -> READY
    WorkflowStateMachine.transition_task(task, TaskCommand.READY)
    assert task.status == TaskExecutionStatus.READY

    # READY -> RUNNING (attempt increments)
    WorkflowStateMachine.transition_task(task, TaskCommand.DISPATCH)
    assert task.status == TaskExecutionStatus.RUNNING
    assert task.attempt_count == 1

    # RUNNING -> COMPLETED
    WorkflowStateMachine.transition_task(task, TaskCommand.COMPLETE)
    assert task.status == TaskExecutionStatus.COMPLETED


def test_task_blocking_and_unblocking():
    task = TaskExecution(workflow_execution_id="exec-1", task_key="task_b", agent_id="agent_1")
    
    # PENDING -> BLOCKED
    WorkflowStateMachine.transition_task(task, TaskCommand.BLOCK)
    assert task.status == TaskExecutionStatus.BLOCKED

    # BLOCKED -> READY
    WorkflowStateMachine.transition_task(task, TaskCommand.READY)
    assert task.status == TaskExecutionStatus.READY


def test_task_retry_within_bounds():
    task = TaskExecution(workflow_execution_id="exec-1", task_key="task_c", agent_id="agent_1")
    WorkflowStateMachine.transition_task(task, TaskCommand.READY)
    WorkflowStateMachine.transition_task(task, TaskCommand.DISPATCH)  # attempt = 1
    assert task.attempt_count == 1

    # RUNNING -> READY (retry)
    WorkflowStateMachine.transition_task(task, TaskCommand.RETRY, max_retries=3)
    assert task.status == TaskExecutionStatus.READY

    # Re-dispatch (attempt = 2)
    WorkflowStateMachine.transition_task(task, TaskCommand.DISPATCH)
    assert task.attempt_count == 2


def test_task_retry_exhaustion_guard():
    task = TaskExecution(workflow_execution_id="exec-1", task_key="task_d", agent_id="agent_1")
    task.attempt_count = 3  # already at max retries
    task.status = TaskExecutionStatus.RUNNING

    # Invariant: Cannot retry beyond max_retries
    with pytest.raises(StateTransitionError, match="Retry limit exhausted"):
        WorkflowStateMachine.transition_task(task, TaskCommand.RETRY, max_retries=3)


def test_task_human_approval_flow():
    task = TaskExecution(workflow_execution_id="exec-1", task_key="task_eval", agent_id="agent_1")
    WorkflowStateMachine.transition_task(task, TaskCommand.READY)
    WorkflowStateMachine.transition_task(task, TaskCommand.DISPATCH)

    # RUNNING -> WAITING_APPROVAL
    WorkflowStateMachine.transition_task(task, TaskCommand.REQUIRE_APPROVAL)
    assert task.status == TaskExecutionStatus.WAITING_APPROVAL

    # WAITING_APPROVAL -> COMPLETED (Approve)
    WorkflowStateMachine.transition_task(task, TaskCommand.APPROVE)
    assert task.status == TaskExecutionStatus.COMPLETED


def test_task_human_rejection_and_escalation():
    task = TaskExecution(workflow_execution_id="exec-1", task_key="task_eval", agent_id="agent_1")
    WorkflowStateMachine.transition_task(task, TaskCommand.READY)
    WorkflowStateMachine.transition_task(task, TaskCommand.DISPATCH)
    WorkflowStateMachine.transition_task(task, TaskCommand.REQUIRE_APPROVAL)

    # WAITING_APPROVAL -> ESCALATED (Reject)
    WorkflowStateMachine.transition_task(task, TaskCommand.REJECT)
    assert task.status == TaskExecutionStatus.ESCALATED

    # ESCALATED -> READY (Operator re-queues)
    WorkflowStateMachine.transition_task(task, TaskCommand.RETRY, max_retries=5)
    assert task.status == TaskExecutionStatus.READY


def test_task_terminal_state_protection():
    task = TaskExecution(workflow_execution_id="exec-1", task_key="task_term", agent_id="agent_1")
    WorkflowStateMachine.transition_task(task, TaskCommand.READY)
    WorkflowStateMachine.transition_task(task, TaskCommand.DISPATCH)
    WorkflowStateMachine.transition_task(task, TaskCommand.COMPLETE)

    # Invariant: Terminal task cannot transition
    with pytest.raises(StateTransitionError, match="terminal state 'COMPLETED'"):
        WorkflowStateMachine.transition_task(task, TaskCommand.DISPATCH)


def test_invalid_task_transition_rejected():
    task = TaskExecution(workflow_execution_id="exec-1", task_key="task_inv", agent_id="agent_1")
    # Cannot jump directly from PENDING to COMPLETED
    with pytest.raises(StateTransitionError, match="Illegal task transition"):
        WorkflowStateMachine.transition_task(task, TaskCommand.COMPLETE)


# =============================================================================
# 3. DAG DEPENDENCY VALIDATION & TOPOLOGICAL RESOLUTION TESTS
# =============================================================================

def test_valid_dag_topological_sort():
    tasks = [
        TaskSpec(task_key="planner", name="Planner", agent_id="planner_agent", depends_on=[]),
        TaskSpec(task_key="research_a", name="Research A", agent_id="researcher_agent", depends_on=["planner"]),
        TaskSpec(task_key="research_b", name="Research B", agent_id="researcher_agent", depends_on=["planner"]),
        TaskSpec(task_key="synthesizer", name="Synthesizer", agent_id="synthesizer_agent", depends_on=["research_a", "research_b"]),
    ]
    wf = WorkflowSpec(
        name="test_dag",
        version=1,
        description="Test DAG",
        input_schema={},
        output_schema={},
        tasks=tasks,
    )
    order = DependencyResolver.validate_workflow_graph(wf)
    assert order[0] == "planner"
    assert "research_a" in order[1:3]
    assert "research_b" in order[1:3]
    assert order[3] == "synthesizer"


def test_dag_circular_dependency_rejected():
    # Circular: A -> B -> C -> A
    tasks = [
        TaskSpec(task_key="node_a", name="A", agent_id="agent", depends_on=["node_c"]),
        TaskSpec(task_key="node_b", name="B", agent_id="agent", depends_on=["node_a"]),
        TaskSpec(task_key="node_c", name="C", agent_id="agent", depends_on=["node_b"]),
    ]
    wf = WorkflowSpec(name="cyclic_wf", version=1, description="Cyclic", input_schema={}, output_schema={}, tasks=tasks)
    with pytest.raises(CyclicDependencyError, match="Circular dependency detected"):
        DependencyResolver.validate_workflow_graph(wf)


def test_dag_self_dependency_rejected():
    tasks = [
        TaskSpec(task_key="self_dep", name="Self Dep", agent_id="agent", depends_on=["self_dep"]),
    ]
    wf = WorkflowSpec(name="self_wf", version=1, description="Self", input_schema={}, output_schema={}, tasks=tasks)
    with pytest.raises(WorkflowValidationError, match="self-dependency on itself"):
        DependencyResolver.validate_workflow_graph(wf)


def test_dag_missing_dependency_rejected():
    tasks = [
        TaskSpec(task_key="node_x", name="X", agent_id="agent", depends_on=["non_existent_task"]),
    ]
    wf = WorkflowSpec(name="missing_wf", version=1, description="Missing", input_schema={}, output_schema={}, tasks=tasks)
    with pytest.raises(WorkflowValidationError, match="depends on non-existent task"):
        DependencyResolver.validate_workflow_graph(wf)


def test_dag_duplicate_task_keys_rejected():
    tasks = [
        TaskSpec(task_key="dup_key", name="Task 1", agent_id="agent", depends_on=[]),
        TaskSpec(task_key="dup_key", name="Task 2", agent_id="agent", depends_on=[]),
    ]
    wf = WorkflowSpec(name="dup_wf", version=1, description="Dup", input_schema={}, output_schema={}, tasks=tasks)
    with pytest.raises(WorkflowValidationError, match="Duplicate task_key 'dup_key'"):
        DependencyResolver.validate_workflow_graph(wf)


def test_get_ready_tasks_resolution():
    task_p = TaskSpec(task_key="planner", name="Planner", agent_id="planner_agent", depends_on=[])
    task_a = TaskSpec(task_key="research_a", name="Research A", agent_id="researcher_agent", depends_on=["planner"])
    task_b = TaskSpec(task_key="research_b", name="Research B", agent_id="researcher_agent", depends_on=["planner"])
    
    wf = WorkflowSpec(
        name="branch_wf",
        version=1,
        description="Branch",
        input_schema={},
        output_schema={},
        tasks=[task_p, task_a, task_b],
    )

    # At start: planner is ready
    ready = DependencyResolver.get_ready_tasks(wf, completed_task_keys=set(), active_or_pending_task_keys=set())
    assert len(ready) == 1
    assert ready[0].task_key == "planner"

    # Once planner completed: research_a and research_b are ready
    ready_after = DependencyResolver.get_ready_tasks(
        wf,
        completed_task_keys={"planner"},
        active_or_pending_task_keys={"planner"},
    )
    ready_keys = [t.task_key for t in ready_after]
    assert len(ready_keys) == 2
    assert "research_a" in ready_keys
    assert "research_b" in ready_keys
