# Low-Level Design (LLD): Multi-Agent Workflow Orchestrator

**Document:** Low-Level Architectural Design & Specifications  
**Status:** Approved Architecture (Day 0)  

---

## 1. Backend Codebase Directory Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── router.py               # Main v1 API router aggregation
│   │   │   ├── workflows.py            # Workflow CRUD & execution trigger
│   │   │   ├── executions.py           # Execution status, step inspection, retry/cancel
│   │   │   ├── agents.py               # Agent registry inspection & metadata
│   │   │   ├── approvals.py            # Human approval decision submission
│   │   │   ├── artifacts.py            # Artifact retrieval & download
│   │   │   └── health.py               # /health and /ready endpoints
│   │   ├── dependencies.py             # FastAPI dependency injections (DB session, auth)
│   │   └── middleware.py               # Request tracing, CORS, error handling
│   │
│   ├── domain/
│   │   ├── models/                     # Core Domain Entities (dataclasses / Pydantic)
│   │   │   ├── workflow.py             # Workflow, WorkflowSpec, TaskSpec
│   │   │   ├── execution.py            # WorkflowExecution, TaskExecution
│   │   │   ├── agent.py                # AgentDefinition, AgentCapability, AgentResult
│   │   │   ├── event.py                # WorkflowEvent, EventType
│   │   │   ├── artifact.py             # Artifact, ArtifactType
│   │   │   └── failure.py              # FailureCategory, FailureRecord, RecoveryAction
│   │   └── interfaces/                 # Pure Abstract Protocols / ABCs
│   │       ├── agent.py                # BaseAgent protocol
│   │       ├── repository.py           # Persistence repository interfaces
│   │       ├── model_provider.py       # LLM provider interface
│   │       ├── context_provider.py     # Context retrieval interface
│   │       └── evaluation_provider.py  # Quality gate evaluation interface
│   │
│   ├── orchestration/
│   │   ├── engine.py                   # Master Orchestrator Engine loop
│   │   ├── scheduler.py                # DAG Scheduler & async Task Dispatcher
│   │   ├── dependency_resolver.py      # Kahn's topological sort & in-degree tracker
│   │   ├── state_machine.py            # Task & Execution state transition validator
│   │   └── approval_manager.py         # Human-in-the-loop approval gate coordinator
│   │
│   ├── agents/
│   │   ├── registry.py                 # Central Agent Registry singleton
│   │   ├── base.py                     # BaseAgent abstract implementation
│   │   └── builtins/                   # Core specialized agents
│   │       ├── planner.py              # Workflow decomposition & planning agent
│   │       ├── researcher.py           # Structured investigation agent
│   │       ├── analyst.py              # Data analysis & reasoning agent
│   │       ├── reviewer.py             # Critique & validation agent
│   │       └── synthesizer.py          # Final output aggregation agent
│   │
│   ├── failures/
│   │   ├── classifier.py               # Rule-based and semantic Failure Classifier
│   │   ├── policies.py                 # Exponential backoff, jitter, retry limits
│   │   ├── circuit_breaker.py          # Rolling failure circuit breaker
│   │   └── recovery.py                 # Recovery strategy execution (Retry, Fallback, Escalate)
│   │
│   ├── providers/
│   │   ├── gemini.py                   # Google Gemini API Provider (Flash / Pro)
│   │   ├── context_adapter.py          # Transient context + MemoryOps stub adapter
│   │   ├── eval_adapter.py             # Builtin rule evaluator + EvalForge stub adapter
│   │   └── runtime_adapter.py          # In-process runtime + Symphony stub adapter
│   │
│   ├── persistence/
│   │   ├── database.py                 # SQLAlchemy async engine & sessionmaker
│   │   ├── models.py                   # SQLAlchemy ORM table mappings
│   │   └── repositories/               # Concrete repository implementations
│   │       ├── workflow_repo.py
│   │       ├── execution_repo.py
│   │       ├── event_repo.py
│   │       └── artifact_repo.py
│   │
│   ├── telemetry/
│   │   ├── event_bus.py                # In-memory async event publisher + DB sink
│   │   ├── logger.py                   # Structured JSON logger (structlog / loguru)
│   │   └── metrics.py                  # Task duration, token counter, failure rate
│   │
│   └── core/
│       ├── config.py                   # Pydantic BaseSettings (env vars)
│       └── exceptions.py               # Custom domain exceptions
│
├── alembic/                            # Database migrations
│   ├── versions/
│   └── env.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

---

## 2. PostgreSQL Relational Schema & ORM Mapping

