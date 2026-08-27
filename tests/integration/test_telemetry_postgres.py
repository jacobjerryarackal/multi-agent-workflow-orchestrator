"""Integration tests for Phase 7.3 Telemetry, Metrics, and Observability with PostgreSQL."""

import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text

from app.main import create_app
from app.api.dependencies import get_db_session, get_model_provider
from app.core.telemetry import telemetry
from tests.unit.test_api_executions import get_canned_provider

POSTGRES_TEST_URL = "postgresql+asyncpg://postgres:12345678@localhost:5432/orchestrator_test_db"


@pytest_asyncio.fixture
async def pg_telemetry_client():
    """Provides an AsyncClient backed by a real PostgreSQL test database with telemetry hooks."""
    engine = create_async_engine(POSTGRES_TEST_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE workflows CASCADE;"))

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    from app.orchestration.background_manager import get_background_manager
    bg_manager = get_background_manager()
    old_factory = bg_manager._session_factory
    old_provider = bg_manager.model_provider
    bg_manager._session_factory = session_factory
    bg_manager.model_provider = get_canned_provider()

    app = create_app()

    async def override_get_db_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def override_get_model_provider():
        return get_canned_provider()

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_model_provider] = override_get_model_provider

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    bg_manager._session_factory = old_factory
    bg_manager.model_provider = old_provider

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE workflows CASCADE;"))

    await engine.dispose()


@pytest.mark.asyncio
async def test_health_telemetry_components(pg_telemetry_client: AsyncClient):
    """Verifies that /api/v1/health returns database pool and background manager metrics."""
    res = await pg_telemetry_client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] in ("healthy", "degraded")
    assert "components" in data
    assert "database" in data["components"]
    assert data["components"]["database"]["details"]["engine"] == "PostgreSQL 16"
    assert "pool_size" in data["components"]["database"]["details"]

    assert "background_manager" in data["components"]
    assert "active_executions" in data["components"]["background_manager"]["details"]


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint(pg_telemetry_client: AsyncClient):
    """Verifies that /api/v1/metrics returns Prometheus/OpenMetrics text format."""
    # Hit health to generate an HTTP request event
    await pg_telemetry_client.get("/api/v1/health")

    res = await pg_telemetry_client.get("/api/v1/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers.get("content-type", "")

    text_body = res.text
    assert "# HELP http_requests_total" in text_body
    assert "# TYPE http_requests_total counter" in text_body
    assert "http_requests_total" in text_body
    assert "database_pool_size" in text_body


@pytest.mark.asyncio
async def test_json_telemetry_snapshot(pg_telemetry_client: AsyncClient):
    """Verifies that /api/v1/telemetry returns a structured JSON metrics snapshot."""
    res = await pg_telemetry_client.get("/api/v1/telemetry")
    assert res.status_code == 200
    data = res.json()

    assert "counters" in data
    assert "gauges" in data
    assert "histograms" in data
    assert "timestamp" in data
    assert "database_pool_size" in data["gauges"]


@pytest.mark.asyncio
async def test_workflow_execution_increments_telemetry(pg_telemetry_client: AsyncClient):
    """Verifies end-to-end telemetry counter and histogram emission during workflow lifecycle."""
    # 1. Register workflow
    spec = {
        "name": "Telemetry Integration Test Workflow",
        "description": "Validates metric counter increments",
        "tasks": [
            {
                "task_key": "task_1",
                "name": "Planner Task",
                "agent_id": "planner_agent",
                "depends_on": [],
                "input_mappings": {},
                "static_inputs": {"objective": "Plan integration test"},
                "timeout_seconds": 30,
            }
        ],
    }

    create_res = await pg_telemetry_client.post("/api/v1/workflows", json=spec)
    assert create_res.status_code == 201
    workflow_id = create_res.json()["id"]

    # 2. Submit execution
    sub_res = await pg_telemetry_client.post(
        f"/api/v1/workflows/{workflow_id}/executions",
        json={"input_data": {"test": "true"}},
    )
    assert sub_res.status_code == 201
    execution_id = sub_res.json()["id"]

    # Wait for execution to finish
    for _ in range(50):
        status_res = await pg_telemetry_client.get(f"/api/v1/executions/{execution_id}")
        assert status_res.status_code == 200
        if status_res.json()["status"] in ("COMPLETED", "FAILED"):
            break
        await asyncio.sleep(0.1)

    # 3. Query telemetry JSON snapshot
    telemetry_res = await pg_telemetry_client.get("/api/v1/telemetry")
    assert telemetry_res.status_code == 200
    metrics_snapshot = telemetry_res.json()

    # Assert workflow submissions counter exists
    assert "workflow_submissions_total" in metrics_snapshot["counters"]
    assert "task_started_total" in metrics_snapshot["counters"]
    assert "task_completed_total" in metrics_snapshot["counters"]
    assert "workflow_completed_total" in metrics_snapshot["counters"]
