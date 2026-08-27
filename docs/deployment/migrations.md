# Database Migrations Lifecycle & Safety Runbook

This runbook outlines Alembic schema migrations, safety rules, and execution workflows.

---

## 1. Migration History

The database schema is versioned sequentially:
1. **`v001_initial_schema`**: Foundational relational schema (workflows, tasks, executions, task executions, events, artifacts).
2. **`v002_evaluation_support`**: Adds `evaluation_history` (JSONB) to `task_executions`.
3. **`v003_task_leases`**: Adds `lease_until` (TIMESTAMP) and `leased_by` (VARCHAR) to `task_executions` for distributed concurrency and watchdog recovery.
4. **`v004_idempotency_constraint`**: Creates partial unique index `uq_workflow_executions_idempotency` enforcing database-level submission deduplication.

---

## 2. Running Migrations

### Local Development:
```bash
# Upgrade database to latest revision
alembic -c backend/alembic.ini upgrade head

# Check current revision status
alembic -c backend/alembic.ini current

# View migration history
alembic -c backend/alembic.ini history
```

### Production Deployment (Pre-Deploy Hook):
In `render.yaml`, migrations execute before Uvicorn starts:
```bash
alembic -c backend/alembic.ini upgrade head
```

---

## 3. Migration Safety Rules

1. **Never Drop Columns/Tables in Single Phase**: Use expand/contract patterns for schema modifications.
2. **Deterministic Reversibility**: Every migration must have a tested `downgrade()` implementation.
3. **Never Rewrite Applied Migrations**: Once committed to `main` and applied, existing migration files (`v001`–`v004`) are immutable.
4. **Index Creation**: Concurrency-sensitive indexes should use non-blocking creation strategies where applicable.
