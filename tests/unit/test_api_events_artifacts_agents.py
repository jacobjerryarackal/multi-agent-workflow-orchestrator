"""Unit tests for Events, Artifacts, and Agents API endpoints."""

import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import create_app
from app.api.dependencies import get_db_session, get_model_provider
from app.domain.models.artifact import Artifact, ArtifactType
from app.persistence.repositories import SqlArtifactRepository
from tests.unit.test_api_executions import get_canned_provider


@pytest.fixture
def app_instance(db_session: AsyncSession) -> FastAPI:
    app = create_app()

    async def override_get_db_session():
        yield db_session

    def override_get_model_provider():
        return get_canned_provider()

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_model_provider] = override_get_model_provider
    return app


@pytest_asyncio.fixture
async def client(app_instance: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.mark.asyncio
async def test_list_audit_events_for_execution(client: AsyncClient):
    # 1. Create and execute workflow
    wf_payload = {
        "name": "audit_event_test_wf",
        "version": 1,
        "description": "Event test",
        "tasks": [
            {
                "task_key": "step_1",
                "name": "Step 1",
                "agent_id": "planner_agent",
                "depends_on": [],
                "static_inputs": {"objective": "Plan audit events"},
            }
        ],
    }
    wf_res = await client.post("/api/v1/workflows", json=wf_payload)
    wf_id = wf_res.json()["id"]

    exec_res = await client.post(
        f"/api/v1/workflows/{wf_id}/executions",
        json={"input_data": {"objective": "Plan audit events"}},
    )
    exec_id = exec_res.json()["id"]

    # 2. Query events
    events_res = await client.get(f"/api/v1/executions/{exec_id}/events")
    assert events_res.status_code == 200
    events_data = events_res.json()
    assert events_data["total_count"] >= 3
    event_types = [e["event_type"] for e in events_data["items"]]
    assert "WORKFLOW_STARTED" in event_types
    assert "TASK_STARTED" in event_types
    assert "WORKFLOW_COMPLETED" in event_types


@pytest.mark.asyncio
async def test_artifacts_endpoints(client: AsyncClient, db_session: AsyncSession):
    # 1. Create a dummy execution
    wf_res = await client.post(
        "/api/v1/workflows",
        json={
            "name": "art_wf",
            "version": 1,
            "description": "Art test",
            "tasks": [
                {
                    "task_key": "t1",
                    "name": "T1",
                    "agent_id": "planner_agent",
                    "depends_on": [],
                    "static_inputs": {"objective": "Plan artifact workflow"},
                }
            ],
        },
    )
    wf_id = wf_res.json()["id"]
    exec_res = await client.post(
        f"/api/v1/workflows/{wf_id}/executions",
        json={"input_data": {"objective": "Plan artifact workflow"}},
    )
    exec_id = exec_res.json()["id"]

    # 2. Persist an artifact directly
    art_repo = SqlArtifactRepository(db_session)
    artifact = Artifact.create_from_data(
        workflow_execution_id=exec_id,
        task_key="t1",
        name="market_research_report",
        artifact_type=ArtifactType.JSON,
        data={"summary": "Market insights 2026", "score": 95},
    )
    await art_repo.save_artifact(artifact)

    # 3. List artifacts for execution
    list_res = await client.get(f"/api/v1/executions/{exec_id}/artifacts")
    assert list_res.status_code == 200
    assert list_res.json()["total_count"] >= 1
    assert any(a["artifact_name"] == "market_research_report" for a in list_res.json()["items"])

    # 4. Get artifact with SHA-256 validation
    get_res = await client.get(f"/api/v1/executions/{exec_id}/artifacts/{artifact.id}")
    assert get_res.status_code == 200
    art_data = get_res.json()
    assert art_data["verified"] is True
    assert art_data["data"]["score"] == 95

    # 5. Non-existent artifact returns 404
    missing_res = await client.get(f"/api/v1/executions/{exec_id}/artifacts/non_existent_art_999")
    assert missing_res.status_code == 404


@pytest.mark.asyncio
async def test_agents_endpoints(client: AsyncClient):
    # 1. List agents (should return 5 built-in agents)
    list_res = await client.get("/api/v1/agents")
    assert list_res.status_code == 200
    agents_data = list_res.json()
    assert agents_data["total_count"] == 5
    agent_ids = [a["agent_id"] for a in agents_data["items"]]
    assert "planner_agent" in agent_ids
    assert "researcher_agent" in agent_ids
    assert "analyst_agent" in agent_ids
    assert "reviewer_agent" in agent_ids
    assert "synthesizer_agent" in agent_ids

    # 2. Get specific agent
    get_res = await client.get("/api/v1/agents/researcher_agent")
    assert get_res.status_code == 200
    agent = get_res.json()
    assert agent["agent_id"] == "researcher_agent"
    assert len(agent["capabilities"]) > 0

    # 3. Unknown agent returns 404
    missing_res = await client.get("/api/v1/agents/unknown_agent_999")
    assert missing_res.status_code == 404
    assert missing_res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
