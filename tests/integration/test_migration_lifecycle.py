"""
Alembic migration lifecycle test suite verifying clean schema, upgrade, downgrade, and column integrity on PostgreSQL 16.
"""

import subprocess
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

POSTGRES_TEST_URL = "postgresql+asyncpg://postgres:12345678@localhost:5432/orchestrator_test_db"


@pytest.mark.asyncio
async def test_complete_migration_lifecycle():
    # 1. Clean slate PostgreSQL database
    engine = create_async_engine(POSTGRES_TEST_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()

    # 2. Upgrade from clean database to head (Applies v001 + v002)
    proc_up1 = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd="backend",
        capture_output=True,
        text=True,
    )
    assert proc_up1.returncode == 0, f"alembic upgrade head failed: {proc_up1.stderr}"

    # 3. Check current revision
    proc_curr = subprocess.run(
        ["alembic", "current"],
        cwd="backend",
        capture_output=True,
        text=True,
    )
    assert "v002_evaluation_support" in proc_curr.stdout

    # 4. Verify PostgreSQL tables and columns
    engine = create_async_engine(POSTGRES_TEST_URL, echo=False)
    async with engine.begin() as conn:
        tables_res = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
        )
        tables = [row[0] for row in tables_res.fetchall()]
        expected_tables = ["alembic_version", "artifacts", "task_executions", "workflow_events", "workflow_executions", "workflow_tasks", "workflows"]
        for tbl in expected_tables:
            assert tbl in tables, f"Missing table: {tbl}"

        # Check task_executions columns (Phase 5 additions)
        cols_res = await conn.execute(
            text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'task_executions'")
        )
        cols = {row[0]: row[1] for row in cols_res.fetchall()}
        assert "revision_count" in cols
        assert "evaluation_history" in cols
    await engine.dispose()

    # 5. Test alembic downgrade base (Rolls back v002 + v001 to empty)
    proc_down_base = subprocess.run(
        ["alembic", "downgrade", "base"],
        cwd="backend",
        capture_output=True,
        text=True,
    )
    assert proc_down_base.returncode == 0, f"alembic downgrade base failed: {proc_down_base.stderr}"

    # Verify tables dropped (except alembic_version)
    engine = create_async_engine(POSTGRES_TEST_URL, echo=False)
    async with engine.begin() as conn:
        tables_res = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name != 'alembic_version'")
        )
        remaining_tables = tables_res.fetchall()
        assert len(remaining_tables) == 0, f"Tables remaining after downgrade base: {remaining_tables}"
    await engine.dispose()

    # 6. Test alembic upgrade head again (Re-applies v001 + v002 from base)
    proc_up2 = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd="backend",
        capture_output=True,
        text=True,
    )
    assert proc_up2.returncode == 0, f"alembic re-upgrade head failed: {proc_up2.stderr}"

    # 7. Test alembic downgrade -1 (v002 -> v001)
    proc_down1 = subprocess.run(
        ["alembic", "downgrade", "-1"],
        cwd="backend",
        capture_output=True,
        text=True,
    )
    assert proc_down1.returncode == 0, f"alembic downgrade -1 failed: {proc_down1.stderr}"

    # Verify column evaluation_history was dropped
    engine = create_async_engine(POSTGRES_TEST_URL, echo=False)
    async with engine.begin() as conn:
        cols_res = await conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'task_executions'")
        )
        cols = [row[0] for row in cols_res.fetchall()]
        assert "evaluation_history" not in cols
    await engine.dispose()

    # 8. Re-upgrade to head (v001 -> v002)
    proc_up3 = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd="backend",
        capture_output=True,
        text=True,
    )
    assert proc_up3.returncode == 0, f"alembic final upgrade head failed: {proc_up3.stderr}"

    # Verify columns restored
    engine = create_async_engine(POSTGRES_TEST_URL, echo=False)
    async with engine.begin() as conn:
        cols_res = await conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'task_executions'")
        )
        cols = [row[0] for row in cols_res.fetchall()]
        assert "evaluation_history" in cols
        assert "revision_count" in cols
    await engine.dispose()
