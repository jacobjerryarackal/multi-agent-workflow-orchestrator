import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from sqlalchemy import text
from app.main import create_app
from app.api.dependencies import get_db_session, get_model_provider
from tests.unit.test_api_executions import get_canned_provider

POSTGRES_TEST_URL = "postgresql+asyncpg://postgres:12345678@localhost:5432/orchestrator_test_db"


@pytest_asyncio.fixture
async def pg_api_client():
    """Provides an AsyncClient backed by a real PostgreSQL test database."""
    engine = create_async_engine(POSTGRES_TEST_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE workflows CASCADE;"))

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    from app.orchestration.background_manager import get_background_manager
    bg_manager = get_background_manager()
    old_factory = bg_manager._session_factory
    bg_manager._session_factory = session_factory

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

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE workflows CASCADE;"))

    await engine.dispose()


@pytest.mark.asyncio
async def test_full_api_multi_agent_lifecycle_postgres(pg_api_client: AsyncClient):
    """
    Validates complete REST API lifecycle:
    1. Health check verification
    2. Agent catalog query
    3. Workflow DAG registration (Planner -> Researcher -> Synthesizer)
    4. Execution submission and completion
    5. Detail retrieval and output verification
    6. Audit event query
    7. Artifact retrieval
    """
    client = pg_api_client

    # 1. Health check
    health_res = await client.get("/api/v1/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] in ("healthy", "degraded")
    assert health_res.json()["components"]["database"]["status"] == "healthy"

    # 2. Agent catalog
    agents_res = await client.get("/api/v1/agents")
    assert agents_res.status_code == 200
    assert agents_res.json()["total_count"] == 5

    # 3. Workflow Registration: Planner -> Researcher -> Synthesizer
    wf_payload = {
        "name": "full_research_pipeline",
        "version": 1,
        "description": "Production research and synthesis pipeline",
        "tasks": [
            {
                "task_key": "planner_node",
                "name": "Decompose Query",
                "agent_id": "planner_agent",
                "depends_on": [],
                "static_inputs": {"objective": "Explain ACID properties in PostgreSQL 16"},
            },
            {
                "task_key": "researcher_node",
                "name": "Investigate Findings",
                "agent_id": "researcher_agent",
                "depends_on": ["planner_node"],
                "static_inputs": {"query": "PostgreSQL 16 ACID properties"},
                "input_mappings": {"plan": "planner_node.plan_summary"},
            },
            {
                "task_key": "synthesizer_node",
                "name": "Synthesize Deliverable",
                "agent_id": "synthesizer_agent",
                "depends_on": ["researcher_node"],
                "input_mappings": {"inputs": "researcher_node.findings"},
            },
        ],
        "max_workflow_duration_seconds": 300,
        "max_parallel_tasks": 3,
    }

    create_wf_res = await client.post("/api/v1/workflows", json=wf_payload)
    assert create_wf_res.status_code == 201
    workflow_id = create_wf_res.json()["id"]

    # 4. Submit Execution (Returns HTTP 201 immediately with status QUEUED or RUNNING)
    submit_res = await client.post(
        f"/api/v1/workflows/{workflow_id}/executions",
        json={
            "input_data": {"objective": "Explain ACID properties in PostgreSQL 16"},
            "idempotency_key": "e2e-pg-idem-001",
            "trigger_type": "api",
        },
    )
    assert submit_res.status_code == 201
    exec_data = submit_res.json()
    assert exec_data["status"] in ("QUEUED", "RUNNING")
    execution_id = exec_data["id"]

    # Poll until background execution completes
    for _ in range(100):
        await asyncio.sleep(0.05)
        detail_res = await client.get(f"/api/v1/executions/{execution_id}")
        if detail_res.json()["status"] == "COMPLETED":
            break

    # 5. Retrieve Execution Detail
    detail_res = await client.get(f"/api/v1/executions/{execution_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["status"] == "COMPLETED"
    assert len(detail["tasks"]) == 3
    assert all(t["status"] == "COMPLETED" for t in detail["tasks"])
    assert "planner_node" in detail["final_outputs"]
    assert "researcher_node" in detail["final_outputs"]
    assert "synthesizer_node" in detail["final_outputs"]

    # 6. Audit Trail Query
    events_res = await client.get(f"/api/v1/executions/{execution_id}/events")
    assert events_res.status_code == 200
    events = events_res.json()["items"]
    assert len(events) >= 5
    event_types = [e["event_type"] for e in events]
    assert "WORKFLOW_STARTED" in event_types
    assert "WORKFLOW_COMPLETED" in event_types
    assert "TASK_STARTED" in event_types
    assert "TASK_COMPLETED" in event_types

    # 7. Artifacts Query
    artifacts_res = await client.get(f"/api/v1/executions/{execution_id}/artifacts")
    assert artifacts_res.status_code == 200
