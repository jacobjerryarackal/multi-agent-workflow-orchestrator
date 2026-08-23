# Bounded Implementation Roadmap: Multi-Agent Workflow Orchestrator

**Document:** Phased Engineering Plan & Milestone Verification Protocol  
**Target Timeline:** 5 Focused Development Days  
**Status:** Approved Roadmap (Day 0)  

---

## Roadmap Overview

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   5-DAY IMPLEMENTATION PHASES                                    │
├───────────────┬─────────────────────────────────────────────────┬────────────────────────────────┤
│ DAY           │ MORNING PHASE                                   │ AFTERNOON PHASE                │
├───────────────┼─────────────────────────────────────────────────┼────────────────────────────────┤
│ **Day 0**     │ Phase 0: System Architecture & Design (DONE)    │ Phase 0: Reference Synthesis   │
│ **Day 1**     │ Phase 1: Domain Contracts & Pydantic Specs      │ Phase 2: State Machine & DB    │
│ **Day 2**     │ Phase 3: Agent Registry & Built-in Agents       │ Phase 4: DAG Resolver & Sched. │
│ **Day 3**     │ Phase 5: Async Execution Engine & Dispatcher    │ Phase 6: Failure & Recovery    │
│ **Day 4**     │ Phase 7: FastAPI Endpoints & Event Stream       │ Phase 8: Quality & Context Adp │
│ **Day 5**     │ Phase 9: Next.js Control Plane (Anti-Slop UI)   │ Phase 10: E2E QA & Deployment  │
└───────────────┴─────────────────────────────────────────────────┴────────────────────────────────┘
```

---

## Detailed Phase Breakdown

### Phase 0: Architecture, System Design & Reference Synthesis (Day 0)
* **Objective**: Complete architectural blueprint, failure matrix, contracts, and ADRs.
* **Deliverables**: `docs/reference-analysis.md`, `docs/architecture/*.md`, `docs/contracts/*.md`, `docs/failure-modes/*.md`, `docs/security/threat-model.md`, `docs/testing/testing-strategy.md`, `docs/adr/*.md`.
* **Acceptance Criteria**: All 22 failure modes mapped to tests; all contracts defined with typed Pydantic models; zero implementation code written before review.

---

### Phase 1: Domain Contracts & Pydantic Models (Day 1 Morning)
* **Objective**: Implement immutable core domain models, typed schemas, and result containers.
* **Target Files**:
  - `backend/app/domain/models/workflow.py`
  - `backend/app/domain/models/execution.py`
  - `backend/app/domain/models/agent.py`
  - `backend/app/domain/models/event.py`
  - `backend/app/domain/models/artifact.py`
  - `backend/app/domain/models/failure.py`
  - `backend/app/domain/interfaces/*.py`
* **Tests**: `tests/unit/test_contracts.py` (Pydantic validation, serialization, JSON schema exports).
* **Acceptance Criteria**: 100% test pass rate on model parsing and schema validation; exportable JSON schemas for frontend type generation.
* **Failure Modes Covered**: Malformed Model Output, Schema Validation Failure.

---

### Phase 2: Workflow State Machine & Persistence Schema (Day 1 Afternoon)
* **Objective**: Implement the closed-loop state machine and PostgreSQL SQLAlchemy ORM models with Alembic migrations.
* **Target Files**:
  - `backend/app/orchestration/state_machine.py`
  - `backend/app/persistence/models.py`
  - `backend/app/persistence/database.py`
  - `backend/app/persistence/repositories/*.py`
  - `backend/alembic/*`
* **Tests**: `tests/unit/test_state_machine.py`, `tests/integration/test_persistence.py`.
* **Acceptance Criteria**: State machine enforces all valid/invalid transitions; database migrations run cleanly on PostgreSQL.
* **Failure Modes Covered**: Inconsistent State Transition, Duplicate Execution Request, Concurrent State Update Conflict.

---

### Phase 3: Agent Registry & Built-in Specialized Agents (Day 2 Morning)
* **Objective**: Build the central Agent Registry and initial 5 specialized agents (`Planner`, `Researcher`, `Analyst`, `Reviewer`, `Synthesizer`).
* **Target Files**:
  - `backend/app/agents/base.py`
  - `backend/app/agents/registry.py`
  - `backend/app/agents/builtins/planner.py`
  - `backend/app/agents/builtins/researcher.py`
  - `backend/app/agents/builtins/analyst.py`
  - `backend/app/agents/builtins/reviewer.py`
  - `backend/app/agents/builtins/synthesizer.py`
  - `backend/app/providers/gemini.py`
* **Tests**: `tests/unit/test_agent_registry.py`, `tests/unit/test_agent_runners.py` (using `MockModelProvider`).
* **Acceptance Criteria**: Agents execute deterministically against mock provider; registry validates input/output schemas.
* **Failure Modes Covered**: Agent Missing in Registry, Malformed Model Output.

---

### Phase 4: DAG Dependency Resolver & Topological Scheduler (Day 2 Afternoon)
* **Objective**: Implement Kahn's algorithm for DAG cycle detection, in-degree dependency tracking, and parallel task scheduling.
* **Target Files**:
  - `backend/app/orchestration/dependency_resolver.py`
  - `backend/app/orchestration/scheduler.py`
* **Tests**: `tests/unit/test_dag.py`, `tests/unit/test_scheduler.py`.
* **Acceptance Criteria**: Correctly orders serial, fan-out, fan-in topologies; raises `CyclicDependencyError` on circular graphs.
* **Failure Modes Covered**: Circular DAG Dependency, Invalid Workflow Definition, Dependency Failure.

---

### Phase 5: Async Execution Engine & Dispatcher (Day 3 Morning)
* **Objective**: Implement the master workflow execution loop, concurrency semaphore, artifact passing, and event publishing.
* **Target Files**:
  - `backend/app/orchestration/engine.py`
  - `backend/app/orchestration/approval_manager.py`
  - `backend/app/telemetry/event_bus.py`
* **Tests**: `tests/integration/test_engine.py`.
* **Acceptance Criteria**: Successfully executes full 5-agent DAG workflow from start to finish with artifact passing.
* **Failure Modes Covered**: Task Wall-Clock Timeout, Workflow Global Timeout, Human Approval Gate Timeout.

---

### Phase 6: Failure Classifier, Circuit Breaker & Recovery (Day 3 Afternoon)
* **Objective**: Implement the failure classification engine, Jittered Exponential Backoff, Rolling Circuit Breaker, and reflection retry loop.
* **Target Files**:
  - `backend/app/failures/classifier.py`
  - `backend/app/failures/policies.py`
  - `backend/app/failures/circuit_breaker.py`
  - `backend/app/failures/recovery.py`
* **Tests**: `tests/unit/test_failures.py`, `tests/unit/test_circuit_breaker.py`, `tests/unit/test_recovery.py`.
* **Acceptance Criteria**: Transient errors retry with backoff; sustained 5xx trips circuit breaker; retry exhaustion triggers escalation.
* **Failure Modes Covered**: Provider Timeout, Rate Limit (429), Provider 503 Outage, Retry Exhaustion, Evaluator Quality Rejection.

---

### Phase 7: REST API & Server-Sent Events (FastAPI) (Day 4 Morning)
* **Objective**: Implement FastAPI endpoints for workflow CRUD, execution triggering, step inspection, approval submission, and SSE stream.
* **Target Files**:
  - `backend/app/api/v1/*.py`
  - `backend/app/main.py`
* **Tests**: `tests/integration/test_api.py`.
* **Acceptance Criteria**: Complete OpenAPI 3.1 schema; `/health` and `/ready` endpoints; real-time event streaming via SSE.
* **Failure Modes Covered**: Duplicate Idempotency Key, Unauthorized Workflow Execution.

---

### Phase 8: Quality Evaluation & Context Provider Adapters (Day 4 Afternoon)
* **Objective**: Implement clean adapter interfaces for quality evaluation gates (EvalForge ready) and context injection (MemoryOps ready).
* **Target Files**:
  - `backend/app/providers/eval_adapter.py`
  - `backend/app/providers/context_adapter.py`
* **Tests**: `tests/unit/test_evaluation_adapter.py`, `tests/unit/test_context_adapter.py`.
* **Acceptance Criteria**: Evaluator evaluates output against criteria; rejected outputs trigger self-correction retry or human gate.
* **Failure Modes Covered**: Evaluator Quality Rejection, Context Overflow.

---

### Phase 9: Next.js Engineering Control Plane (Day 5 Morning)
* **Objective**: Build the Next.js + TypeScript dashboard with reusable components, DAG visualization, execution timeline, and approval modals.
* **Design Rule**: NO AI-SLOP. High-density, technical, restrained, accessible.
* **Target Structure**:
  - `frontend/src/app/` (thin page compositions)
  - `frontend/src/components/ui/` (reusable buttons, badges, tables, modals)
  - `frontend/src/features/workflow-graph/` (interactive DAG visualizer)
  - `frontend/src/features/execution-timeline/` (latency waterfall & event log)
  - `frontend/src/features/failure-inspector/` (retry history & error diffs)
  - `frontend/src/features/approval-gate/` (decision review modal)
* **Tests**: Component unit tests and render tests.
* **Acceptance Criteria**: Zero inline business logic in `page.tsx`; live updates via SSE; clear visual distinction between task states.

---

### Phase 10: Production Hardening, Verification & Deployment (Day 5 Afternoon)
* **Objective**: End-to-end integration verification, security audit, Docker containerization, and deployment setup (Render + Vercel + PostgreSQL).
* **Target Files**: `Dockerfile`, `docker-compose.yml`, `render.yaml`, `README.md`.
* **Tests**: Full end-to-end smoke test suite executing complex DAG workflows with simulated failures and recoveries.
* **Acceptance Criteria**: 100% test suite pass rate; zero secrets in frontend; automated deployment configuration verified.
