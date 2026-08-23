"""Explicit, deterministic state machine for Workflow and Task execution lifecycles."""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional, Set, Tuple
from ..domain.models.execution import (
    WorkflowExecution,
    WorkflowExecutionStatus,
    TaskExecution,
    TaskExecutionStatus,
)
from ..domain.models.workflow import TaskSpec, WorkflowSpec
from ..core.exceptions import StateTransitionError


class WorkflowCommand(str, Enum):
    """Commands triggering Workflow state transitions."""
    START = "START"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    COMPLETE = "COMPLETE"
    FAIL = "FAIL"
    CANCEL = "CANCEL"
    TIMEOUT = "TIMEOUT"


class TaskCommand(str, Enum):
    """Commands triggering Task state transitions."""
    BLOCK = "BLOCK"
    READY = "READY"
    DISPATCH = "DISPATCH"
    COMPLETE = "COMPLETE"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    RETRY = "RETRY"
    FAIL = "FAIL"
    TIMEOUT = "TIMEOUT"
    CANCEL = "CANCEL"


@dataclass(frozen=True)
class WorkflowTransitionRule:
    from_status: WorkflowExecutionStatus
    command: WorkflowCommand
    to_status: WorkflowExecutionStatus
    description: str


@dataclass(frozen=True)
class TaskTransitionRule:
    from_status: TaskExecutionStatus
    command: TaskCommand
    to_status: TaskExecutionStatus
    description: str


