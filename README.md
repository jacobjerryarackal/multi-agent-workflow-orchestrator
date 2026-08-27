# Multi-Agent Workflow Orchestrator

[![Status: Architecture Approved](https://img.shields.io/badge/status-Architecture%20Approved%20(Day%200)-blue.svg)]()
[![Architecture: Modular Monolith DAG](https://img.shields.io/badge/architecture-Modular%20Monolith%20DAG-brightgreen.svg)]()
[![Backend: FastAPI + Python](https://img.shields.io/badge/backend-FastAPI%20%7C%20Python%203.11%2B-blue.svg)]()
[![Database: PostgreSQL](https://img.shields.io/badge/database-PostgreSQL%20ACID%20%2B%20JSONB-navy.svg)]()
[![Frontend: Next.js + TS](https://img.shields.io/badge/frontend-Next.js%2014%20%7C%20TypeScript-black.svg)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)]()

> A production-oriented, model-agnostic Multi-Agent Workflow Orchestration Engine designed to coordinate heterogeneous specialized agents across complex Directed Acyclic Graph (DAG) topologies with deterministic state machines, failure recovery, artifact passing, and human-in-the-loop approval gates.

---

## 1. Portfolio Context: The Fourth Pillar

The developer's portfolio consists of four specialized, complementary pillars:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               DEVELOPER PORTFOLIO MATRIX                               │
├──────────────────────────┬─────────────────────────────────────┬───────────────────────┤
│ Pillar                   │ System Focus                        │ Repository            │
├──────────────────────────┼─────────────────────────────────────┼───────────────────────┤
│ **1. Agent Runtime**     │ Code Sandboxes & Tool Execution     │ Symphony / Harness    │
│ **2. Governed Memory**   │ Long-Term Memory & Hybrid Retrieval │ MemoryOps AI          │
│ **3. Agent Evaluation**  │ Evals, Golden Datasets & LLM Judges │ EvalForge             │
│ **4. Orchestration**     │ Multi-Agent DAGs & State Machine    │ **This Project**      │
└──────────────────────────┴─────────────────────────────────────┴───────────────────────┘
```

---

## 2. Core Capabilities

* **Deterministic DAG Scheduler**: Topological sort (Kahn's algorithm) with strict cycle detection, parallel branch dispatching, and serial fan-in aggregation.
* **Strongly-Typed Agent Contracts**: Pydantic input/output schemas with runtime validation and self-correction reflection prompts.
* **Closed-Loop State Machine**: Deterministic state transitions (`PENDING`, `BLOCKED`, `READY`, `RUNNING`, `COMPLETED`, `FAILED`, `WAITING_APPROVAL`, `ESCALATED`, `TIMED_OUT`, `CANCELLED`).
* **Multi-Tier Failure Recovery**: 8 failure classifications, full jitter exponential backoff, rolling circuit breakers, and human escalation gates.
* **Event Sourcing & Auditability**: Every state change emits an immutable `WorkflowEvent` persisted to PostgreSQL and streamed via SSE.
* **Anti-AI-Slop Control Plane**: High-density, technical Next.js dashboard providing topological graph inspection, latency waterfalls, and failure diagnostics without visual gimmicks.

---

## 3. Architectural Documentation

All architectural specifications, formal contracts, and failure-mode taxonomies are fully documented in the `docs/` repository:

| Document | Purpose |
| :--- | :--- |
| **[Reference Synthesis](docs/reference-analysis.md)** | Deep comparative analysis of 7 engineering references and portfolio lessons. |
| **[System Overview](docs/architecture/system-overview.md)** | High-level system mission, core pillars, and architectural boundaries. |
| **[High-Level Design (HLD)](docs/architecture/high-level-design.md)** | Layered modular monolith topology and subsystem responsibilities. |
| **[Low-Level Design (LLD)](docs/architecture/low-level-design.md)** | Codebase directory structure, PostgreSQL relational schema, and Python protocols. |
| **[State Machine Spec](docs/architecture/workflow-state-machine.md)** | Formal task and workflow state transition tables, guards, and invariants. |
| **[Execution Model](docs/architecture/execution-model.md)** | DAG resolution algorithms, async dispatching, artifact flows, and Genesis bounds. |
| **[Agent Contract](docs/contracts/agent-contract.md)** | BaseAgent interface, AgentResult model, and built-in agent specifications. |
| **[Workflow Contract](docs/contracts/workflow-contract.md)** | WorkflowSpec, TaskSpec, JSON schema definitions, and canonical DAG examples. |
| **[Event Contract](docs/contracts/event-contract.md)** | Event schema, SSE streaming format, and real-time telemetry model. |
| **[Failure Matrix](docs/failure-modes/failure-matrix.md)** | Complete 22-scenario failure taxonomy, classifications, and mitigation table. |
| **[Recovery Strategies](docs/failure-modes/recovery-strategies.md)** | Full jitter backoff, circuit breaking, reflection prompts, and HITL gates. |
| **[Threat Model](docs/security/threat-model.md)** | STRIDE security analysis, trust boundaries, and zero-secret frontend policies. |
| **[Testing Strategy](docs/testing/testing-strategy.md)** | Testing pyramid, failure-to-test mapping matrix, and mock provider specs. |
| **[Implementation Roadmap](docs/implementation-plan.md)** | Bounded 5-day phased implementation plan with explicit acceptance criteria. |
| **[ADRs (Decisions)](docs/adr/)** | Architectural Decision Records (ADR 001 through ADR 004). |
| **[Deployment Architecture](docs/deployment/architecture.md)** | Cloud topology (Next.js/Vercel + FastAPI/Render + PostgreSQL). |
| **[Environment Variables](docs/deployment/environment.md)** | Comprehensive environment variables and secret boundaries guide. |
| **[Render Guide](docs/deployment/render.md)** | Backend containerization and managed PostgreSQL deployment. |
| **[Vercel Guide](docs/deployment/vercel.md)** | Frontend deployment and serverless API rewrite proxy setup. |
| **[Database Migrations](docs/deployment/migrations.md)** | Alembic migration lifecycle, safety rules, and pre-deploy hooks. |
| **[Operations & Telemetry](docs/deployment/operations.md)** | Monitoring, health checks, and Prometheus metrics guide. |
| **[Troubleshooting](docs/deployment/troubleshooting.md)** | Common production failure scenarios and resolutions. |
| **[Backup & Recovery](docs/deployment/backup_restore.md)** | Disaster recovery runbook for PostgreSQL. |

---

## 4. Initial 5 Built-in Specialized Agents

1. **`planner_agent`**: Decomposes user goals into structured sub-tasks, dependency requirements, and risk factors.
2. **`researcher_agent`**: Conducts structured investigation across parallel thematic domains.
3. **`analyst_agent`**: Performs qualitative reasoning, tradeoff analysis, and quantitative comparisons.
4. **`reviewer_agent`**: Audits findings against quality standards and flags contradictions or factual gaps.
5. **`synthesizer_agent`**: Integrates all upstream findings into a cohesive, high-impact final deliverable.

---

## 5. Technology Stack

* **Backend**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy (Async), Alembic, `asyncpg`.
* **Database**: PostgreSQL (ACID relational tables + JSONB state/artifacts).
* **Model Provider**: Google Gemini API (`gemini-2.5-flash` / `gemini-2.5-pro`).
* **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, Lucide Icons.
* **Testing**: Pytest, Pytest-Asyncio, HTTPX.
* **Deployment Targets**: Render (Backend Web Service), Vercel (Frontend Control Plane), Managed PostgreSQL.

---

## 6. Quick Start & Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- PostgreSQL 16 instance running locally

### Backend Setup
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env and supply your GEMINI_API_KEY and DATABASE_URL

# 3. Apply database migrations
alembic -c backend/alembic.ini upgrade head

# 4. Run backend server
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000 in your browser
```

### Verification & Smoke Testing
```bash
# Run backend test suite
pytest tests -v

# Run smoke test against running backend
python scripts/deploy_smoke_test.py --url http://127.0.0.1:8000
```