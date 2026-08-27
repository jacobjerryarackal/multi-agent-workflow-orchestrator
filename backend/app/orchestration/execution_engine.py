"""Production-grade multi-agent workflow execution engine with quality evaluation and bounded revision loops."""

import asyncio
from datetime import datetime, timezone
import hashlib
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

from ..core.exceptions import (
    AgentNotFoundError,
    ArtifactIntegrityError,
    OrchestratorException,
    StateTransitionError,
    WorkflowNotFoundError,
    WorkflowValidationError,
)
from ..core.telemetry import telemetry
from ..domain.interfaces.evaluation_provider import EvaluationProvider
from ..domain.interfaces.repository import (
    ArtifactRepository,
    EventRepository,
    ExecutionRepository,
    WorkflowRepository,
)
from ..domain.models.agent import AgentExecutionContext, AgentResult, ProducedArtifact
from ..domain.models.artifact import Artifact, ArtifactType
from ..domain.models.evaluation import (
    EvaluationRequest,
    EvaluationResult,
    EvaluationVerdict,
    RevisionContext,
)
from ..domain.models.event import EventType, WorkflowEvent
from ..domain.models.execution import (
    TaskExecution,
    TaskExecutionStatus,
    WorkflowExecution,
    WorkflowExecutionStatus,
)
from ..domain.models.workflow import TaskSpec, WorkflowSpec
from ..agents.registry import AgentRegistry
from ..evaluators.composite import CompositeQualityEvaluator
from .dependency_resolver import DependencyResolver
from .state_machine import TaskCommand, WorkflowCommand, WorkflowStateMachine

logger = structlog.get_logger(__name__)


