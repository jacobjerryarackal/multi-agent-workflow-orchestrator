# Evaluation & Revision Failure Mode Matrix & Operational Runbook

**Document:** Orchestrator Quality Evaluation & Optimization Failure Modes  
**Phase:** Phase 5 Implementation  
**Status:** Implemented & Verified  

---

## 1. Evaluation & Optimization Failure Matrix

| # | Failure Scenario | Trigger / Root Cause | Detection Mechanism | Local Impact | State Transition | Recovery Action | Observability |
| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **Evaluator Unavailable** | Network failure reaching model provider | Evaluator provider raises connection exception | Task cannot complete evaluation | Task remains `RUNNING` or fails to `ESCALATE` | Evaluator logs error, catches exception, returns `FAIL` with infrastructure category | `EVALUATION_FAILED` event with error details |
| 2 | **Evaluator Timeout** | Evaluator LLM latency exceeds 30s timeout | Evaluator timeout handler triggers | Evaluation aborted | Task: `FAIL` / `ESCALATE` | Non-blocking timeout aborts evaluation cleanly | `EVALUATION_FAILED` with timeout category |
| 3 | **Invalid Evaluator Output** | Model judge emits invalid JSON schema | Pydantic `ValidationError` in `GeminiSemanticEvaluator` | Evaluation result unparseable | Task: `FAIL` / `ESCALATE` | Catches parsing error; NEVER silently passes unverified output | Structured log and `EVALUATION_FAILED` event |
| 4 | **Evaluator Disagreement / Low Confidence** | Evaluator score below `min_pass_score` despite `PASS` verdict | Composite Evaluator score vs min threshold guard | Overrides verdict to `REQUIRES_REVISION` or `FAIL` | Gate correction to `REQUIRES_REVISION` | Enforces score threshold strictly | Metric logged in `EVALUATION_COMPLETED` |
| 5 | **Deterministic Validation Failure** | Missing required key, empty payload, or prohibited term | `DeterministicRuleEvaluator` (Layer 1) | Task output rejected before LLM call | Task: `REVISE` (if budget remains) or `FAIL` | Returns immediate feedback; saves LLM latency/tokens | `EVALUATION_COMPLETED` (Layer 1) |
| 6 | **Semantic Quality Failure** | Output lacks technical depth or accuracy | Layer 2 `GeminiSemanticEvaluator` returns `REQUIRES_REVISION` | Output rejected | Task: `REVISE` | Injects structured `RevisionContext` into task input | `REVISION_REQUESTED` event |
| 7 | **Revision Worsens Result** | Revision attempt scores lower than original | Evaluation history tracks score progression | Evaluator continues to reject output | Task: `REVISE` or `FAIL` | Enforces strict revision threshold | Score progression in `evaluation_history` |
| 8 | **Revision Budget Exhausted** | Task fails quality after `max_revisions` cycles | `revision_count >= max_revisions` guard | Task cannot continue revising | Task: `FAILED` (or `ESCALATED`) | Executes `rejection_policy` (`FAIL` cascades; `ESCALATE` notifies human) | `EVALUATION_FAILED` or `EVALUATION_ESCALATED` |
| 9 | **Repeated Evaluator Inconsistency** | Non-deterministic judge outputs contradictory feedback | Score oscillation across revisions | Revision budget exhausted | Task: `ESCALATE` | Escalates to human operator | Full audit trail in `evaluation_history` |
| 10 | **Gemini Rate Limit (429)** | Vendor API quota exhausted during evaluation | Evaluator provider catches 429 status code | Evaluation temporarily fails | Task: `RETRY` (infrastructure backoff) | Exponential backoff on provider call | `EVALUATION_FAILED` with 429 status |
| 11 | **Gemini Transient Service Failure (503)** | Provider service degradation | Provider raises 503 error | Evaluation temporarily fails | Task: `RETRY` | Transient retry on model provider | Telemetry log with 503 code |
| 12 | **Artifact Integrity Failure** | Produced artifact checksum does not match SHA-256 | Engine `hashlib.sha256()` validation | Task aborted before evaluation | Task: `FAILED` | Blocks corrupted artifact from entering evaluation or downstream DAG | `TASK_FAILED` with `artifact_integrity_failure` |
| 13 | **Evaluation Context Overflow** | Repeated revision feedback bloats prompt | Bounded `RevisionContext` isolates only latest feedback | Context bounded | Context preserved without history bloat | Token usage tracked in metrics |
| 14 | **Unsafe Automated Recovery** | High-risk action fails evaluation | Evaluator emits `ESCALATE` | Workflow pauses | Task: `ESCALATED` | Halts automated loop; alerts operator | `EVALUATION_ESCALATED` event |
| 15 | **Human Escalation Required** | Workflow task specified `rejection_policy: ESCALATE` | Engine executes `TaskCommand.ESCALATE` | Workflow paused | Task: `ESCALATED`<br>Workflow: `PAUSED` | Human operator reviews via approval mechanism | `EVALUATION_ESCALATED` event |

---

## 2. Invariant Guarantees

1. **Attempt Count vs Revision Count Independence**: `attempt_count` tracks transient execution retries; `revision_count` tracks quality revision cycles. They never conflate.
2. **Evaluator Failure Never Silently Passes**: An infrastructure crash, invalid JSON response, or timeout in the evaluator always results in a structured failure or escalation.
3. **Bounded Revision Budget**: Revision loops are strictly bounded by `max_revisions` (default 2, max 4). Uncontrolled autonomous loops are impossible.
4. **Context Isolation**: No database sessions, secrets, or raw SQL enter the evaluation request or prompt.
