# Testing & Verification Strategy

**Document:** Test Pyramid, Failure-Mode Mapping & Quality Verification  
**Status:** Approved Architecture (Day 0)  

---

## 1. Testing Pyramid & Test Levels

```
                     ┌───────────────────────┐
                     │   E2E Smoke Tests     │  (5%)  FastAPI + PostgreSQL + Next.js Live Run
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │   Integration Tests   │  (25%) API endpoints, DB repo queries, SSE stream
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │      Unit Tests       │  (70%) State machine, DAG sort, Agent schemas,
                     └───────────────────────┘        Failure classifier, Backoff & Circuit breaker
```

---

## 2. Failure Mode → Test Mapping Matrix

Every critical failure mode identified in the Failure Matrix is mapped to a dedicated automated test suite:

| Failure Mode | Test File Target | Test Function | Test Objective |
| :--- | :--- | :--- | :--- |
| **Provider Timeout** | `tests/unit/test_failures.py` | `test_provider_timeout_retry` | Verifies exponential backoff and eventual retry success on timeout. |
| **Provider Rate Limit** | `tests/unit/test_failures.py` | `test_rate_limit_backoff` | Verifies 429 response triggers `retry-after` pause without crashing worker. |
| **Provider Outage (503)** | `tests/unit/test_circuit_breaker.py` | `test_circuit_breaker_tripping` | Verifies 5 consecutive failures trip breaker into `OPEN` state. |
| **Malformed JSON Output** | `tests/unit/test_agent_runner.py` | `test_malformed_json_recovery` | Verifies reflection prompt repairs invalid JSON string on retry. |
| **Schema Validation Error**| `tests/unit/test_contracts.py` | `test_pydantic_schema_validation` | Verifies Pydantic rejection when required field is missing. |
| **Circular DAG Dependency**| `tests/unit/test_dag.py` | `test_circular_dependency_rejection`| Verifies Kahn's algorithm raises `CyclicDependencyError` on $A \to B \to A$. |
| **Task Wall-Clock Timeout**| `tests/unit/test_scheduler.py` | `test_task_timeout_cancellation` | Verifies task exceeding duration limit is safely cancelled. |
| **Workflow Global Timeout**| `tests/integration/test_engine.py` | `test_workflow_global_timeout` | Verifies running DAG transitions to `TIMED_OUT` when budget expires. |
| **Retry Exhaustion** | `tests/unit/test_recovery.py` | `test_retry_exhaustion_escalation` | Verifies task transitions to `FAILED` when `max_retries` is reached. |
| **Missing Agent in Registry**| `tests/unit/test_registry.py` | `test_missing_agent_lookup` | Verifies workflow validator catches unregistered agent IDs. |
| **Artifact Checksum Error**| `tests/unit/test_artifacts.py` | `test_artifact_checksum_verification`| Verifies tampered artifact content fails SHA-256 validation. |
| **Evaluator Rejection** | `tests/unit/test_evaluation.py` | `test_evaluator_rejection_loop` | Verifies score < 0.8 triggers retry or human gate. |
| **Illegal State Transition**| `tests/unit/test_state_machine.py`| `test_illegal_state_transition` | Verifies exception when attempting illegal transition (e.g. PENDING to COMPLETED). |
| **Duplicate Idempotency Key**| `tests/integration/test_api.py`| `test_idempotent_workflow_trigger`| Verifies duplicate POST returns existing execution record. |
| **Approval Gate Timeout** | `tests/unit/test_approval.py` | `test_approval_timeout_escalation` | Verifies expired approval gate triggers configured auto-action. |

---

## 3. Mock Provider for Deterministic Offline Testing

To enable fast, zero-cost, 100% reproducible testing in CI/CD without calling external Gemini APIs, the test suite uses `MockModelProvider`:

```python
class MockModelProvider:
    def __init__(self, canned_responses: dict[str, Any] | None = None):
        self.canned_responses = canned_responses or {}
        self.call_history: list[dict[str, Any]] = []

    async def generate_structured(
        self,
        prompt: str,
        system_instruction: str,
        response_schema: type[BaseModel],
        temperature: float = 0.2,
        timeout_seconds: float = 30.0,
    ) -> tuple[BaseModel, dict[str, int]]:
        self.call_history.append({"prompt": prompt, "schema": response_schema.__name__})
        
        if response_schema.__name__ in self.canned_responses:
            data = self.canned_responses[response_schema.__name__]
            return response_schema(**data), {"prompt_tokens": 50, "completion_tokens": 50, "total_tokens": 100}
            
        raise ValueError(f"No mock response configured for schema {response_schema.__name__}")
```
