# Agent Failure Matrix & Resolution Blueprint

**Document:** Comprehensive Agent Failure Modes, Detection, Impact, and Recovery  
**Status:** Approved Specification (Phase 3)  

---

## 1. Agent Failure Mode Resolution Table

| Failure Mode | Trigger / Root Cause | Detection Mechanism | Local Impact | Recovery Owner | Recovery Action |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Invalid Input Payload** | Upstream task or client passes missing/malformed fields | Pydantic `ValidationError` in `AbstractAgent.execute()` | Agent returns `AgentResult(success=False, error_category='contract_validation_failure')` | Orchestrator (Phase 4) | Non-retryable. Mark task `FAILED`; cascade `BLOCKED` to downstream nodes. |
| **Malformed Model Output** | LLM outputs invalid JSON or non-conformant schema | `json.loads` or Pydantic `ValidationError` in `generate_structured()` | Agent execution fails with `SchemaValidationError` | Orchestrator | Retryable if attempts remain. Transition task `RUNNING -> READY` via `TaskCommand.RETRY`. |
| **Provider Timeout** | LLM latency exceeds `context.timeout_seconds` | `asyncio.TimeoutError` or provider timeout exception | Agent returns `infrastructure_provider_failure` | Orchestrator | Retryable. Apply exponential backoff with jitter. |
| **Rate Limit / 429** | Quota exceeded on Gemini API | `GeminiProviderError` with code 429 | Task fails temporarily | Orchestrator | Retryable with exponential backoff & token bucket throttle. |
| **Service Unavailable (500/503)** | Transient provider outage | `GeminiProviderError` with code 500/503 | Task fails temporarily | Orchestrator | Retryable up to `max_retries`. |
| **Reviewer Rejection (`FAIL`)** | Critical defect, hallucination, or contradiction detected | `ReviewOutput.decision == 'FAIL'` | Task produces negative review audit | Orchestrator / Human Operator | Route to Human Approval Gate or fallback revision branch. |
| **Reviewer Revision Request (`REQUIRES_REVISION`)** | Minor defect or missing citations | `ReviewOutput.decision == 'REQUIRES_REVISION'` | Audit warning emitted | Orchestrator / Synthesizer | Synthesizer records warning in deliverable; or routes to revision task. |
| **Synthesizer Upstream Failure** | Upstream research or analysis task failed | Missing upstream artifact in execution context | Synthesizer input validation fails | Orchestrator | Block synthesizer dispatch until upstream resolves or abort workflow. |

---

## 2. Core Boundary Principle

* **Agent / Provider Layer Responsibility**: Detect errors, classify them into standard `FailureCategory` types, and return structured `AgentResult(success=False)` without unhandled process crashes.
* **Orchestration Layer Responsibility**: Decide whether to retry, escalate to human approval, switch to a fallback agent, or terminate the workflow execution.