```
┌───────────────────────────┐         1:N         ┌───────────────────────────┐
│         workflows         │────────────────────▶│       workflow_tasks      │
│ ───────────────────────── │                     │ ───────────────────────── │
│ id (UUID, PK)             │                     │ id (UUID, PK)             │
│ name (VARCHAR)            │                     │ workflow_id (UUID, FK)    │
│ version (INT)             │                     │ task_key (VARCHAR)        │
│ description (TEXT)        │                     │ agent_id (VARCHAR)        │
│ input_schema (JSONB)      │                     │ depends_on (JSONB/Array)  │
│ output_schema (JSONB)     │                     │ timeout_seconds (INT)     │
│ config (JSONB)            │                     │ retry_policy (JSONB)      │
│ created_at (TIMESTAMPTZ)  │                     │ approval_required (BOOL)  │
└─────────────┬─────────────┘                     └─────────────┬─────────────┘
              │                                                 │
              │ 1:N                                             │ 1:N
              ▼                                                 ▼
┌───────────────────────────┐         1:N         ┌───────────────────────────┐
│    workflow_executions    │────────────────────▶│      task_executions      │
│ ───────────────────────── │                     │ ───────────────────────── │
│ id (UUID, PK)             │                     │ id (UUID, PK)             │
│ workflow_id (UUID, FK)    │                     │ workflow_execution_id(FK) │
│ status (VARCHAR)          │                     │ task_key (VARCHAR)        │
│ trigger_type (VARCHAR)    │                     │ status (VARCHAR)          │
│ initial_inputs (JSONB)    │                     │ attempt_count (INT)       │
│ final_outputs (JSONB)     │                     │ input_data (JSONB)        │
│ error_summary (TEXT)      │                     │ output_data (JSONB)       │
│ started_at (TIMESTAMPTZ)  │                     │ error_details (JSONB)     │
│ completed_at (TIMESTAMPTZ)│                     │ started_at (TIMESTAMPTZ)  │
│ execution_duration_ms(INT)│                     │ completed_at(TIMESTAMPTZ) │
└─────────────┬─────────────┘                     └─────────────┬─────────────┘
              │                                                 │
              │ 1:N                                             │ 1:N
              ▼                                                 ▼
┌───────────────────────────┐                     ┌───────────────────────────┐
│      workflow_events      │                     │         artifacts         │
│ ───────────────────────── │                     │ ───────────────────────── │
│ id (UUID, PK)             │                     │ id (UUID, PK)             │
│ workflow_execution_id(FK) │                     │ workflow_execution_id(FK) │
│ task_execution_id (FK,opt)│                     │ task_key (VARCHAR)        │
│ event_type (VARCHAR)      │                     │ name (VARCHAR)            │
│ payload (JSONB)           │                     │ artifact_type (VARCHAR)   │
│ created_at (TIMESTAMPTZ)  │                     │ uri_or_content (TEXT/JSON)│
└───────────────────────────┘                     │ checksum_sha256 (VARCHAR) │
                                                  │ created_at (TIMESTAMPTZ)  │
                                                  └───────────────────────────┘
```

---

## 3. Core Interface Definitions (Python Protocols)

### 3.1 BaseAgent Protocol
```python
from typing import Any, Dict, Protocol
from pydantic import BaseModel

class AgentContext(BaseModel):
    workflow_execution_id: str
    task_key: str
    attempt: int
    inputs: Dict[str, Any]
    upstream_artifacts: Dict[str, Any]
    metadata: Dict[str, Any] = {}

class AgentResult(BaseModel):
    success: bool
    data: Dict[str, Any]
    artifacts: list[Dict[str, Any]] = []
    error_message: str | None = None
    execution_duration_ms: int
    token_usage: Dict[str, int] = {}
    metadata: Dict[str, Any] = {}

class BaseAgent(Protocol):
    agent_id: str
    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]

    async def execute(self, context: AgentContext) -> AgentResult:
        ...
```

### 3.2 ModelProvider Protocol
```python
class ModelProvider(Protocol):
    async def generate_structured(
        self,
        prompt: str,
        system_instruction: str,
        response_schema: type[BaseModel],
        temperature: float = 0.2,
        timeout_seconds: float = 30.0,
    ) -> tuple[BaseModel, Dict[str, int]]:
        ...
```

### 3.3 EvaluationProvider Protocol
```python
from enum import Enum

class EvaluationVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    RETRY = "RETRY"
    ESCALATE = "ESCALATE"

class EvaluationResult(BaseModel):
    verdict: EvaluationVerdict
    score: float  # 0.0 to 1.0
    rationale: str
    feedback: str | None = None

class EvaluationProvider(Protocol):
    async def evaluate_task_output(
        self,
        task_key: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        criteria: Dict[str, Any],
    ) -> EvaluationResult:
        ...
```

---

## 4. Execution Concurrency and Transaction Locking

1. **Asyncio Concurrency**: The Scheduler dispatches independent ready tasks concurrently via `asyncio.gather` or bounded task pools using `asyncio.Semaphore(max_parallel_tasks)`.
2. **Optimistic Concurrency & DB Locking**:
   - State updates on `task_executions` and `workflow_executions` use atomic transactions with explicit status checks.
   - For state transitions (e.g. approving a task or claiming ready tasks), queries use `SELECT ... FOR UPDATE` where necessary to prevent race conditions during concurrent worker polling.
3. **Idempotency Key**: Execution requests can supply an `idempotency_key` (UUID/Hash) stored with `workflow_executions` to prevent duplicate triggering from retried network requests.
