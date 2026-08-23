# ADR-002: Durable Workflow State & Event Sourcing in PostgreSQL

**Status:** Accepted  
**Date:** 2026-08-23  

---

## Context

Workflow executions can span multiple minutes, encounter external provider failures, pause for human approval gates, or require administrator recovery after server restarts. We evaluated three state persistence strategies:
1. **In-Memory State**: Fast, ephemeral dictionary state stored in Python process memory.
2. **Redis Key-Value Cache**: Fast distributed cache, but lacks relational integrity, joins, and complex audit queries.
3. **PostgreSQL Relational + JSONB Event Store**: Fully ACID-compliant database with relational schema for workflows/tasks and JSONB fields for unstructured outputs and immutable events.

---

## Decision

We chose **Option 3: PostgreSQL Relational + JSONB Event Store**.

1. **Durability & Crash Recovery**: If the orchestrator server crashes or restarts, running workflows can be resumed or reconciled from the last committed task checkpoint in PostgreSQL.
2. **First-Class Audit Trail**: Every state transition emits an immutable `WorkflowEvent` row, providing a complete historical log for observability, compliance, and debugging.
3. **Hybrid Schema Flexibility**: Relational tables (`workflows`, `workflow_executions`, `task_executions`) provide structured constraints, while `JSONB` columns accommodate diverse agent input/output payloads and artifacts.

---

## Consequences

* **Positive**:
  - Full transactional guarantees on state transitions.
  - Rich SQL querying for execution history, failure metrics, and timeline dashboards.
  - Native support on managed cloud platforms (Render, Supabase, Neon).
* **Negative / Trade-offs**:
  - Requires database migrations (Alembic) and async database connection management (`asyncpg` / SQLAlchemy).
