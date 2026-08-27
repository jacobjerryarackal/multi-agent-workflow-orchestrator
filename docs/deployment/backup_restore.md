# Database Backup & Restoration Runbook

This operational runbook explains backup procedures, disaster recovery, and data verification for PostgreSQL.

---

## 1. What Needs to Be Backed Up?

The state of the orchestrator is contained in PostgreSQL:
- **`workflows` & `workflow_tasks`**: Registered workflow definitions and DAG dependency graphs.
- **`workflow_executions` & `task_executions`**: Historical execution runs, token usage, evaluation records.
- **`workflow_events`**: Immutable audit trails and state transition logs.
- **`artifacts`**: Generated outputs, markdown reports, and cryptographic SHA-256 hashes.
- **`alembic_version`**: Schema migration version pointer.

---

## 2. Backup Execution (pg_dump)

Run a compressed binary dump from a secure terminal with access to the database:

```bash
# Export full database with schema and data
pg_dump -Fc --no-acl --no-owner -h <DB_HOST> -p <DB_PORT> -U <DB_USER> -d <DB_NAME> -f orchestrator_backup_$(date +%Y%m%d_%H%M%S).dump
```

*Flags explained*:
- `-Fc`: Custom compressed format (supports parallel restoration).
- `--no-acl --no-owner`: Omits ownership/privilege statements for seamless restoration to different database users.

---

## 3. Restoration Procedure (pg_restore)

To restore a backup into a new or recovered PostgreSQL instance:

```bash
# 1. Ensure target database exists
createdb -h <DB_HOST> -p <DB_PORT> -U <DB_USER> <TARGET_DB_NAME>

# 2. Restore database objects and data
pg_restore -h <DB_HOST> -p <DB_PORT> -U <DB_USER> -d <TARGET_DB_NAME> --clean --if-exists orchestrator_backup_<TIMESTAMP>.dump
```

---

## 4. Post-Restoration Verification & Alignment

1. **Verify Migration Status**:
   ```bash
   alembic -c backend/alembic.ini current
   ```
   Ensure the current database revision matches `head` (currently `v004_idempotency_constraint`). If missing, run `alembic upgrade head`.

2. **Verify Record Integrity**:
   Run a sanity check query:
   ```sql
   SELECT count(*) FROM workflows;
   SELECT count(*) FROM workflow_executions;
   SELECT count(*) FROM artifacts;
   ```

3. **Reclaim In-Flight Workflows**:
   Upon booting the backend, `BackgroundExecutionManager` will automatically scan for any executions left in `RUNNING` state during the restore and resume them cleanly.
