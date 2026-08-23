"""Unit tests for Workflow API endpoints (POST /api/v1/workflows, GET /api/v1/workflows, GET /api/v1/workflows/{id})."""

import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import create_app
from app.api.dependencies import get_db_session


@pytest.fixture
def app_instance(db_session: AsyncSession) -> FastAPI:
    app = create_app()

    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    return app


@pytest_asyncio.fixture
async def client(app_instance: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_workflow_success(client: AsyncClient):
    payload = {
        "name": "research_pipeline",
        "version": 1,
        "description": "Multi-agent research and synthesis pipeline",
        "input_schema": {"type": "object", "properties": {"topic": {"type": "string"}}},
        "output_schema": {"type": "object"},
        "tasks": [
            {
                "task_key": "plan_task",
                "name": "Planning Task",
                "agent_id": "planner_agent",
                "depends_on": [],
                "static_inputs": {"focus": "overview"},
                "timeout_seconds": 60,
                "retry_policy": {"max_attempts": 3},
                "approval_gate": {"required": False},
                "evaluation_gate": {"enabled": False},
            },
            {
                "task_key": "research_task",
                "name": "Research Task",
                "agent_id": "researcher_agent",
                "depends_on": ["plan_task"],
                "input_mappings": {"plan": "plan_task.plan"},
                "timeout_seconds": 60,
                "retry_policy": {"max_attempts": 2},
                "approval_gate": {"required": False},
                "evaluation_gate": {"enabled": False},
            },
        ],
        "max_workflow_duration_seconds": 600,
        "max_parallel_tasks": 5,
    }

    response = await client.post("/api/v1/workflows", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "research_pipeline"
    assert len(data["tasks"]) == 2
    assert "id" in data


@pytest.mark.asyncio
async def test_create_workflow_cyclic_dependency_rejected(client: AsyncClient):
    payload = {
        "name": "cyclic_workflow",
        "version": 1,
        "description": "Workflow with cycle",
        "input_schema": {},
        "output_schema": {},
        "tasks": [
            {
                "task_key": "task_a",
                "name": "Task A",
                "agent_id": "planner_agent",
                "depends_on": ["task_b"],
            },
            {
                "task_key": "task_b",
                "name": "Task B",
                "agent_id": "researcher_agent",
                "depends_on": ["task_a"],
            },
        ],
    }

    response = await client.post("/api/v1/workflows", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_get_and_list_workflows(client: AsyncClient):
    # 1. Create a workflow
    payload = {
        "name": "list_test_pipeline",
        "version": 1,
        "description": "Listing test pipeline",
        "tasks": [
            {
                "task_key": "root_task",
                "name": "Root Task",
                "agent_id": "planner",
                "depends_on": [],
            }
        ],
    }
    create_res = await client.post("/api/v1/workflows", json=payload)
    assert create_res.status_code == 201
    wf_id = create_res.json()["id"]

    # 2. Get workflow by ID
    get_res = await client.get(f"/api/v1/workflows/{wf_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == wf_id
    assert get_res.json()["name"] == "list_test_pipeline"

    # 3. List workflows
    list_res = await client.get("/api/v1/workflows")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total_count"] >= 1
    assert any(item["id"] == wf_id for item in list_data["items"])


@pytest.mark.asyncio
async def test_get_workflow_not_found(client: AsyncClient):
    response = await client.get("/api/v1/workflows/non_existent_wf_9999")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"