class WorkflowExecutionEngine:
    """
    Core orchestrator responsible for end-to-end multi-agent workflow execution:
    - DAG task dependency resolution
    - Atomic task locking and claiming (PostgreSQL row-level locking)
    - Input mapping and artifact passing across tasks
    - Agent discovery and parallel bounded execution
    - Layered quality evaluation (Deterministic + Semantic LLM)
    - Bounded optimization and revision cycles
    - Failure handling, backoff retries, and failure propagation
    - Append-only event auditing and terminal state finalization
    - Stale task lease recovery and resume
    """

    def __init__(
        self,
        workflow_repo: WorkflowRepository,
        execution_repo: ExecutionRepository,
        event_repo: EventRepository,
        artifact_repo: ArtifactRepository,
        agent_registry: AgentRegistry,
        evaluator: Optional[EvaluationProvider] = None,
    ):
        self.workflow_repo = workflow_repo
        self.execution_repo = execution_repo
        self.event_repo = event_repo
        self.artifact_repo = artifact_repo
        self.agent_registry = agent_registry
        self.evaluator = evaluator or CompositeQualityEvaluator()
        self._session_lock = asyncio.Lock()

    async def submit_workflow(
        self,
        workflow_id: str,
        initial_inputs: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        trigger_type: str = "manual",
    ) -> WorkflowExecution:
        """
        Submits and initializes a workflow execution record from a registered WorkflowSpec.
        Validates the DAG structure, creates task execution placeholders, and persists the record.
        """
        async with self._session_lock:
            workflow = await self.workflow_repo.get_workflow_spec(workflow_id)
            if not workflow:
                raise WorkflowNotFoundError(f"Workflow with ID '{workflow_id}' does not exist.")

            # 1. Validate DAG graph topology
            DependencyResolver.validate_workflow_graph(workflow)

            # 2. Check idempotency if key is provided
            if idempotency_key:
                existing = await self.execution_repo.get_workflow_execution_by_idempotency_key(
                    workflow_id, idempotency_key
                )
                if existing:
                    logger.info(
                        "Idempotent workflow execution reused",
                        workflow_id=workflow_id,
                        execution_id=existing.id,
                        idempotency_key=idempotency_key,
                    )
                    return existing

            # 3. Create WorkflowExecution domain entity
            execution = WorkflowExecution(
                workflow_id=workflow_id,
                status=WorkflowExecutionStatus.QUEUED,
                trigger_type=trigger_type,
                idempotency_key=idempotency_key,
                initial_inputs=initial_inputs,
            )

            # 4. Initialize task executions
            for task_spec in workflow.tasks:
                initial_task_status = (
                    TaskExecutionStatus.READY
                    if not task_spec.depends_on
                    else TaskExecutionStatus.BLOCKED
                )
                task_exec = TaskExecution(
                    workflow_execution_id=execution.id,
                    task_key=task_spec.task_key,
                    agent_id=task_spec.agent_id,
                    status=initial_task_status,
                    attempt_count=0,
                    revision_count=0,
                )
                execution.tasks[task_spec.task_key] = task_exec

            # 5. Persist workflow execution
            saved_execution = await self.execution_repo.create_workflow_execution(execution)

        # Record submission telemetry metric
        telemetry.increment_counter(
            "workflow_submissions_total",
            value=1.0,
            labels={"trigger_type": trigger_type},
        )

        # 6. Audit event (only for newly created execution)
        if saved_execution.id == execution.id:
            await self._emit_event(
                execution_id=saved_execution.id,
                workflow_id=workflow_id,
                event_type=EventType.WORKFLOW_STARTED,
                payload={"initial_inputs": initial_inputs, "task_count": len(workflow.tasks)},
            )

        logger.info(
            "Workflow execution submitted",
            workflow_id=workflow_id,
            execution_id=saved_execution.id,
        )
        return saved_execution

    async def run_to_completion(
        self,
        execution_id: str,
        max_poll_cycles: int = 100,
        poll_interval_seconds: float = 0.01,
    ) -> WorkflowExecution:
        """
        Drives the execution loop until the workflow reaches a terminal state
        or pauses on a human approval / external gate.
        """
        async with self._session_lock:
            execution = await self.execution_repo.get_workflow_execution(execution_id)
            if not execution:
                raise WorkflowNotFoundError(f"Execution '{execution_id}' not found.")

            workflow = await self.workflow_repo.get_workflow_spec(execution.workflow_id)
            if not workflow:
                raise WorkflowNotFoundError(f"Workflow '{execution.workflow_id}' not found.")

            # Transition workflow to RUNNING if still QUEUED
            if execution.status == WorkflowExecutionStatus.QUEUED:
                WorkflowStateMachine.transition_workflow(execution, WorkflowCommand.START)
                execution = await self.execution_repo.update_workflow_execution(execution)
                telemetry.increment_counter("workflow_started_total", value=1.0)

        task_spec_map = {t.task_key: t for t in workflow.tasks}

        cycles = 0
        start_time = time.perf_counter()

        while cycles < max_poll_cycles:
            cycles += 1
            # If workflow entered terminal state or paused, break
            if execution.status in (
                WorkflowExecutionStatus.COMPLETED,
                WorkflowExecutionStatus.FAILED,
                WorkflowExecutionStatus.CANCELLED,
                WorkflowExecutionStatus.TIMED_OUT,
                WorkflowExecutionStatus.PAUSED,
            ):
                break

            # 1. Global Workflow Timeout Check
            elapsed_seconds = time.perf_counter() - start_time
            if elapsed_seconds > workflow.max_workflow_duration_seconds:
                async with self._session_lock:
                    WorkflowStateMachine.transition_workflow(execution, WorkflowCommand.TIMEOUT)
                    # pyrefly: ignore [deprecated]
                    execution.completed_at = datetime.utcnow()
                    execution.error_summary = f"Workflow exceeded maximum duration of {workflow.max_workflow_duration_seconds}s."
                    await self.execution_repo.update_workflow_execution(execution)
                telemetry.increment_counter(
                    "workflow_failed_total",
                    value=1.0,
                    labels={"error_category": "timeout"},
                )
                telemetry.observe_histogram(
                    "workflow_duration_seconds",
                    value=elapsed_seconds,
                )
                await self._emit_event(
                    execution_id=execution.id,
                    workflow_id=workflow.id,
                    event_type=EventType.WORKFLOW_TIMED_OUT,
                    payload={"duration_seconds": elapsed_seconds},
                )
                break

            # Refresh execution state from database
            async with self._session_lock:
                latest_execution = await self.execution_repo.get_workflow_execution(execution_id)
                if latest_execution:
                    execution = latest_execution

            # 2. Update task statuses based on DAG dependency resolution
            completed_keys = {
                k for k, t in execution.tasks.items() if t.status == TaskExecutionStatus.COMPLETED
            }
            failed_keys = {
                k for k, t in execution.tasks.items() if t.status in (TaskExecutionStatus.FAILED, TaskExecutionStatus.TIMED_OUT)
            }

            async with self._session_lock:
                # Unblock blocked tasks whose dependencies are fully met
                for task_key, task_exec in execution.tasks.items():
                    if task_exec.status == TaskExecutionStatus.BLOCKED:
                        spec = task_spec_map[task_key]
                        if set(spec.depends_on).issubset(completed_keys):
                            WorkflowStateMachine.transition_task(task_exec, TaskCommand.READY)
                            await self.execution_repo.update_task_execution(task_exec)
                        elif any(dep in failed_keys for dep in spec.depends_on):
                            # Upstream failure cascade -> fail downstream task
                            WorkflowStateMachine.transition_task(task_exec, TaskCommand.FAIL)
                            task_exec.error_details = {
                                "reason": "Upstream prerequisite task failed unrecoverably.",
                                "failed_dependencies": [dep for dep in spec.depends_on if dep in failed_keys],
                            }
                            await self.execution_repo.update_task_execution(task_exec)

            # 3. Identify ready tasks to dispatch
            ready_tasks = [
                t for t in execution.tasks.values() if t.status == TaskExecutionStatus.READY
            ]

            if not ready_tasks:
                # Check for active running tasks or waiting intervention
                running_tasks = [
                    t for t in execution.tasks.values() if t.status == TaskExecutionStatus.RUNNING
                ]
                waiting_intervention = [
                    t for t in execution.tasks.values()
                    if t.status in (TaskExecutionStatus.WAITING_APPROVAL, TaskExecutionStatus.ESCALATED)
                ]

                if not running_tasks and not waiting_intervention:
                    # No tasks can make progress. Finalize workflow.
                    await self._finalize_workflow(execution, workflow)
                    break

                if waiting_intervention and not running_tasks:
                    # Workflow is paused waiting on human intervention
                    break

                await asyncio.sleep(poll_interval_seconds)
                continue

            tasks_to_run = ready_tasks[: workflow.max_parallel_tasks]

            # 4. Execute ready tasks concurrently (agents run in parallel outside lock)
            await asyncio.gather(
                *[self._process_single_task(execution, task_spec_map[t.task_key]) for t in tasks_to_run]
            )

        total_duration_ms = int((time.perf_counter() - start_time) * 1000)
        execution.execution_duration_ms = total_duration_ms

        async with self._session_lock:
            final_exec = await self.execution_repo.get_workflow_execution(execution_id)
            return final_exec or execution

    async def _process_single_task(
        self,
        execution: WorkflowExecution,
        task_spec: TaskSpec,
    ) -> None:
        """
        Executes a single task within the workflow execution:
        - Atomic claim via SELECT FOR UPDATE with lease duration
        - Input mapping resolution from initial inputs + upstream outputs + revision context
        - Agent discovery & non-blocking execution (parallel across tasks)
        - Output & artifact persistence
        - Layered Quality Evaluation & Revision Looping
        - State transition & retry handling
        """
        task_key = task_spec.task_key
        lease_duration = task_spec.timeout_seconds + 30

        # 1. Atomic claim (acquires row lock, sets status=RUNNING, increments attempt_count, sets lease)
        async with self._session_lock:
            repo_any: Any = self.execution_repo
            claimed_task = await repo_any.claim_task_for_execution(
                execution.id, task_key, lease_duration_seconds=lease_duration
            )
            if not claimed_task:
                return

            # Build input payload
            input_payload = await self._resolve_task_inputs(execution, task_spec, claimed_task)
            claimed_task.input_data = input_payload
            await self.execution_repo.update_task_execution(claimed_task)
            execution.tasks[task_key] = claimed_task

        telemetry.increment_counter(
            "task_started_total",
            value=1.0,
            labels={"agent_id": task_spec.agent_id},
        )
        telemetry.increment_counter(
            "task_lease_claim_total",
            value=1.0,
            labels={"worker_id": "process_worker"},
        )

        await self._emit_event(
            execution_id=execution.id,
            workflow_id=execution.workflow_id,
            task_key=task_key,
            agent_id=task_spec.agent_id,
            event_type=EventType.TASK_STARTED,
            payload={
                "attempt_count": claimed_task.attempt_count,
                "revision_count": claimed_task.revision_count,
                "lease_duration_seconds": lease_duration,
            },
        )

        # 2. Resolve agent from registry
        try:
            agent = self.agent_registry.get(task_spec.agent_id)
        except AgentNotFoundError as exc:
            async with self._session_lock:
                claimed_task.status = TaskExecutionStatus.FAILED
                claimed_task.error_details = {"error": str(exc), "category": "agent_not_found"}
                await self.execution_repo.update_task_execution(claimed_task)
                execution.tasks[task_key] = claimed_task
            await self._emit_event(
                execution_id=execution.id,
                workflow_id=execution.workflow_id,
                task_key=task_key,
                agent_id=task_spec.agent_id,
                event_type=EventType.TASK_FAILED,
                payload={"error": str(exc)},
            )
            return

        # 3. Construct bounded AgentExecutionContext (isolated context boundary)
        agent_context = AgentExecutionContext(
            workflow_execution_id=execution.id,
            workflow_id=execution.workflow_id,
            task_key=task_key,
            attempt_number=claimed_task.attempt_count,
            input_payload=input_payload,
            timeout_seconds=task_spec.timeout_seconds,
        )

        # 4. Execute agent (non-blocking model I/O runs in parallel without holding session lock)
        agent_result: AgentResult = await agent.execute(agent_context)

        # 5. Handle execution result
        if agent_result.success:
            await self._handle_task_success(execution, claimed_task, task_spec, agent_result)
        else:
            await self._handle_task_failure(execution, claimed_task, task_spec, agent_result)

    async def _handle_task_success(
        self,
        execution: WorkflowExecution,
        task_exec: TaskExecution,
        task_spec: TaskSpec,
        result: AgentResult,
    ) -> None:
        """Handles successful agent output, artifact verification, quality evaluation, and approval gating."""
        task_key = task_spec.task_key
        task_exec.output_data = result.structured_data
        task_exec.token_usage = result.token_metrics.model_dump()
        task_exec.execution_duration_ms = result.execution_duration_ms
        # pyrefly: ignore [deprecated]
        task_exec.completed_at = datetime.utcnow()

        # 1. Persist and verify produced artifacts
        for prod_artifact in result.artifacts:
            computed_checksum = hashlib.sha256(prod_artifact.content_or_uri.encode("utf-8")).hexdigest()
            if prod_artifact.checksum_sha256 != computed_checksum:
                telemetry.increment_counter("artifact_integrity_failure_total", value=1.0)
                task_exec.status = TaskExecutionStatus.FAILED
                task_exec.error_details = {
                    "error": f"Artifact '{prod_artifact.name}' checksum mismatch. Expected {prod_artifact.checksum_sha256}, got {computed_checksum}",
                    "category": "artifact_integrity_failure",
                }
                async with self._session_lock:
                    await self.execution_repo.update_task_execution(task_exec)
                    execution.tasks[task_key] = task_exec
                await self._emit_event(
                    execution_id=execution.id,
                    workflow_id=execution.workflow_id,
                    task_key=task_spec.task_key,
                    agent_id=task_spec.agent_id,
                    event_type=EventType.TASK_FAILED,
                    payload={"error": task_exec.error_details["error"]},
                )
                return

            artifact = Artifact(
                workflow_execution_id=execution.id,
                task_key=task_spec.task_key,
                name=prod_artifact.name,
                artifact_type=ArtifactType(prod_artifact.artifact_type),
                content=prod_artifact.content_or_uri,
                checksum_sha256=prod_artifact.checksum_sha256,
                metadata=prod_artifact.metadata,
            )
            async with self._session_lock:
                await self.artifact_repo.save_artifact(artifact)
            telemetry.increment_counter(
                "artifact_created_total",
                value=1.0,
                labels={"artifact_type": prod_artifact.artifact_type},
            )
            telemetry.increment_counter(
                "artifact_integrity_verified_total",
                value=1.0,
                labels={"status": "valid"},
            )
            await self._emit_event(
                execution_id=execution.id,
                workflow_id=execution.workflow_id,
                task_key=task_spec.task_key,
                agent_id=task_spec.agent_id,
                event_type=EventType.ARTIFACT_PRODUCED,
                payload={"artifact_name": artifact.name, "checksum": artifact.checksum_sha256},
            )

        # 2. Quality Evaluation Gate (if enabled)
        if task_spec.evaluation_gate.enabled:
            eval_gate = task_spec.evaluation_gate
            telemetry.increment_counter(
                "evaluation_started_total",
                value=1.0,
                labels={"evaluator_type": eval_gate.evaluator_name},
            )
            await self._emit_event(
                execution_id=execution.id,
                workflow_id=execution.workflow_id,
                task_key=task_key,
                agent_id=task_spec.agent_id,
                event_type=EventType.EVALUATION_STARTED,
                payload={"revision_count": task_exec.revision_count, "evaluator": eval_gate.evaluator_name},
            )

            eval_request = EvaluationRequest(
                workflow_execution_id=execution.id,
                task_key=task_key,
                agent_id=task_spec.agent_id,
                input_payload=task_exec.input_data,
                output_payload=result.structured_data,
                produced_artifacts=[a.model_dump() for a in result.artifacts],
                evaluation_criteria=eval_gate.criteria,
                min_pass_score=eval_gate.min_pass_score,
                current_revision=task_exec.revision_count,
                max_revisions=eval_gate.max_revisions,
            )

            eval_result: EvaluationResult = await self.evaluator.evaluate(eval_request)
            
            telemetry.increment_counter(
                "evaluation_completed_total",
                value=1.0,
                labels={
                    "evaluator_type": eval_gate.evaluator_name,
                    "verdict": eval_result.verdict.value,
                },
            )
            telemetry.observe_histogram(
                "evaluation_duration_seconds",
                value=eval_result.evaluation_duration_ms / 1000.0,
                labels={"evaluator_type": eval_gate.evaluator_name},
            )
            telemetry.observe_histogram(
                "evaluation_score",
                value=eval_result.score,
                labels={"evaluator_type": eval_gate.evaluator_name},
            )

            # Save evaluation history in structured audit trail
            task_exec.evaluation_history.append(eval_result.model_dump())

            await self._emit_event(
                execution_id=execution.id,
                workflow_id=execution.workflow_id,
                task_key=task_key,
                agent_id=task_spec.agent_id,
                event_type=EventType.EVALUATION_COMPLETED,
                payload={
                    "verdict": eval_result.verdict.value,
                    "score": eval_result.score,
                    "passed_checks": eval_result.passed_checks,
                    "failed_checks": eval_result.failed_checks,
                    "duration_ms": eval_result.evaluation_duration_ms,
                },
            )

            # Process Evaluation Verdict
            if eval_result.verdict == EvaluationVerdict.PASS:
                await self._emit_event(
                    execution_id=execution.id,
                    workflow_id=execution.workflow_id,
                    task_key=task_key,
                    agent_id=task_spec.agent_id,
                    event_type=EventType.EVALUATION_PASSED,
                    payload={"score": eval_result.score},
                )
                # Proceed to approval or completion
            elif eval_result.verdict == EvaluationVerdict.REQUIRES_REVISION:
                # Check revision budget
                if task_exec.revision_count < eval_gate.max_revisions:
                    WorkflowStateMachine.transition_task(
                        task_exec,
                        TaskCommand.REVISE,
                        max_revisions=eval_gate.max_revisions,
                    )
                    # Construct and attach bounded RevisionContext
                    rev_ctx = RevisionContext(
                        revision_number=task_exec.revision_count,
                        evaluator_verdict=eval_result.verdict,
                        score=eval_result.score,
                        failed_checks=eval_result.failed_checks,
                        required_changes=eval_result.required_changes,
                        actionable_feedback=eval_result.actionable_feedback,
                    )
                    task_exec.input_data["_revision_context"] = rev_ctx.model_dump()
                    async with self._session_lock:
                        await self.execution_repo.update_task_execution(task_exec)
                        execution.tasks[task_key] = task_exec
                    await self._emit_event(
                        execution_id=execution.id,
                        workflow_id=execution.workflow_id,
                        task_key=task_key,
                        agent_id=task_spec.agent_id,
                        event_type=EventType.REVISION_REQUESTED,
                        payload={
                            "revision_number": task_exec.revision_count,
                            "required_changes": eval_result.required_changes,
                            "actionable_feedback": eval_result.actionable_feedback,
                        },
                    )
                    return
                else:
                    # Revision budget exhausted -> apply rejection policy
                    if eval_gate.rejection_policy == "ESCALATE":
                        WorkflowStateMachine.transition_task(task_exec, TaskCommand.ESCALATE)
                        async with self._session_lock:
                            await self.execution_repo.update_task_execution(task_exec)
                            execution.tasks[task_key] = task_exec
                        await self._emit_event(
                            execution_id=execution.id,
                            workflow_id=execution.workflow_id,
                            task_key=task_key,
                            agent_id=task_spec.agent_id,
                            event_type=EventType.EVALUATION_ESCALATED,
                            payload={"reason": "Revision budget exhausted", "rejection_policy": "ESCALATE"},
                        )
                        return
                    else:
                        WorkflowStateMachine.transition_task(task_exec, TaskCommand.FAIL)
                        task_exec.error_details = {
                            "error": "Evaluation revision budget exhausted",
                            "failed_checks": eval_result.failed_checks,
                            "revision_count": task_exec.revision_count,
                        }
                        async with self._session_lock:
                            await self.execution_repo.update_task_execution(task_exec)
                            execution.tasks[task_key] = task_exec
                        await self._emit_event(
                            execution_id=execution.id,
                            workflow_id=execution.workflow_id,
                            task_key=task_key,
                            agent_id=task_spec.agent_id,
                            event_type=EventType.EVALUATION_FAILED,
                            payload={"error": task_exec.error_details["error"]},
                        )
                        return
            elif eval_result.verdict == EvaluationVerdict.ESCALATE:
                WorkflowStateMachine.transition_task(task_exec, TaskCommand.ESCALATE)
                async with self._session_lock:
                    await self.execution_repo.update_task_execution(task_exec)
                    execution.tasks[task_key] = task_exec
                await self._emit_event(
                    execution_id=execution.id,
                    workflow_id=execution.workflow_id,
                    task_key=task_key,
                    agent_id=task_spec.agent_id,
                    event_type=EventType.EVALUATION_ESCALATED,
                    payload={"rationale": eval_result.rationale},
                )
                return
            else:
                # EvaluationVerdict.FAIL
                WorkflowStateMachine.transition_task(task_exec, TaskCommand.FAIL)
                task_exec.error_details = {
                    "error": f"Evaluation rejected task output: {eval_result.rationale}",
                    "failed_checks": eval_result.failed_checks,
                }
                async with self._session_lock:
                    await self.execution_repo.update_task_execution(task_exec)
                    execution.tasks[task_key] = task_exec
                await self._emit_event(
                    execution_id=execution.id,
                    workflow_id=execution.workflow_id,
                    task_key=task_key,
                    agent_id=task_spec.agent_id,
                    event_type=EventType.EVALUATION_FAILED,
                    payload={"error": eval_result.rationale},
                )
                return

        # 3. Check approval gate
        if task_spec.approval_gate.required:
            WorkflowStateMachine.transition_task(task_exec, TaskCommand.REQUIRE_APPROVAL)
            async with self._session_lock:
                await self.execution_repo.update_task_execution(task_exec)
                execution.tasks[task_key] = task_exec
            telemetry.increment_counter("approval_requested_total", value=1.0)
            await self._emit_event(
                execution_id=execution.id,
                workflow_id=execution.workflow_id,
                task_key=task_spec.task_key,
                agent_id=task_spec.agent_id,
                event_type=EventType.TASK_WAITING_APPROVAL,
                payload={"approver_roles": task_spec.approval_gate.approver_roles},
            )
        else:
            WorkflowStateMachine.transition_task(task_exec, TaskCommand.COMPLETE)
            async with self._session_lock:
                await self.execution_repo.update_task_execution(task_exec)
                execution.tasks[task_key] = task_exec
            telemetry.increment_counter(
                "task_completed_total",
                value=1.0,
                labels={"agent_id": task_spec.agent_id},
            )
            telemetry.observe_histogram(
                "task_execution_duration_seconds",
                value=(task_exec.execution_duration_ms or 0) / 1000.0,
                labels={"agent_id": task_spec.agent_id},
            )
            await self._emit_event(
                execution_id=execution.id,
                workflow_id=execution.workflow_id,
                task_key=task_spec.task_key,
                agent_id=task_spec.agent_id,
                event_type=EventType.TASK_COMPLETED,
                payload={"output_keys": list(result.structured_data.keys())},
            )

    async def _handle_task_failure(
        self,
        execution: WorkflowExecution,
        task_exec: TaskExecution,
        task_spec: TaskSpec,
        result: AgentResult,
    ) -> None:
        """Handles task failure, evaluates retry policy, or marks task terminally FAILED."""
        task_key = task_spec.task_key
        task_exec.error_details = {
            "error_message": result.error_message,
            "error_category": result.error_category,
            "attempt": task_exec.attempt_count,
        }
        task_exec.execution_duration_ms = result.execution_duration_ms

        retry_policy = task_spec.retry_policy
        max_retries = max(0, retry_policy.max_attempts - 1)

        # Check retry eligibility (attempt_count <= max_retries)
        if task_exec.attempt_count <= max_retries:
            try:
                WorkflowStateMachine.transition_task(
                    task_exec,
                    TaskCommand.RETRY,
                    max_retries=max_retries,
                )
                async with self._session_lock:
                    await self.execution_repo.update_task_execution(task_exec)
                    execution.tasks[task_key] = task_exec
                telemetry.increment_counter(
                    "task_retry_total",
                    value=1.0,
                    labels={"agent_id": task_spec.agent_id},
                )
                await self._emit_event(
                    execution_id=execution.id,
                    workflow_id=execution.workflow_id,
                    task_key=task_spec.task_key,
                    agent_id=task_spec.agent_id,
                    event_type=EventType.TASK_RETRIED,
                    payload={
                        "attempt": task_exec.attempt_count,
                        "max_retries": max_retries,
                        "error": result.error_message,
                    },
                )
                return
            except StateTransitionError:
                pass

        # Retries exhausted or non-retryable -> mark FAILED
        WorkflowStateMachine.transition_task(task_exec, TaskCommand.FAIL)
        # pyrefly: ignore [deprecated]
        task_exec.completed_at = datetime.utcnow()
        async with self._session_lock:
            await self.execution_repo.update_task_execution(task_exec)
            execution.tasks[task_key] = task_exec
        telemetry.increment_counter(
            "task_failed_total",
            value=1.0,
            labels={
                "agent_id": task_spec.agent_id,
                "error_category": result.error_category or "execution_failure",
            },
        )
        telemetry.observe_histogram(
            "task_execution_duration_seconds",
            value=(task_exec.execution_duration_ms or 0) / 1000.0,
            labels={"agent_id": task_spec.agent_id},
        )
        await self._emit_event(
            execution_id=execution.id,
            workflow_id=execution.workflow_id,
            task_key=task_spec.task_key,
            agent_id=task_spec.agent_id,
            event_type=EventType.TASK_FAILED,
            payload={"error": result.error_message, "attempts": task_exec.attempt_count},
        )

    async def _resolve_task_inputs(
        self,
        execution: WorkflowExecution,
        task_spec: TaskSpec,
        task_exec: Optional[TaskExecution] = None,
    ) -> Dict[str, Any]:
        """
        Builds the input dictionary for a task by combining:
        1. Static inputs defined on TaskSpec
        2. Global initial workflow inputs
        3. Upstream task output mappings defined in input_mappings
        4. Injected _revision_context if executing a revision cycle
        """
        resolved: Dict[str, Any] = {}
        resolved.update(task_spec.static_inputs)

        # Merge matching workflow initial inputs
        for k, v in execution.initial_inputs.items():
            if k not in resolved:
                resolved[k] = v

        # Map upstream outputs: e.g. {"research_findings": "research_task.findings"}
        for target_key, source_expr in task_spec.input_mappings.items():
            if "." in source_expr:
                src_task, src_field = source_expr.split(".", 1)
                if src_task in execution.tasks:
                    upstream_output = execution.tasks[src_task].output_data
                    if src_field in upstream_output:
                        resolved[target_key] = upstream_output[src_field]
            else:
                if source_expr in execution.tasks:
                    resolved[target_key] = execution.tasks[source_expr].output_data

        # Preserve revision context if present on task_exec
        if task_exec and "_revision_context" in task_exec.input_data:
            resolved["_revision_context"] = task_exec.input_data["_revision_context"]

        return resolved

    async def _finalize_workflow(
        self,
        execution: WorkflowExecution,
        workflow: WorkflowSpec,
    ) -> None:
        """Determines terminal workflow state (COMPLETED or FAILED) and computes final outputs."""
        all_tasks = execution.tasks.values()
        is_all_completed = all(t.status == TaskExecutionStatus.COMPLETED for t in all_tasks)
        has_any_failed = any(t.status in (TaskExecutionStatus.FAILED, TaskExecutionStatus.TIMED_OUT) for t in all_tasks)

        total_duration_sec = (execution.execution_duration_ms or 0) / 1000.0

        if is_all_completed:
            WorkflowStateMachine.transition_workflow(execution, WorkflowCommand.COMPLETE)
            # pyrefly: ignore [deprecated]
            execution.completed_at = datetime.utcnow()
            
            # Aggregate final outputs from leaf nodes
            final_outputs: Dict[str, Any] = {}
            for t in all_tasks:
                final_outputs[t.task_key] = t.output_data
            execution.final_outputs = final_outputs

            async with self._session_lock:
                await self.execution_repo.update_workflow_execution(execution)
            telemetry.increment_counter("workflow_completed_total", value=1.0)
            telemetry.observe_histogram("workflow_duration_seconds", value=total_duration_sec)
            await self._emit_event(
                execution_id=execution.id,
                workflow_id=workflow.id,
                event_type=EventType.WORKFLOW_COMPLETED,
                payload={"total_tasks": len(all_tasks)},
            )
            logger.info("Workflow execution completed successfully", execution_id=execution.id)
        elif has_any_failed:
            WorkflowStateMachine.transition_workflow(execution, WorkflowCommand.FAIL)
            # pyrefly: ignore [deprecated]
            execution.completed_at = datetime.utcnow()
            execution.error_summary = "One or more critical tasks failed unrecoverably."
            async with self._session_lock:
                await self.execution_repo.update_workflow_execution(execution)
            telemetry.increment_counter(
                "workflow_failed_total",
                value=1.0,
                labels={"error_category": "task_failure"},
            )
            telemetry.observe_histogram("workflow_duration_seconds", value=total_duration_sec)
            await self._emit_event(
                execution_id=execution.id,
                workflow_id=workflow.id,
                event_type=EventType.WORKFLOW_FAILED,
                payload={"error": execution.error_summary},
            )
            logger.warning("Workflow execution failed", execution_id=execution.id)

    async def _emit_event(
        self,
        execution_id: str,
        workflow_id: str,
        event_type: EventType,
        payload: Dict[str, Any],
        task_key: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> None:
        """Appends an immutable telemetry event to the EventRepository."""
        event = WorkflowEvent(
            workflow_execution_id=execution_id,
            workflow_id=workflow_id,
            task_key=task_key,
            agent_id=agent_id,
            event_type=event_type,
            payload=payload,
            actor="orchestration_engine",
        )
        async with self._session_lock:
            await self.event_repo.append_event(event)

    async def recover_stale_tasks(self, now: Optional[datetime] = None) -> int:
        """
        Scans for RUNNING tasks whose lease has expired.
        Reclaims them safely:
        - If attempt_count < max_attempts: re-queues as READY to retry
        - If attempt_count >= max_attempts: marks FAILED
        Returns number of tasks recovered.
        """
        repo_any: Any = self.execution_repo
        async with self._session_lock:
            stale_models = await repo_any.find_and_lock_stale_tasks(now=now) if hasattr(repo_any, "find_and_lock_stale_tasks") else []

        recovered_count = 0

        for model in stale_models:
            telemetry.increment_counter("task_lease_expired_total", value=1.0)
            telemetry.increment_counter(
                "task_recovery_total",
                value=1.0,
                labels={"reason": "lease_expired"},
            )
            task_domain = model.to_domain()
            # Retrieve workflow spec for task retry policy
            async with self._session_lock:
                workflow_exec = await self.execution_repo.get_workflow_execution(model.workflow_execution_id)
            if not workflow_exec:
                continue
            async with self._session_lock:
                workflow = await self.workflow_repo.get_workflow_spec(workflow_exec.workflow_id)
            if not workflow:
                continue

            task_spec = next((t for t in workflow.tasks if t.task_key == model.task_key), None)
            max_attempts = task_spec.retry_policy.max_attempts if task_spec else 3

            if model.attempt_count < max_attempts:
                # Reclaim task to READY for next execution attempt
                model.status = TaskExecutionStatus.READY.value
                model.lease_until = None
                model.leased_by = None
                async with self._session_lock:
                    await self.execution_repo.update_task_execution(model.to_domain())

                telemetry.increment_counter("task_recovery_retry_total", value=1.0)
                await self._emit_event(
                    execution_id=model.workflow_execution_id,
                    workflow_id=workflow_exec.workflow_id,
                    task_key=model.task_key,
                    agent_id=model.agent_id,
                    event_type=EventType.TASK_RETRIED,
                    payload={
                        "reason": "Task lease expired, reclaimed to READY",
                        "attempt": model.attempt_count,
                        "max_attempts": max_attempts,
                    },
                )
                logger.info(
                    "Stale task reclaimed to READY",
                    task_key=model.task_key,
                    execution_id=model.workflow_execution_id,
                    attempt=model.attempt_count,
                )
            else:
                # Retry budget exhausted -> mark FAILED
                model.status = TaskExecutionStatus.FAILED.value
                model.lease_until = None
                model.leased_by = None
                model.error_details = {
                    "error": "Task lease expired and retry budget exhausted.",
                    "category": "TEMPORAL_FAILURE",
                }
                # pyrefly: ignore [deprecated]
                model.completed_at = datetime.utcnow()
                async with self._session_lock:
                    await self.execution_repo.update_task_execution(model.to_domain())

                telemetry.increment_counter("task_recovery_failure_total", value=1.0)
                await self._emit_event(
                    execution_id=model.workflow_execution_id,
                    workflow_id=workflow_exec.workflow_id,
                    task_key=model.task_key,
                    agent_id=model.agent_id,
                    event_type=EventType.TASK_FAILED,
                    payload={"error": model.error_details["error"]},
                )
                logger.warning(
                    "Stale task failed after lease expiration",
                    task_key=model.task_key,
                    execution_id=model.workflow_execution_id,
                )

            recovered_count += 1

        return recovered_count

