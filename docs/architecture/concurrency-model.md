# Concurrency Model & State Synchronization

**Document:** Concurrency Architecture, Race Prevention & Idempotency  
**Status:** Approved Architecture (Phase 2)  

---

## 1. Concurrency Dynamics in the Orchestrator

The orchestrator executes multi-agent workflows with both sequential and parallel DAG branches. Concurrency introduces potential hazards:
1. **Duplicate Dispatch**: Two concurrent scheduler ticks both identify a task as `READY` and dispatch it twice.
2. **Retry Race**: A delayed timeout event fires just as a task successfully returns `COMPLETED`.
3. **Double Submission**: A client retries an HTTP POST `/workflows/{id}/execute` due to a network glitch.
4. **Approval vs. SLA Expiration**: A human operator approves a task in the UI at the exact millisecond the approval timeout trigger fires.

---

## 2. Mitigation Strategies & Invariants

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               CONCURRENCY DEFENSE TIERS                                │
├──────────────────────────┬─────────────────────────────────────────────────────────────┤
│ 1. API Level             │ Idempotency Key deduplication on workflow execution trigger │
│ 2. In-Memory Engine      │ Asynchronous Worker Semaphore (`max_parallel_tasks`)        │
│ 3. State Machine Level   │ Pure domain validation of atomic state transitions          │
│ 4. Database Level        │ Row-level locking (`SELECT ... FOR UPDATE`) on state claims │
└──────────────────────────┴─────────────────────────────────────────────────────────────┘
```

### 2.1 Idempotency Key at Ingress
* Clients sending `POST /workflows/{id}/execute` may provide a header `Idempotency-Key: <UUID>`.
* The database has a unique index on `workflow_executions(workflow_id, idempotency_key)`.
* If a duplicate request arrives, the server returns the existing `WorkflowExecution` record without re-spawning the engine loop.

### 2.2 Atomic Task Claiming with Database Row Locking (`SELECT ... FOR UPDATE`)
When an async worker or scheduler loop attempts to acquire a task:
```python
stmt = (
    select(TaskExecutionModel)
    .where(
        TaskExecutionModel.workflow_execution_id == workflow_execution_id,
        TaskExecutionModel.task_key == task_key,
        TaskExecutionModel.status == TaskExecutionStatus.READY.value,
    )
    .with_for_update()
)
result = await session.execute(stmt)
model = result.scalar_one_or_none()
if not model:
    return None  # Already claimed by another concurrent worker

model.status = TaskExecutionStatus.RUNNING.value
model.attempt_count += 1
model.started_at = datetime.utcnow()
await session.flush()
```

#### Detailed Concurrency Characteristics:
1. **Locked Row**: The exact `task_executions` record for `(workflow_execution_id, task_key)`.
2. **Lock Window**: Exclusive row lock held from the moment `SELECT ... FOR UPDATE` executes until the transaction commits (`async with session.begin():`).
3. **Double Dispatch Elimination**: If two concurrent scheduler routines attempt to claim the same `READY` task simultaneously:
   - Worker 1 acquires the row lock, checks `status == 'READY'`, mutates it to `'RUNNING'`, increments `attempt_count`, and commits.
   - Worker 2 unblocks from the lock, re-evaluates the query filter `status == 'READY'`, receives `None` (0 rows), and cleanly exits without dispatching.
4. **Worker Crash & Orphan Handling**: If a worker process crashes while a task is `RUNNING`:
   - The transaction aborts/releases the row lock.
   - The orchestrator's periodic reconciliation loop identifies tasks in `RUNNING` exceeding `task.timeout_seconds` + grace period and transitions them to `TIMED_OUT` (or re-queues them via `TaskCommand.RETRY`).

### 2.3 Terminal State Immutability
Once a task reaches a terminal state (`COMPLETED`, `FAILED`, `CANCELLED`, `TIMED_OUT`), `WorkflowStateMachine.transition_task()` raises `StateTransitionError` on any subsequent command, preventing racing timeouts or delayed responses from overwriting a completed task.

---

## 3. Transaction Isolation Level

* PostgreSQL default isolation level: `READ COMMITTED`.
* Critical state transition updates occur inside explicit transaction blocks (`async with session.begin():`).
* Events are committed in the same database transaction as the task/workflow status update to ensure strict zero-data-loss consistency.
