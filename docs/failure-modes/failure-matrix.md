# Multi-Agent Workflow Failure Matrix & Taxonomy

**Document:** Comprehensive Failure Modes, Classification & Mitigation Engineering  
**Status:** Approved Architecture (Day 0)  

---

## 1. Failure Classification Taxonomy

The system defines 8 high-level failure classes:

1. `INFRASTRUCTURE_PROVIDER_FAILURE`: External LLM API network timeouts, 503 unavailable, rate limits.
2. `CONTRACT_VALIDATION_FAILURE`: Malformed JSON, Pydantic schema validation failures, missing required fields.
3. `DEPENDENCY_TOPOLOGY_FAILURE`: Circular DAG dependencies, missing upstream task references.
4. `RUNTIME_RESOURCE_FAILURE`: Context window token overflow, output payload size limit exceeded.
5. `TEMPORAL_FAILURE`: Task wall-clock timeout, workflow global timeout, human approval SLA expiration.
6. `INTEGRITY_ARTIFACT_FAILURE`: Missing upstream artifact, SHA-256 checksum mismatch, state corruption.
7. `QUALITY_EVALUATION_FAILURE`: Evaluator score below threshold, factuality critique rejection.
8. `CONCURRENCY_STATE_FAILURE`: Duplicate execution attempt, race condition on task state transition.

---

## 2. Complete Failure Modes Matrix (22 Canonical Failure Scenarios)

