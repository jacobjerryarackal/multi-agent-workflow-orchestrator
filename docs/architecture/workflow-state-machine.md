# Workflow & Task State Machine Specification

**Document:** Formal State Machine & Lifecycle Transitions  
**Status:** Approved Architecture (Day 0)  

---

## 1. Task Execution State Machine

```
                        ┌─────────────┐
                        │   PENDING   │
                        └──────┬──────┘
                               │
            ┌──────────────────┴──────────────────┐
            │ Dependencies unmet                  │ Dependencies met
            ▼                                     ▼
     ┌─────────────┐                       ┌─────────────┐
     │   BLOCKED   │──────────────────────▶│    READY    │
     └─────────────┘  All upstream OK      └──────┬──────┘
                                                  │ Dispatch
                                                  ▼
                                           ┌─────────────┐
                                           │   RUNNING   │
                                           └──────┬──────┘
            ┌───────────────────┬─────────────────┼───────────────────┬───────────────────┐
            │ Success           │ Requires        │ Timeout           │ Fatal Error /     │ Cancellation
            ▼                   │ Approval        ▼                   │ Exhausted Retry   ▼
     ┌─────────────┐            ▼          ┌─────────────┐            ▼            ┌─────────────┐
     │  COMPLETED  │     ┌─────────────┐   │  TIMED_OUT  │     ┌─────────────┐     │  CANCELLED  │
     └─────────────┘     │   WAITING   │   └─────────────┘     │   FAILED    │     └─────────────┘
                         │  APPROVAL   │                       └─────────────┘
                         └──────┬──────┘                              ▲
                                │                                     │
                 ┌──────────────┴──────────────┐                      │
                 │ Approved                    │ Rejected /           │
                 ▼                             │ Escalated            │
          ┌─────────────┐                      └──────────────────────┘
          │  COMPLETED  │                                 │
          └─────────────┘                                 ▼
                                                   ┌─────────────┐
                                                   │  ESCALATED  │
                                                   └─────────────┘
```

---

## 2. Task State Transition Matrix

| Current State | Next State | Trigger / Event | Guard Condition |
| :--- | :--- | :--- | :--- |
| `PENDING` | `BLOCKED` | `EVALUATE_DEPENDENCIES` | At least one upstream dependency has not completed. |
| `PENDING` | `READY` | `EVALUATE_DEPENDENCIES` | Has zero dependencies or all upstream dependencies are `COMPLETED`. |
| `BLOCKED` | `READY` | `UPSTREAM_TASK_COMPLETED` | All upstream dependencies transition to `COMPLETED`. |
| `BLOCKED` | `FAILED` | `UPSTREAM_TASK_FAILED` | Upstream dependency failed without recovery strategy. |
| `READY` | `RUNNING` | `TASK_DISPATCHED` | Execution worker pool acquires task. |
| `RUNNING` | `COMPLETED` | `AGENT_EXECUTION_SUCCESS` | Agent returns valid structured output satisfying output schema & eval gate. |
| `RUNNING` | `WAITING_APPROVAL`| `APPROVAL_GATE_REQUIRED` | Task output valid, but task definition specifies human approval gate. |
| `RUNNING` | `READY` (Retry)| `TRANSIENT_FAILURE` | Failure classified as retryable and `attempt < max_retries`. |
| `RUNNING` | `FAILED` | `NON_RETRYABLE_FAILURE` | Fatal failure or `attempt >= max_retries`. |
| `RUNNING` | `TIMED_OUT` | `TASK_TIMEOUT_EXPIRED` | Execution duration exceeds `timeout_seconds`. |
| `RUNNING` | `CANCELLED` | `WORKFLOW_CANCELLED` | User or operator aborted workflow. |
| `WAITING_APPROVAL`| `COMPLETED` | `HUMAN_APPROVED` | Authorized user submits approval decision. |
| `WAITING_APPROVAL`| `ESCALATED` | `HUMAN_REJECTED` | Reviewer rejects output; routed for review or alternative path. |
| `WAITING_APPROVAL`| `TIMED_OUT` | `APPROVAL_TIMEOUT` | Approval gate SLA window expired. |

---

## 3. Workflow Execution State Machine

| State | Description | Allowed Next States |
| :--- | :--- | :--- |
| `QUEUED` | Workflow submitted, graph validated, awaiting runner dispatch. | `RUNNING`, `CANCELLED` |
| `RUNNING` | Tasks are actively being scheduled, executed, or awaiting approval. | `COMPLETED`, `FAILED`, `PAUSED`, `CANCELLED`, `TIMED_OUT` |
| `PAUSED` | Workflow paused awaiting human intervention / approval gate. | `RUNNING`, `CANCELLED` |
| `COMPLETED` | All terminal tasks in DAG reached `COMPLETED` state. | *(Terminal)* |
| `FAILED` | One or more critical tasks failed and cannot be recovered. | *(Terminal)* |
| `CANCELLED` | Execution explicitly stopped by user command. | *(Terminal)* |
| `TIMED_OUT` | Total workflow wall-clock duration exceeded `max_workflow_duration`. | *(Terminal)* |

---

## 4. Invariant Rules & Illegal Transitions

1. **Terminal State Immutability**: Once a task or workflow enters `COMPLETED`, `CANCELLED`, or `TIMED_OUT`, its state cannot be updated (except explicit administrative retry creating a new execution attempt).
2. **No Skipping States**: A task cannot jump from `PENDING` directly to `RUNNING` or `COMPLETED` without passing through `READY`.
3. **Strict In-Degree Dependency Requirement**: A task in `BLOCKED` cannot transition to `READY` while any parent task is in `PENDING`, `BLOCKED`, `RUNNING`, or `FAILED`.
4. **Approval Gate Guard**: A task with `approval_required=True` can NEVER transition directly from `RUNNING` to `COMPLETED`. It must enter `WAITING_APPROVAL`.
