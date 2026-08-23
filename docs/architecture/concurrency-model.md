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

### 2.2 Atomic Task Claiming with Database Row Locking
When the scheduler identifies ready tasks to dispatch to workers:
```sql
-- Atomic Task Acquisition
SELECT * FROM task_executions 
WHERE id = :task_id AND status = 'READY' 
FOR UPDATE;

UPDATE task_executions 
SET status = 'RUNNING', attempt_count = attempt_count + 1, started_at = NOW() 
WHERE id = :task_id;
```
If another worker or retry loop tries to acquire the same task, the `WHERE status = 'READY'` condition fails or waits on the row lock, preventing double execution.

### 2.3 Terminal State Immutability
Once a task reaches a terminal state (`COMPLETED`, `FAILED`, `CANCELLED`, `TIMED_OUT`), `WorkflowStateMachine.transition_task()` raises `StateTransitionError` on any subsequent command, preventing racing timeouts or delayed responses from overwriting a completed task.

---

## 3. Transaction Isolation Level

* PostgreSQL default isolation level: `READ COMMITTED`.
* Critical state transition updates occur inside explicit transaction blocks (`async with session.begin():`).
* Events are committed in the same database transaction as the task/workflow status update to ensure strict zero-data-loss consistency.
