"""Unit tests for Execution API endpoints."""

import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import create_app
from app.api.dependencies import get_db_session, get_model_provider
from tests.conftest import MockModelProvider


def get_canned_provider() -> MockModelProvider:
    return MockModelProvider(
        canned_responses={
            "PlanOutput": {
                "plan_summary": "Execution plan",
                "sub_tasks": [
                    {
                        "task_key": "res_1",
                        "name": "Research Task",
                        "description": "Investigate facts",
                        "required_capability": "research",
                        "depends_on": [],
                    }
                ],
                "risk_factors": ["None identified"],
            },
            "ResearchOutput": {
                "findings": [
                    {
                        "topic": "PostgreSQL Architecture",
                        "detail": "PostgreSQL 16 supports robust ACID transactions and row-level locking.",
                        "sources_cited": ["https://postgresql.org"],
                        "confidence": 0.95,
                    }
                ],
                "assumptions": ["Standard PostgreSQL config"],
                "uncertainties": [],
                "recommended_follow_up": [],
            },
            "AnalysisOutput": {
                "insights": ["PostgreSQL 16 is ACID compliant"],
                "tradeoffs": [
                    {
                        "option_name": "Postgres",
                        "pros": ["ACID", "Reliable"],
                        "cons": ["Connection overhead"],
                        "impact_score": 0.9,
                    }
                ],
                "conclusions": ["Adopt PostgreSQL 16"],
                "confidence_score": 0.95,
            },
            "ReviewOutput": {
                "decision": "PASS",
                "passed_checks": ["ACID compliance"],
                "failed_checks": [],
                "issues": [],
                "required_changes": [],
                "confidence": 0.95,
            },
            "SynthesisOutput": {
                "title": "PostgreSQL 16 Technical Synthesis",
                "executive_summary": "Synthesized final report on PostgreSQL 16",
                "key_conclusions": ["PostgreSQL 16 fulfills all requirements"],
                "detailed_report": "# Comprehensive Report\nPostgreSQL is robust and ACID compliant.",
                "review_acknowledgment": "Reviewed and approved without caveats.",
            },
            "QualityScore": {
                "overall_score": 0.95,
                "completeness": 0.95,
                "factual_grounding": 0.95,
                "relevance": 0.95,
                "coherence": 0.95,
                "critique": "Quality meets standards",
                "passed": True,
            },
        }
    )


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
async def test_submit_and_run_workflow_execution(client: AsyncClient):
    # 1. Create a 2-step workflow: Planner -> Researcher
    wf_payload = {
        "name": "e2e_exec_workflow",
        "version": 1,
        "description": "Execution test workflow",
        "tasks": [
            {
                "task_key": "plan_task",
                "name": "Plan",
                "agent_id": "planner_agent",
                "depends_on": [],
                "static_inputs": {"objective": "Decompose transformer architecture research"},
            },
            {
                "task_key": "research_task",
                "name": "Research",
                "agent_id": "researcher_agent",
                "depends_on": ["plan_task"],
                "static_inputs": {"query": "Transformer self-attention details"},
                "input_mappings": {"plan": "plan_task.plan_summary"},
            },
        ],
    }
    wf_res = await client.post("/api/v1/workflows", json=wf_payload)
    assert wf_res.status_code == 201
    wf_id = wf_res.json()["id"]

    # 2. Submit execution
    exec_payload = {
        "input_data": {"objective": "Explain transformers"},
        "idempotency_key": "idem-key-101",
        "trigger_type": "api",
    }
    exec_res = await client.post(f"/api/v1/workflows/{wf_id}/executions", json=exec_payload)
    assert exec_res.status_code == 201
    exec_data = exec_res.json()
    assert exec_data["status"] == "COMPLETED"
    assert len(exec_data["tasks"]) == 2
    assert all(t["status"] == "COMPLETED" for t in exec_data["tasks"])

    exec_id = exec_data["id"]

    # 3. Test Idempotency (submitting same idempotency key returns existing execution)
    dup_res = await client.post(f"/api/v1/workflows/{wf_id}/executions", json=exec_payload)
    assert dup_res.status_code == 201
    assert dup_res.json()["id"] == exec_id

    # 4. Get execution detail
    detail_res = await client.get(f"/api/v1/executions/{exec_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == exec_id

    # 5. List executions
    list_res = await client.get(f"/api/v1/executions?workflow_id={wf_id}")
    assert list_res.status_code == 200
    assert list_res.json()["total_count"] >= 1


@pytest.mark.asyncio
async def test_cancel_execution(client: AsyncClient):
    # 1. Create a workflow
    wf_payload = {
        "name": "cancel_test_wf",
        "version": 1,
        "description": "Cancel test",
        "tasks": [
            {
                "task_key": "t1",
                "name": "Task 1",
                "agent_id": "planner_agent",
                "depends_on": [],
                "static_inputs": {"objective": "Quick plan"},
            }
        ],
    }
    wf_res = await client.post("/api/v1/workflows", json=wf_payload)
    wf_id = wf_res.json()["id"]

    # 2. Submit execution
    exec_res = await client.post(
        f"/api/v1/workflows/{wf_id}/executions",
        json={"input_data": {"objective": "Plan"}, "idempotency_key": "cancel-key-1"},
    )
    exec_id = exec_res.json()["id"]

    # 3. Trying to cancel completed execution should return 409 (Conflict / Invalid State Transition)
    cancel_res = await client.post(f"/api/v1/executions/{exec_id}/cancel")
    assert cancel_res.status_code == 409
    assert cancel_res.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


@pytest.mark.asyncio
async def test_approval_gate_endpoints(client: AsyncClient):
    # 1. Create workflow with human approval gate
    wf_payload = {
        "name": "approval_test_wf",
        "version": 1,
        "description": "Approval test",
        "tasks": [
            {
                "task_key": "planning_gate",
                "name": "Planning Gate",
                "agent_id": "planner_agent",
                "depends_on": [],
                "static_inputs": {"objective": "Formulate execution blueprint"},
                "approval_gate": {
                    "required": True,
                    "approver_roles": ["admin"],
                    "timeout_seconds": 3600,
                },
            }
        ],
    }
    wf_res = await client.post("/api/v1/workflows", json=wf_payload)
    wf_id = wf_res.json()["id"]

    # 2. Submit execution (pauses in WAITING_APPROVAL)
    exec_res = await client.post(
        f"/api/v1/workflows/{wf_id}/executions",
        json={"input_data": {"objective": "Formulate blueprint"}},
    )
    assert exec_res.status_code == 201
    exec_data = exec_res.json()
    exec_id = exec_data["id"]

    task = next(t for t in exec_data["tasks"] if t["task_key"] == "planning_gate")
    assert task["status"] == "WAITING_APPROVAL"

    # 3. Approve the task
    approve_res = await client.post(
        f"/api/v1/executions/{exec_id}/tasks/planning_gate/approve",
        json={"approver": "lead_operator", "comment": "Plan approved for execution"},
    )
    assert approve_res.status_code == 200
    approved_task = approve_res.json()
    assert approved_task["status"] == "COMPLETED"

    # 4. Attempting to approve an already completed task should return 403 (Approval Gate Violation)
    dup_approve = await client.post(
        f"/api/v1/executions/{exec_id}/tasks/planning_gate/approve",
        json={"approver": "lead_operator"},
    )
    assert dup_approve.status_code == 403
    assert dup_approve.json()["error"]["code"] == "APPROVAL_GATE_VIOLATION"
