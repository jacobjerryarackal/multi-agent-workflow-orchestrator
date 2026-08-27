"""
Live End-to-End Execution Evidence Collector for Phase 6.4.1.
Executes a real workflow through the live running stack:
FastAPI -> App Service -> Execution Engine -> Agents -> Evaluator -> PostgreSQL -> Events -> Artifacts -> Frontend.
"""

import asyncio
import json
import uuid
import httpx
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

POSTGRES_TEST_URL = "postgresql+asyncpg://postgres:12345678@localhost:5432/orchestrator_test_db"
API_BASE = "http://localhost:8000"
FRONTEND_BASE = "http://localhost:3000"


async def main():
    async with httpx.AsyncClient(base_url=API_BASE, timeout=120.0) as client:
        # 1. Health Check
        health_resp = await client.get("/api/v1/health")
        print(f"[1] Backend Health HTTP {health_resp.status_code}: {health_resp.json()['status']}")

        # 2. Register Workflow
        wf_name = f"e2e_evidence_wf_{uuid.uuid4().hex[:6]}"
        wf_spec = {
            "name": wf_name,
            "description": "Deterministic End-to-End Production Readiness Pipeline",
            "tasks": [
                {
                    "task_key": "step_1_plan",
                    "name": "Decomposition Stage",
                    "agent_id": "planner_agent",
                    "depends_on": [],
                    "timeout_seconds": 60,
                    "retry_policy": {"max_attempts": 2},
                    "approval_gate": {"required": False},
                    "evaluation_gate": {"enabled": False}
                },
                {
                    "task_key": "step_2_analyze",
                    "name": "Quality Analysis Stage",
                    "agent_id": "analyst_agent",
                    "depends_on": ["step_1_plan"],
                    "input_mappings": {"research_findings": "step_1_plan.sub_tasks"},
                    "timeout_seconds": 60,
                    "retry_policy": {"max_attempts": 2},
                    "approval_gate": {"required": False},
                    "evaluation_gate": {
                        "enabled": True,
                        "evaluator_name": "composite_quality_evaluator",
                        "min_pass_score": 0.7,
                        "max_revisions": 2,
                        "deterministic_rules": ["output_payload_present"]
                    }
                }
            ]
        }
        wf_resp = await client.post("/api/v1/workflows", json=wf_spec)
        assert wf_resp.status_code == 201, f"Workflow creation failed: {wf_resp.text}"
        wf_data = wf_resp.json()
        workflow_id = wf_data["id"]
        print(f"[2] Registered Workflow: ID={workflow_id}, Name={wf_name}")

        # 3. Trigger Execution
        exec_payload = {
            "input_data": {
                "objective": "Verify complete live execution lifecycle for Phase 6.4.1",
                "environment": "production_validation"
            }
        }
        exec_resp = await client.post(f"/api/v1/workflows/{workflow_id}/executions", json=exec_payload)
        assert exec_resp.status_code == 201, f"Execution submission failed: {exec_resp.text}"
        exec_data = exec_resp.json()
        execution_id = exec_data["id"]
        print(f"[3] Submitted Execution: ID={execution_id}, Status={exec_data['status']}")

        # 4. Poll until terminal
        final_exec = None
        for _ in range(60):
            await asyncio.sleep(1.0)
            status_resp = await client.get(f"/api/v1/executions/{execution_id}")
            if status_resp.status_code == 200:
                final_exec = status_resp.json()
                if final_exec["status"] in ["COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"]:
                    break

        print(f"[4] Execution Finished with Status: {final_exec['status']}")

        # 5. Fetch Events via API
        events_resp = await client.get(f"/api/v1/executions/{execution_id}/events")
        events = events_resp.json().get("items", []) if events_resp.status_code == 200 else []
        print(f"[5] API Events Count: {len(events)}")

        # 6. Fetch Artifacts via API
        artifacts_resp = await client.get(f"/api/v1/executions/{execution_id}/artifacts")
        artifacts = artifacts_resp.json().get("items", []) if artifacts_resp.status_code == 200 else []
        print(f"[6] API Artifacts Count: {len(artifacts)}")

    # 7. Check Frontend Next.js Route for Execution
    async with httpx.AsyncClient(base_url=FRONTEND_BASE, timeout=30.0) as fe_client:
        fe_resp = await fe_client.get(f"/executions/{execution_id}")
        print(f"[7] Frontend Execution Page HTTP {fe_resp.status_code}")

    # 8. Query PostgreSQL Directly for Verification
    engine = create_async_engine(POSTGRES_TEST_URL, echo=False)
    async with engine.begin() as conn:
        db_exec = (await conn.execute(
            text("SELECT id, workflow_id, status, started_at, completed_at, error_summary FROM workflow_executions WHERE id = :id"),
            {"id": execution_id}
        )).fetchone()

        db_tasks = (await conn.execute(
            text("SELECT id, task_key, agent_id, status, attempt_count, revision_count, execution_duration_ms FROM task_executions WHERE workflow_execution_id = :id"),
            {"id": execution_id}
        )).fetchall()

        db_events_count = (await conn.execute(
            text("SELECT count(*) FROM workflow_events WHERE workflow_execution_id = :id"),
            {"id": execution_id}
        )).scalar()

        db_artifacts = (await conn.execute(
            text("SELECT id, task_key, name, checksum_sha256, artifact_type FROM artifacts WHERE workflow_execution_id = :id"),
            {"id": execution_id}
        )).fetchall()
    await engine.dispose()

    # 9. Structured Evidence Report
    evidence = {
        "workflow_id": workflow_id,
        "workflow_name": wf_name,
        "execution_id": execution_id,
        "execution_status": db_exec[2] if db_exec else None,
        "started_at": str(db_exec[3]) if db_exec and db_exec[3] else None,
        "completed_at": str(db_exec[4]) if db_exec and db_exec[4] else None,
        "error_summary": db_exec[5] if db_exec else None,
        "tasks": [
            {
                "task_id": t[0],
                "task_key": t[1],
                "agent_id": t[2],
                "status": t[3],
                "attempt_count": t[4],
                "revision_count": t[5],
                "execution_duration_ms": t[6],
            }
            for t in db_tasks
        ],
        "events_count_in_db": db_events_count,
        "artifacts_in_db": [
            {
                "artifact_id": a[0],
                "task_key": a[1],
                "name": a[2],
                "checksum_sha256": a[3],
                "type": a[4],
            }
            for a in db_artifacts
        ],
        "frontend_http_status": fe_resp.status_code,
    }

    print("\n================ LIVE E2E EVIDENCE OBJECT ================")
    print(json.dumps(evidence, indent=2))
    print("==========================================================\n")

if __name__ == "__main__":
    asyncio.run(main())
