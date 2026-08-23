# Execution Engine Failure Matrix & Operational Runbook

**Document:** Comprehensive Orchestrator Failure Modes, Invariant Gating, and Recovery Blueprint  
**Phase:** Phase 4.1 Release Gate  
**Status:** Implemented & Verified  

---

## 1. Execution Engine Failure Matrix

| # | Failure Scenario | Trigger / Root Cause | Detection Mechanism | Local Impact | Engine State Transition | Recovery Action | Observability & Telemetry |
| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **Duplicate Task Claim** | Concurrent scheduler routines attempt to dispatch same ready node | `SqlExecutionRepository.claim_task_for_execution()` with `SELECT FOR UPDATE` returns `None` | Second worker safely unblocks | None (task remains `RUNNING` on first worker) | Second worker exits dispatch loop cleanly without double-executing | `TASK_STARTED` emitted exactly once |
| 2 | **Missing Agent** | Workflow references `agent_id` not registered in `AgentRegistry` | `agent_registry.get()` raises `AgentNotFoundError` | Task fails immediately with `agent_not_found` | Task: `FAILED`<br>Downstream: `FAILED` | Engine marks task `FAILED`, cascades unrecoverable failure | `TASK_FAILED` event with error details |
| 3 | **Malformed Agent Output** | Model outputs non-conforming JSON structure | Pydantic `ValidationError` in `AbstractAgent.execute()` | Agent returns `AgentResult(success=False, error_category='contract_validation_failure')` | Task: `RETRY` (if attempts remain) or `FAILED` | Engine triggers retry if within `max_retries`; otherwise cascades failure | `TASK_RETRIED` or `TASK_FAILED` event |
| 4 | **Provider Timeout** | Model provider latency exceeds task timeout | Provider raises timeout exception | Agent returns `infrastructure_provider_failure` | Task: `RETRY` (backoff) or `TIMED_OUT` | Exponential backoff retry | `TASK_RETRIED` event with attempt counter |
| 5 | **Provider Rate Limit (429)** | Vendor API quota exhausted | `GeminiProviderError` with code 429 | Task fails temporarily | Task: `RETRY` | Backoff with jitter up to `max_retries` | `TASK_RETRIED` event with code 429 |
| 6 | **Task Timeout** | Task execution duration exceeds `task_spec.timeout_seconds` | Engine wall-clock monitor | Task marked timed out | Task: `TIMED_OUT`<br>Downstream: `FAILED` | Non-retryable task abort | `TASK_TIMED_OUT` event |
| 7 | **Workflow Timeout** | Total workflow elapsed time exceeds `max_workflow_duration_seconds` | Engine polling loop `time.perf_counter() - start_time` check | Global workflow aborted | Workflow: `TIMED_OUT`<br>Active tasks halted | Terminal workflow abort | `WORKFLOW_TIMED_OUT` event |
| 8 | **Retry Exhaustion** | Task attempts exceed `max_retries` (attempt_count > max_retries) | `_handle_task_failure()` retry limit guard | Task permanently marked `FAILED` | Task: `FAILED`<br>Workflow: `FAILED` | Escalates to terminal workflow failure or human operator | `TASK_FAILED` event with final attempt count |
| 9 | **Dependency Failure** | Upstream prerequisite task failed unrecoverably | Dependency resolver evaluates `failed_keys` intersection | Downstream task cannot execute | Downstream: `BLOCKED -> FAILED` | Cascade failure marks dependent tasks `FAILED` without dispatch | `TASK_FAILED` with `failed_dependencies` list |
| 10 | **Artifact Corruption** | Output artifact payload does not match SHA-256 checksum | Engine computes `hashlib.sha256()` on `ProducedArtifact` content | Artifact rejected | Task: `FAILED` | Aborts task; blocks poisoned artifact from downstream consumption | `TASK_FAILED` event with checksum mismatch log |
| 11 | **Database Lock Timeout** | Concurrent contention on SQLite/PostgreSQL row lock | Database driver raises lock timeout | Transaction aborts | Engine catches and retries task claim next cycle | Exponential backoff on task acquisition | Structured log `db_lock_contention` |
| 12 | **Cancellation Race** | User cancels workflow while worker is in mid-execution | `WorkflowStateMachine.transition_workflow(CANCEL)` | Workflow enters `CANCELLED` | Workflow: `CANCELLED`<br>Subsequent transitions rejected | State machine guards reject any further completion writes | `WORKFLOW_CANCELLED` event |
| 13 | **Concurrent Overflow** | Number of ready tasks exceeds `max_parallel_tasks` | Engine slices `ready_tasks[:max_parallel_tasks]` | Excess ready tasks wait in `READY` queue | Dispatched tasks: `RUNNING`<br>Queued tasks: `READY` | Engine dispatches next batch on subsequent cycle | Bounded parallelism verified in unit tests |
| 14 | **Stuck / Non-Progressing Loop** | No tasks running and no tasks ready | Engine evaluates `not ready_tasks and not running_tasks` | Engine exits poll loop cleanly | Workflow: `COMPLETED` (if all done) or `FAILED` | Engine finalizes terminal status without infinite loop | Finalization log and terminal event |
| 15 | **Context Overflow** | Upstream outputs accumulate too many data fields | Bounded `AgentExecutionContext` filtering | Agent receives only explicitly mapped fields | Bounded context preserved | Prevents unbounded prompt bloat | Prompt size logged in metrics |

---

## 2. Invariant Guarantees

1. **Attempt Count as Single Source of Truth**: All retry decisions and attempt counts are strictly tracked on `task_executions.attempt_count` (1 = first run, 2 = 1st retry, etc.).
2. **Deterministic Termination**: Every loop in `run_to_completion()` is bounded by `max_poll_cycles` and `max_workflow_duration_seconds`. Infinite execution loops are strictly impossible.
3. **Context Isolation**: No database sessions, secrets, API keys, or raw SQL are ever passed inside `AgentExecutionContext`.