| # | Failure Mode | Detection Mechanism | Classification | Severity | Retryable? | Max Retries | Backoff Strategy | Recovery Strategy | Escalation Strategy | Terminal State | Telemetry Event | Test Requirement |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | **Provider Timeout** | HTTP client timeout exception | `INFRASTRUCTURE_PROVIDER_FAILURE` | Medium | Yes | 3 | Exponential + Jitter (2s, 4s, 8s) | Re-invoke ModelProvider endpoint | Escalate to backup model if configured | `TIMED_OUT` (if exhausted) | `TASK_FAILED`, `TASK_RETRIED` | `test_provider_timeout_retry` |
| **2** | **Provider Rate Limit (429)** | HTTP 429 status code + `retry-after` | `INFRASTRUCTURE_PROVIDER_FAILURE` | Medium | Yes | 4 | Respect `retry-after` header + Jitter | Pause worker task dispatching | Alert operations team if sustained | `FAILED` | `TASK_RETRIED`, `RATE_LIMIT_WARNING` | `test_rate_limit_backoff` |
| **3** | **Provider 500/503 Unavailable** | HTTP 5xx response code | `INFRASTRUCTURE_PROVIDER_FAILURE` | High | Yes | 3 | Exponential (3s, 6s, 12s) | Retry via circuit breaker | Fallback to secondary model provider | `FAILED` | `CIRCUIT_BREAKER_TRIGGERED` | `test_provider_outage_circuit_breaker` |
| **4** | **Malformed Model Output** | JSONDecodeError on raw response | `CONTRACT_VALIDATION_FAILURE` | Medium | Yes | 2 | Linear (1s) | Re-prompt with error feedback & schema reminder | Escalate to human or fail | `FAILED` | `SCHEMA_VALIDATION_ERROR` | `test_malformed_json_recovery` |
| **5** | **Schema Validation Failure** | Pydantic `ValidationError` | `CONTRACT_VALIDATION_FAILURE` | Medium | Yes | 2 | Linear (1s) | Self-correction reflection prompt with validation diff | Route task to reviewer or human gate | `FAILED` | `CONTRACT_MISMATCH_RECORDED` | `test_pydantic_schema_validation_rejection` |
| **6** | **Tool Execution Failure** | Exception raised inside tool handler | `CONTRACT_VALIDATION_FAILURE` | Medium | Yes | 2 | Exponential (2s, 4s) | Retry tool with sanitized arguments | Fallback to alternative tool or agent | `FAILED` | `TOOL_EXECUTION_FAILED` | `test_tool_failure_handling` |
| **7** | **Dependency Failure** | Upstream task entered terminal `FAILED` | `DEPENDENCY_TOPOLOGY_FAILURE` | High | No | 0 | None | Mark downstream tasks as `BLOCKED`/`SKIPPED` | Halt dependent branch, alert operator | `FAILED` / `BLOCKED` | `DOWNSTREAM_BLOCKED_EVENT` | `test_cascade_dependency_failure` |
| **8** | **Context Window Overflow** | Token counter > model limit | `RUNTIME_RESOURCE_FAILURE` | High | Yes | 1 | None | Apply contextual summarization & prune history | Reject input if fundamentally oversized | `FAILED` | `CONTEXT_OVERFLOW_WARNING` | `test_context_truncation_and_recovery` |
| **9** | **Task Wall-Clock Timeout** | `asyncio.wait_for` timeout | `TEMPORAL_FAILURE` | High | Yes | 2 | Exponential (2s, 4s) | Terminate task attempt, re-dispatch | Mark `TIMED_OUT`, alert workflow manager | `TIMED_OUT` | `TASK_TIMED_OUT` | `test_task_timeout_cancellation` |
| **10**| **Workflow Global Timeout** | Wall clock > `max_workflow_duration` | `TEMPORAL_FAILURE` | Critical | No | 0 | None | Cancel all running tasks, save partial state | Abort workflow, notify user | `TIMED_OUT` | `WORKFLOW_TIMED_OUT` | `test_workflow_global_timeout` |
| **11**| **Retry Limit Exhaustion** | `attempt_count >= max_retries` | `INFRASTRUCTURE_PROVIDER_FAILURE` | High | No | 0 | None | Check for configured fallback agent | Transition task to `FAILED` & pause workflow | `FAILED` | `RETRY_EXHAUSTION_EVENT` | `test_retry_exhaustion_escalation` |
| **12**| **Circular DAG Dependency** | Kahn's algorithm fails | `DEPENDENCY_TOPOLOGY_FAILURE` | Critical | No | 0 | None | Reject workflow submission at registration API | Return 422 Unprocessable Entity | `REJECTED` | `INVALID_WORKFLOW_REJECTED` | `test_circular_dependency_rejection` |
| **13**| **Invalid Workflow Definition** | Schema validation error on WorkflowSpec | `DEPENDENCY_TOPOLOGY_FAILURE` | High | No | 0 | None | Reject workflow registration with field diffs | Immediate API rejection (400 Bad Request) | `REJECTED` | `SCHEMA_VALIDATION_ERROR` | `test_invalid_workflow_spec` |
| **14**| **Agent Missing in Registry** | `agent_id` lookup returns `None` | `DEPENDENCY_TOPOLOGY_FAILURE` | High | No | 0 | None | Fail validation at workflow start | Reject execution trigger (404 Not Found) | `FAILED` | `AGENT_NOT_FOUND_ERROR` | `test_missing_agent_registry_lookup` |
| **15**| **Artifact Missing** | Upstream artifact UUID not in DB | `INTEGRITY_ARTIFACT_FAILURE` | High | No | 0 | None | Mark task `FAILED` with missing artifact ref | Escalate to administrator | `FAILED` | `ARTIFACT_NOT_FOUND` | `test_missing_artifact_integrity` |
| **16**| **Corrupted Artifact (Checksum)** | SHA-256 hash does not match DB record | `INTEGRITY_ARTIFACT_FAILURE` | High | No | 0 | None | Invalidate corrupted artifact, reject downstream | Alert security/data integrity logger | `FAILED` | `ARTIFACT_CHECKSUM_MISMATCH` | `test_artifact_checksum_verification` |
| **17**| **Evaluator Quality Rejection** | Evaluator score < `min_pass_score` | `QUALITY_EVALUATION_FAILURE` | Medium | Yes | 2 | Linear (1s) | Re-prompt agent with evaluator critique | Route task to human approval gate | `FAILED` / `ESCALATED` | `EVALUATION_GATE_SCORED` | `test_evaluator_rejection_loop` |
| **18**| **Inconsistent State Transition** | State machine raises `IllegalTransition` | `CONCURRENCY_STATE_FAILURE` | High | No | 0 | None | Abort transition, reload fresh state from DB | Log integrity anomaly for root-cause analysis | `FAILED` | `ILLEGAL_STATE_TRANSITION_ALERT` | `test_state_machine_guard_invariants` |
| **19**| **Duplicate Execution Request** | Duplicate `idempotency_key` in DB | `CONCURRENCY_STATE_FAILURE` | Low | No | 0 | None | Return existing `workflow_execution_id` | Return HTTP 200 with existing status | *(Current)* | `IDEMPOTENT_HIT_LOGGED` | `test_idempotent_execution_request` |
| **20**| **Concurrent State Update Conflict**| Database optimistic locking / conflict | `CONCURRENCY_STATE_FAILURE` | Medium | Yes | 3 | Exponential (0.1s, 0.2s, 0.4s) | Refresh DB record and re-evaluate transition | Fail task update if conflict persists | `FAILED` | `CONCURRENCY_CONFLICT_LOGGED` | `test_concurrent_state_lock_resolution` |
| **21**| **Human Approval Gate Timeout**| Approval pending duration > SLA | `TEMPORAL_FAILURE` | Medium | No | 0 | None | Execute configured `auto_action_on_timeout` | Send urgent reminder notification | `ESCALATED` / `FAILED` | `APPROVAL_SLA_EXPIRED` | `test_approval_gate_timeout_action` |
| **22**| **Partial Workflow Failure** | Non-critical optional branch failed | `DEPENDENCY_TOPOLOGY_FAILURE` | Medium | No | 0 | None | Continue execution of independent DAG branches | Mark workflow `COMPLETED_WITH_WARNINGS` | `COMPLETED` | `PARTIAL_WORKFLOW_WARNING` | `test_partial_failure_branch_resilience` |
