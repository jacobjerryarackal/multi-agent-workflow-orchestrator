# High-Level Design (HLD): Multi-Agent Workflow Orchestrator

**Document:** High-Level Architectural Design  
**Status:** Approved Architecture (Day 0)  

---

## 1. Modular Monolith Architecture

The system is architected as a clean, layered Modular Monolith. This avoids premature microservices distributed complexity while maintaining strict domain encapsulation.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                PRESENTATION / API LAYER                                │
│   FastAPI Endpoints  •  OpenAPI 3.1  •  WebSocket / SSE Event Stream  •  CORS & Auth   │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
┌──────────────────────────────────────────▼─────────────────────────────────────────────┐
│                              ORCHESTRATION ENGINE LAYER                                │
│  ┌─────────────────────────┐  ┌──────────────────────────┐  ┌───────────────────────┐  │
│  │   Workflow Service      │  │  DAG Dependency Engine   │  │   Scheduler & Queue   │  │
│  │   • Definition Parse    │  │  • Topological Sort      │  │   • Task Dispatcher   │  │
│  │   • Invariant Check     │  │  • Cycle Detection       │  │   • Parallel Bounds   │  │
│  └─────────────────────────┘  └──────────────────────────┘  └───────────────────────┘  │
│  ┌─────────────────────────┐  ┌──────────────────────────┐  ┌───────────────────────┐  │
│  │    State Machine        │  │  Failure & Recovery Mgr  │  │ Human Approval Gate   │  │
│  │  • Task State Engine    │  │  • Classifier Engine     │  │  • Resume / Reject    │  │
│  │  • Event Publisher      │  │  • Retry / Backoff       │  │  • Timeout Guard      │  │
│  └─────────────────────────┘  └──────────────────────────┘  └───────────────────────┘  │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
┌──────────────────────────────────────────▼─────────────────────────────────────────────┐
│                                AGENT & RUNTIME LAYER                                   │
│  ┌─────────────────────────┐  ┌──────────────────────────┐  ┌───────────────────────┐  │
│  │     Agent Registry      │  │    BaseAgent Runner      │  │   Artifact Manager    │  │
│  │  • Schema Reflection    │  │  • Input/Output Contract │  │   • Scoped Artifacts  │  │
│  │  • Capabilities Spec   │  │  • Token Budget Limits   │  │   • Checkpointing     │  │
│  └─────────────────────────┘  └──────────────────────────┘  └───────────────────────┘  │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
┌──────────────────────────────────────────▼─────────────────────────────────────────────┐
│                            EXTERNAL ADAPTERS & PROVIDERS                               │
│  ┌───────────────────┐  ┌───────────────────┐  ┌─────────────────┐  ┌───────────────┐  │
│  │   ModelProvider   │  │ ContextProvider   │  │ EvaluationProv. │  │ ExecutionProv │  │
│  │   (Gemini API)    │  │ (MemoryOps Adpt)  │  │ (EvalForge Adp) │  │ (Symphony Ad) │  │
│  └───────────────────┘  └───────────────────┘  └─────────────────┘  └───────────────┘  │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
┌──────────────────────────────────────────▼─────────────────────────────────────────────┐
│                               PERSISTENCE & STORAGE LAYER                              │
│   PostgreSQL (Workflows, Tasks, Events, Runs, Artifacts, Approvals, Retry Audits)       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Subsystems and Responsibilities

### 2.1 Workflow Subsystem (`app/orchestration/workflow/`)
* **Workflow Definition**: Ingests JSON/YAML workflow schemas defining tasks, DAG dependencies, timeout bounds, and configuration.
* **Workflow Validator**: Validates that all referenced agents exist in the registry, input/output contracts align across edges, and the graph contains zero cycles.

### 2.2 Scheduler & Dependency Resolver (`app/orchestration/scheduler/`)
* **DAG Resolver**: Uses topological sorting and in-degree tracking to identify ready-to-run tasks whose dependencies have succeeded.
* **Concurrent Dispatcher**: Executes ready tasks concurrently up to a configurable `max_parallel_tasks` limit using `asyncio` task pools.

### 2.3 State Machine Subsystem (`app/orchestration/state/`)
* **Execution State Engine**: Enforces strict task status transitions (`PENDING` -> `BLOCKED` -> `READY` -> `RUNNING` -> `COMPLETED` / `FAILED` / `WAITING_APPROVAL` / `ESCALATED` / `CANCELLED` / `TIMED_OUT`).
* **State Store**: Persists all intermediate states and context variables in PostgreSQL.

### 2.4 Agent Subsystem (`app/agents/`)
* **Agent Registry**: Central directory of available agents with their capabilities, metadata, version, and Pydantic schemas.
* **Agent Executor**: Invokes agent execution logic within strict timeout and token budget constraints.

### 2.5 Failure & Recovery Subsystem (`app/failures/`)
* **Failure Classifier**: Inspects exceptions, API response codes, validation errors, and evaluator rejects to categorize failures.
* **Recovery Policy Engine**: Computes backoff intervals, increments retry counts, checks circuit breaker thresholds, triggers fallback agents, or routes to human approval.

### 2.6 Artifact Subsystem (`app/artifacts/`)
* **Artifact Store**: Manages structured outputs, files, documents, and intermediate representations produced by tasks and shared downstream.
* **Contract Validation**: Validates artifact schemas between producer and consumer tasks.

### 2.7 Observability & Telemetry Subsystem (`app/telemetry/`)
* **Event Stream Engine**: Emits timestamped, typed events for every lifecycle phase.
* **Audit Trail**: Provides reproducible execution history for compliance and debugging.