class WorkflowStateMachine:
    """
    Pure domain state machine governing WorkflowExecution and TaskExecution lifecycles.
    Enforces deterministic state transitions, guard conditions, and terminal immutability.
    """

    # Terminal state definitions
    WORKFLOW_TERMINAL_STATES: Set[WorkflowExecutionStatus] = {
        WorkflowExecutionStatus.COMPLETED,
        WorkflowExecutionStatus.FAILED,
        WorkflowExecutionStatus.CANCELLED,
        WorkflowExecutionStatus.TIMED_OUT,
    }

    TASK_TERMINAL_STATES: Set[TaskExecutionStatus] = {
        TaskExecutionStatus.COMPLETED,
        TaskExecutionStatus.FAILED,
        TaskExecutionStatus.CANCELLED,
        TaskExecutionStatus.TIMED_OUT,
    }

    # Declarative Workflow Transition Map: (from_status, command) -> (to_status, description)
    _WORKFLOW_TRANSITIONS: Dict[Tuple[WorkflowExecutionStatus, WorkflowCommand], WorkflowTransitionRule] = {
        (WorkflowExecutionStatus.QUEUED, WorkflowCommand.START): WorkflowTransitionRule(
            WorkflowExecutionStatus.QUEUED, WorkflowCommand.START, WorkflowExecutionStatus.RUNNING,
            "Workflow execution dispatched to active scheduler"
        ),
        (WorkflowExecutionStatus.QUEUED, WorkflowCommand.CANCEL): WorkflowTransitionRule(
            WorkflowExecutionStatus.QUEUED, WorkflowCommand.CANCEL, WorkflowExecutionStatus.CANCELLED,
            "Workflow cancelled before starting execution"
        ),
        (WorkflowExecutionStatus.RUNNING, WorkflowCommand.PAUSE): WorkflowTransitionRule(
            WorkflowExecutionStatus.RUNNING, WorkflowCommand.PAUSE, WorkflowExecutionStatus.PAUSED,
            "Workflow paused awaiting human intervention or approval"
        ),
        (WorkflowExecutionStatus.RUNNING, WorkflowCommand.COMPLETE): WorkflowTransitionRule(
            WorkflowExecutionStatus.RUNNING, WorkflowCommand.COMPLETE, WorkflowExecutionStatus.COMPLETED,
            "All terminal tasks completed successfully"
        ),
        (WorkflowExecutionStatus.RUNNING, WorkflowCommand.FAIL): WorkflowTransitionRule(
            WorkflowExecutionStatus.RUNNING, WorkflowCommand.FAIL, WorkflowExecutionStatus.FAILED,
            "One or more critical tasks failed unrecoverably"
        ),
        (WorkflowExecutionStatus.RUNNING, WorkflowCommand.CANCEL): WorkflowTransitionRule(
            WorkflowExecutionStatus.RUNNING, WorkflowCommand.CANCEL, WorkflowExecutionStatus.CANCELLED,
            "Workflow cancelled by user or operator"
        ),
        (WorkflowExecutionStatus.RUNNING, WorkflowCommand.TIMEOUT): WorkflowTransitionRule(
            WorkflowExecutionStatus.RUNNING, WorkflowCommand.TIMEOUT, WorkflowExecutionStatus.TIMED_OUT,
            "Workflow wall-clock duration exceeded maximum limit"
        ),
        (WorkflowExecutionStatus.PAUSED, WorkflowCommand.RESUME): WorkflowTransitionRule(
            WorkflowExecutionStatus.PAUSED, WorkflowCommand.RESUME, WorkflowExecutionStatus.RUNNING,
            "Workflow resumed after approval or intervention"
        ),
        (WorkflowExecutionStatus.PAUSED, WorkflowCommand.CANCEL): WorkflowTransitionRule(
            WorkflowExecutionStatus.PAUSED, WorkflowCommand.CANCEL, WorkflowExecutionStatus.CANCELLED,
            "Paused workflow cancelled by user or operator"
        ),
    }

    # Declarative Task Transition Map: (from_status, command) -> (to_status, description)
    _TASK_TRANSITIONS: Dict[Tuple[TaskExecutionStatus, TaskCommand], TaskTransitionRule] = {
        (TaskExecutionStatus.PENDING, TaskCommand.BLOCK): TaskTransitionRule(
            TaskExecutionStatus.PENDING, TaskCommand.BLOCK, TaskExecutionStatus.BLOCKED,
            "Task blocked awaiting upstream dependencies"
        ),
        (TaskExecutionStatus.PENDING, TaskCommand.READY): TaskTransitionRule(
            TaskExecutionStatus.PENDING, TaskCommand.READY, TaskExecutionStatus.READY,
            "Dependencies satisfied; task ready for worker pool"
        ),
        (TaskExecutionStatus.BLOCKED, TaskCommand.READY): TaskTransitionRule(
            TaskExecutionStatus.BLOCKED, TaskCommand.READY, TaskExecutionStatus.READY,
            "All upstream tasks completed; unblocking task"
        ),
        (TaskExecutionStatus.BLOCKED, TaskCommand.FAIL): TaskTransitionRule(
            TaskExecutionStatus.BLOCKED, TaskCommand.FAIL, TaskExecutionStatus.FAILED,
            "Upstream dependency failed permanently; task cascaded to failure"
        ),
        (TaskExecutionStatus.BLOCKED, TaskCommand.CANCEL): TaskTransitionRule(
            TaskExecutionStatus.BLOCKED, TaskCommand.CANCEL, TaskExecutionStatus.CANCELLED,
            "Workflow cancelled; blocked task cancelled"
        ),
        (TaskExecutionStatus.READY, TaskCommand.DISPATCH): TaskTransitionRule(
            TaskExecutionStatus.READY, TaskCommand.DISPATCH, TaskExecutionStatus.RUNNING,
            "Task acquired by worker and execution started"
        ),
        (TaskExecutionStatus.READY, TaskCommand.CANCEL): TaskTransitionRule(
            TaskExecutionStatus.READY, TaskCommand.CANCEL, TaskExecutionStatus.CANCELLED,
            "Workflow cancelled; ready task cancelled"
        ),
        (TaskExecutionStatus.RUNNING, TaskCommand.COMPLETE): TaskTransitionRule(
            TaskExecutionStatus.RUNNING, TaskCommand.COMPLETE, TaskExecutionStatus.COMPLETED,
            "Agent executed successfully and output contract verified"
        ),
        (TaskExecutionStatus.RUNNING, TaskCommand.REQUIRE_APPROVAL): TaskTransitionRule(
            TaskExecutionStatus.RUNNING, TaskCommand.REQUIRE_APPROVAL, TaskExecutionStatus.WAITING_APPROVAL,
            "Task output valid; entering human approval gate"
        ),
        (TaskExecutionStatus.RUNNING, TaskCommand.RETRY): TaskTransitionRule(
            TaskExecutionStatus.RUNNING, TaskCommand.RETRY, TaskExecutionStatus.READY,
            "Transient failure detected; task re-queued for retry"
        ),
        (TaskExecutionStatus.RUNNING, TaskCommand.FAIL): TaskTransitionRule(
            TaskExecutionStatus.RUNNING, TaskCommand.FAIL, TaskExecutionStatus.FAILED,
            "Fatal failure or retries exhausted"
        ),
        (TaskExecutionStatus.RUNNING, TaskCommand.TIMEOUT): TaskTransitionRule(
            TaskExecutionStatus.RUNNING, TaskCommand.TIMEOUT, TaskExecutionStatus.TIMED_OUT,
            "Task duration exceeded timeout limit"
        ),
        (TaskExecutionStatus.RUNNING, TaskCommand.CANCEL): TaskTransitionRule(
            TaskExecutionStatus.RUNNING, TaskCommand.CANCEL, TaskExecutionStatus.CANCELLED,
            "Task execution cancelled"
        ),
        (TaskExecutionStatus.WAITING_APPROVAL, TaskCommand.APPROVE): TaskTransitionRule(
            TaskExecutionStatus.WAITING_APPROVAL, TaskCommand.APPROVE, TaskExecutionStatus.COMPLETED,
            "Human operator approved task output"
        ),
        (TaskExecutionStatus.WAITING_APPROVAL, TaskCommand.REJECT): TaskTransitionRule(
            TaskExecutionStatus.WAITING_APPROVAL, TaskCommand.REJECT, TaskExecutionStatus.ESCALATED,
            "Human operator rejected task output; routed to escalation"
        ),
        (TaskExecutionStatus.WAITING_APPROVAL, TaskCommand.TIMEOUT): TaskTransitionRule(
            TaskExecutionStatus.WAITING_APPROVAL, TaskCommand.TIMEOUT, TaskExecutionStatus.TIMED_OUT,
            "Approval SLA expired"
        ),
        (TaskExecutionStatus.WAITING_APPROVAL, TaskCommand.CANCEL): TaskTransitionRule(
            TaskExecutionStatus.WAITING_APPROVAL, TaskCommand.CANCEL, TaskExecutionStatus.CANCELLED,
            "Workflow cancelled while awaiting approval"
        ),
        (TaskExecutionStatus.ESCALATED, TaskCommand.RETRY): TaskTransitionRule(
            TaskExecutionStatus.ESCALATED, TaskCommand.RETRY, TaskExecutionStatus.READY,
            "Escalated task reset for retry by operator"
        ),
        (TaskExecutionStatus.ESCALATED, TaskCommand.FAIL): TaskTransitionRule(
            TaskExecutionStatus.ESCALATED, TaskCommand.FAIL, TaskExecutionStatus.FAILED,
            "Escalated task permanently marked as failed"
        ),
        (TaskExecutionStatus.ESCALATED, TaskCommand.CANCEL): TaskTransitionRule(
            TaskExecutionStatus.ESCALATED, TaskCommand.CANCEL, TaskExecutionStatus.CANCELLED,
            "Workflow cancelled; escalated task cancelled"
        ),
    }

    # =========================================================================
    # WORKFLOW TRANSITION API
    # =========================================================================

    @classmethod
    def transition_workflow(
        cls,
        execution: WorkflowExecution,
        command: WorkflowCommand,
        reason: Optional[str] = None,
    ) -> WorkflowExecutionStatus:
        """
        Validates and transitions a WorkflowExecution to a new status.
        Raises StateTransitionError if the transition is illegal or violates guards.
        """
        current_status = execution.status

        # Invariant 1: Terminal states are immutable
        if current_status in cls.WORKFLOW_TERMINAL_STATES:
            raise StateTransitionError(
                f"Cannot execute command '{command.value}' on workflow in terminal state '{current_status.value}'."
            )

        key = (current_status, command)
        rule = cls._WORKFLOW_TRANSITIONS.get(key)
        if not rule:
            raise StateTransitionError(
                f"Illegal workflow transition: Cannot apply command '{command.value}' from status '{current_status.value}'."
            )

        execution.status = rule.to_status
        return rule.to_status

    # =========================================================================
    # TASK TRANSITION API
    # =========================================================================

    @classmethod
    def transition_task(
        cls,
        task_execution: TaskExecution,
        command: TaskCommand,
        max_retries: int = 3,
        reason: Optional[str] = None,
    ) -> TaskExecutionStatus:
        """
        Validates and transitions a TaskExecution to a new status.
        Enforces retry count guards, terminal protection, and state invariants.
        Raises StateTransitionError if the transition is illegal or violates guards.
        """
        current_status = task_execution.status

        # Invariant 1: Terminal states cannot transition (unless explicitly re-triggered)
        if current_status in cls.TASK_TERMINAL_STATES:
            raise StateTransitionError(
                f"Cannot execute command '{command.value}' on task '{task_execution.task_key}' in terminal state '{current_status.value}'."
            )

        # Invariant 2: Retry bounds guard (attempt_count > max_retries)
        # Note: attempt_count represents total execution attempts (1 = first run, 2 = 1st retry, etc.)
        # If attempt_count > max_retries, all allowed retries have been exhausted.
        if command == TaskCommand.RETRY:
            if task_execution.attempt_count > max_retries:
                raise StateTransitionError(
                    f"Retry limit exhausted for task '{task_execution.task_key}'. "
                    f"Execution attempts ({task_execution.attempt_count}) exceeded max_retries ({max_retries})."
                )

        key = (current_status, command)
        rule = cls._TASK_TRANSITIONS.get(key)
        if not rule:
            raise StateTransitionError(
                f"Illegal task transition: Cannot apply command '{command.value}' to task '{task_execution.task_key}' from status '{current_status.value}'."
            )

        # Invariant 3: Increment attempt count on dispatch
        if command == TaskCommand.DISPATCH:
            task_execution.attempt_count += 1

        task_execution.status = rule.to_status
        return rule.to_status
