# State Machine & Persistence Test Matrix

**Document:** State Transition Invariants, Persistence Mappings & Test Verifications  
**Status:** Approved (Phase 2)  

---

## 1. State Machine Transitions & Invariants Matrix

| State / Transition | Trigger Command | Target State | Invariant Enforced | Test Function | Expected Result |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `QUEUED` $\to$ `RUNNING` | `START` | `RUNNING` | Dispatched to active scheduler | `test_workflow_lifecycle_success_path` | Transition succeeded |
| `RUNNING` $\to$ `COMPLETED` | `COMPLETE` | `COMPLETED` | Terminal state immutability | `test_workflow_lifecycle_success_path` | Transition succeeded |
| `RUNNING` $\to$ `PAUSED` | `PAUSE` | `PAUSED` | Can resume or cancel | `test_workflow_pause_and_resume` | Transition succeeded |
| `PAUSED` $\to$ `RUNNING` | `RESUME` | `RUNNING` | Resumed after intervention | `test_workflow_pause_and_resume` | Transition succeeded |
| `COMPLETED` $\to$ Any | Any | Rejected | **Invariant 1**: Terminal state immutable | `test_workflow_terminal_state_protection` | Raises `StateTransitionError` |
| `RUNNING` $\to$ `CANCELLED` | `CANCEL` | `CANCELLED` | User abort halts execution | `test_workflow_cancellation` | Transition succeeded |
| `RUNNING` $\to$ `TIMED_OUT` | `TIMEOUT` | `TIMED_OUT` | Wall-clock SLA guard | `test_workflow_timeout` | Transition succeeded |
| `PENDING` $\to$ `BLOCKED` | `BLOCK` | `BLOCKED` | Unmet upstream dependencies | `test_task_blocking_and_unblocking` | Transition succeeded |
| `BLOCKED` $\to$ `READY` | `READY` | `READY` | **Invariant 4**: All deps satisfied | `test_task_blocking_and_unblocking` | Transition succeeded |
| `READY` $\to$ `RUNNING` | `DISPATCH` | `RUNNING` | **Invariant 8**: Increments `attempt_count` | `test_task_lifecycle_happy_path` | `attempt_count` += 1 |
| `RUNNING` $\to$ `COMPLETED` | `COMPLETE` | `COMPLETED` | Output contract satisfied | `test_task_lifecycle_happy_path` | Transition succeeded |
| `RUNNING` $\to$ `READY` | `RETRY` | `READY` | **Invariant 3**: Attempt count < max | `test_task_retry_within_bounds` | Re-queued as READY |
| `RUNNING` $\to$ `READY` | `RETRY` (Exhausted)| Rejected | **Invariant 3**: Cannot exceed max retries | `test_task_retry_exhaustion_guard` | Raises `StateTransitionError` |
| `RUNNING` $\to$ `WAITING_APPROVAL` | `REQUIRE_APPROVAL` | `WAITING_APPROVAL` | Human gate required before COMPLETED | `test_task_human_approval_flow` | Pauses for approval |
| `WAITING_APPROVAL` $\to$ `COMPLETED` | `APPROVE` | `COMPLETED` | Human signoff recorded | `test_task_human_approval_flow` | Task completed |
| `WAITING_APPROVAL` $\to$ `ESCALATED` | `REJECT` | `ESCALATED` | Operator rejection routes to escalation | `test_task_human_rejection_and_escalation` | Task escalated |
| `PENDING` $\to$ `COMPLETED` | `COMPLETE` | Rejected | **Invariant 2**: Illegal state jump | `test_invalid_task_transition_rejected` | Raises `StateTransitionError` |
| Circular DAG | Registration | Rejected | **Invariant 10**: Cycle rejection (Kahn) | `test_dag_circular_dependency_rejected` | Raises `CyclicDependencyError` |
| Self Dependency | Registration | Rejected | **Invariant 10**: Self dependency rejected | `test_dag_self_dependency_rejected` | Raises `WorkflowValidationError` |
| Missing Dependency | Registration | Rejected | **Invariant 10**: Dangling task key rejected | `test_dag_missing_dependency_rejected` | Raises `WorkflowValidationError` |
| Duplicate Task Key | Registration | Rejected | **Invariant 10**: Unique task key in workflow | `test_dag_duplicate_task_keys_rejected` | Raises `WorkflowValidationError` |

---

## 2. Failure Mode → Persistence & State Transition Mapping

| Failure Mode | Database Entity Affected | State Transition | Audit Event Persisted | Test Mapping |
| :--- | :--- | :--- | :--- | :--- |
| **Provider Timeout** | `task_executions` (`status`, `attempt_count`) | `RUNNING` $\to$ `READY` | `TASK_FAILED`, `TASK_RETRIED` | `test_task_retry_within_bounds` |
| **Retry Exhaustion** | `task_executions` (`status`, `error_details`) | `RUNNING` $\to$ `FAILED` | `TASK_FAILED` | `test_task_retry_exhaustion_guard` |
| **Approval Rejection**| `task_executions` (`status`), `workflow_events` | `WAITING_APPROVAL` $\to$ `ESCALATED` | `APPROVAL_DECISION_RECORDED` | `test_task_human_rejection_and_escalation` |
| **DAG Cycle Bomb** | None (Rejected before DB insert) | Registration Rejection | None | `test_dag_circular_dependency_rejected` |
| **Artifact Checksum Tamper**| `artifacts` (`checksum_sha256`) | Integrity check failure | `ARTIFACT_CHECKSUM_MISMATCH` | `test_artifact_repository_save_and_retrieve` |
| **Workflow Timeout**| `workflow_executions` (`status`) | `RUNNING` $\to$ `TIMED_OUT` | `WORKFLOW_TIMED_OUT` | `test_workflow_timeout` |
