# Failure Propagation & Workflow Impact Architecture

**Document:** Task Failure Decoupling, Cascading & Workflow Resilience  
**Status:** Approved Architecture (Phase 2 Review)  

---

## 1. Task Failure vs. Workflow Failure

A cardinal rule of the Multi-Agent Workflow Orchestrator: **A single task failure does NOT automatically trigger a global workflow failure.**

```
                           ┌───────────────────────────┐
                           │   Task Encounters Error   │
                           └─────────────┬─────────────┘
                                         │
                                         ▼
                           ┌───────────────────────────┐
                           │    Failure Classification │
                           └─────────────┬─────────────┘
                                         │
                 ┌───────────────────────┼───────────────────────┐
                 │ Retryable &           │ Quality /             │ Non-Retryable /
                 │ Attempt <= Max        │ Policy Gate           │ Retries Exhausted
                 ▼                       ▼                       ▼
      ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
      │ TaskCommand.RETRY   │ │ Human Approval Gate │ │ Critical vs.        │
      │ • Status: READY     │ │ • WAITING_APPROVAL  │ │ Non-Critical Check  │
      │ • Backoff & Jitter  │ │ • Pause branch only │ └──────────┬──────────┘
      └─────────────────────┘ └─────────────────────┘            │
                                                ┌────────────────┴────────────────┐
                                                │ Non-Critical Branch             │ Critical Path
                                                ▼                                 ▼
                                     ┌─────────────────────┐           ┌─────────────────────┐
                                     │ • Task: FAILED      │           │ • Task: FAILED      │
                                     │ • Cascade: BLOCKED  │           │ • Cascade: BLOCKED  │
                                     │ • Workflow Continues│           │ • Workflow: FAILED  │
                                     └─────────────────────┘           └─────────────────────┘
```

---

## 2. Failure Policy Resolution Spectrum

When a task execution fails:

1. **Tier 1 — Automated Retry**:
   - Condition: Error category is in `retry_policy.retryable_categories` and `task.attempt_count <= retry_policy.max_attempts`.
   - Action: `WorkflowStateMachine.transition_task(task, TaskCommand.RETRY)`.
   - Workflow impact: Zero. Workflow remains `RUNNING`.

2. **Tier 2 — Human Escalation**:
   - Condition: Rejection from an evaluator gate or high-uncertainty model output.
   - Action: `WorkflowStateMachine.transition_task(task, TaskCommand.REQUIRE_APPROVAL)`.
   - Workflow impact: Dependent downstream tasks remain `BLOCKED`. Independent parallel branches continue executing.

3. **Tier 3 — Non-Critical Task Failure (Graceful Degradation)**:
   - Condition: A supplementary task (e.g. `market_sentiment_scrape`) fails permanently, but is flagged as non-blocking.
   - Action: Task enters `FAILED`. Directly dependent tasks enter `BLOCKED` (or are skipped). Independent DAG branches continue to completion.
   - Workflow impact: Workflow reaches `COMPLETED` (or `COMPLETED_WITH_WARNINGS`).

4. **Tier 4 — Critical Path Failure (Terminal Workflow Abort)**:
   - Condition: A mandatory prerequisite task (e.g. `planner_agent`) fails permanently and has no fallback.
   - Action: Task enters `FAILED`. All downstream tasks are marked `BLOCKED`.
   - Workflow impact: Engine issues `WorkflowCommand.FAIL`, transitioning `WorkflowExecution` to `FAILED`.

---

## 3. Invariant Guarantees

1. **Branch Isolation**: A failure in one parallel branch (e.g. `Branch B`) never abruptly cancels an active, healthy parallel branch (`Branch A`) unless the global workflow is explicitly terminated.
2. **Terminal Traceability**: The exact root-cause failure record is stored on `task_executions.error_details` and emitted as a `TASK_FAILED` `WorkflowEvent`.
