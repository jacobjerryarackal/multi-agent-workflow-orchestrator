# ADR-004: Multi-Tier Failure Classification, Circuit Breaking & Human Escalation

**Status:** Accepted  
**Date:** 2026-08-23  

---

## Context

Multi-agent pipelines encounter diverse failure modes ranging from temporary API rate limits to permanent schema contract errors and quality rejections. A naive "retry everything 3 times" policy leads to:
1. Wasted API tokens and latency retrying fatal errors (e.g. invalid schemas, cyclic DAGs).
2. Thundering herd problems crashing overloaded upstream providers.
3. Silent delivery of factually incorrect outputs to downstream users.

We evaluated:
1. **Blind Global Retry**: Fixed 3 retries with constant sleep for any exception.
2. **Crash-Fast (No Retries)**: Any failure aborts the entire workflow immediately.
3. **Multi-Tier Classification & Dynamic Recovery**: Classify errors into 8 categories; apply tailored recovery policies (Jittered Exponential Backoff, Circuit Breakers, Reflection Prompts, Fallback Routing, Human Approval Escalation).

---

## Decision

We chose **Option 3: Multi-Tier Classification & Dynamic Recovery**.

1. **Selective Retries**: Only transient errors (`INFRASTRUCTURE_PROVIDER_FAILURE`, `TEMPORAL_FAILURE`) trigger backoff retries.
2. **Schema Reflection**: Schema errors trigger a single self-correction prompt containing the exact Pydantic validation diff.
3. **Circuit Breaking**: Provider outages trip rolling circuit breakers, preventing cascading API quota depletion.
4. **Human-in-the-Loop Escalation**: Tasks requiring high stakes verification or failing quality evaluation gates transition into `WAITING_APPROVAL` / `ESCALATED` states without halting unrelated DAG branches.

---

## Consequences

* **Positive**:
  - High pipeline resilience without infinite retry loops or wasted token spend.
  - Predictable system degradation ("slower but correct" rather than "fast but wrong").
  - Complete operational visibility into recovery actions via telemetry events.
* **Negative / Trade-offs**:
  - Requires maintaining a comprehensive failure classification engine and circuit breaker state tracking.
