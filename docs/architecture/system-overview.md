# System Overview: Multi-Agent Workflow Orchestrator

**Project:** Multi-Agent Workflow Orchestration Engine  
**Document:** System Overview & Architectural Strategy  
**Status:** Approved Architecture (Day 0)  

---

## 1. System Mission & Scope

The **Multi-Agent Workflow Orchestrator** is a production-grade, domain-agnostic orchestration platform designed to coordinate heterogeneous, specialized AI agents and deterministic tasks across complex Directed Acyclic Graph (DAG) topologies.

Rather than relying on unconstrained conversational chaining or unpredictable multi-agent debates, the engine treats agent coordination as a **deterministic, stateful workflow execution problem**.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    ORCHESTRATOR CONTROL PLANE                                    │
│                                                                                                  │
│  ┌───────────────────────┐   ┌───────────────────────┐   ┌────────────────────────────────────┐  │
│  │   Workflow Schema     │   │     Agent Registry    │   │         Scheduler & Engine         │  │
│  │  (DAG, Tasks, I/O)    │──▶│  (Capabilities, Caps) │──▶│  (State Machine, Queue, Workers)   │  │
│  └───────────────────────┘   └───────────────────────┘   └─────────────────┬──────────────────┘  │
│                                                                            │                     │
│                                       ┌────────────────────────────────────┴──────────────────┐  │
│                                       ▼                                                       │  │
│                   ┌───────────────────────────────────────┐                                   │  │
│                   │          Task Execution Loop          │                                   │  │
│                   │  ┌─────────────────────────────────┐  │                                   │  │
│                   │  │ 1. Dependency Resolution        │  │                                   │  │
│                   │  │ 2. Context Injection            │  │                                   │  │
│                   │  │ 3. Agent Execution (Gemini)     │  │                                   │  │
│                   │  │ 4. Output Contract Validation   │  │                                   │  │
│                   │  │ 5. Quality Evaluation Gate      │  │                                   │  │
│                   │  │ 6. Artifact & State Persistence │  │                                   │  │
│                   │  └─────────────────────────────────┘  │                                   │  │
│                   └───────────────────┬───────────────────┘                                   │  │
│                                       │                                                       │  │
│                                       ▼ (on error or quality rejection)                       │  │
│                   ┌───────────────────────────────────────┐                                   │  │
│                   │      Failure & Recovery Engine        │                                   │  │
│                   │  • Classification  • Backoff Retry    │                                   │  │
│                   │  • Circuit Breaker • Human Escalation │                                   │  │
│                   └───────────────────────────────────────┘                                   │  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Architectural Pillars

### A. Directed Acyclic Graph (DAG) & Dependency-Aware Scheduling
* Workflows are defined as directed graphs of tasks with explicit dependencies (`depends_on`).
* Supports serial chains, fan-out parallel branches, fan-in aggregations, and conditional branching.
* Invariant: Cycle detection is enforced at workflow registration time via topological sorting (Kahn's algorithm).

### B. Strongly Typed Agent Contracts
* Agents implement a strict `BaseAgent` specification with typed input (`input_schema`) and output (`output_schema`) contracts using Pydantic.
* Every agent run produces an immutable `AgentResult` containing status, structured output, generated artifacts, latency metrics, and token usage.

### C. Explicit Closed-Loop State Machine
* All tasks and workflow runs transition through deterministic states (`PENDING` -> `RUNNING` -> `COMPLETED` / `FAILED` / `WAITING_APPROVAL` / `ESCALATED` / `CANCELLED`).
* Every state transition emits an immutable `WorkflowEvent` persisted to PostgreSQL.

### D. Multi-Tier Failure Classification & Recovery
* Failures are classified into 8 canonical categories (e.g., `TRANSIENT_PROVIDER_ERROR`, `SCHEMA_VALIDATION_ERROR`, `TIMEOUT_ERROR`, `EVALUATOR_REJECTION`, `DEADLOCK_DETECTED`).
* Automated recovery policies dictate exponential backoff, circuit breaking, fallback agent routing, or escalation to human review.

### E. Pluggable Ecosystem Interfaces
* Clean adapter interfaces for external portfolio systems:
  - `ContextProvider`: Ingests context (compatible with MemoryOps AI).
  - `EvaluationProvider`: Scores quality gates (compatible with EvalForge).
  - `ExecutionProvider`: Sandboxed agent harnesses (compatible with Symphony).
  - `ModelProvider`: LLM gateway (starting with Google Gemini Flash / Pro).

---

## 3. High-Density Observability & Control Plane

The frontend control plane (Next.js + Tailwind + TypeScript) is designed for serious systems engineering:
* **Interactive DAG Graph**: Visualizing task node statuses, execution paths, and real-time dependency resolution.
* **Execution Timeline & Waterfall**: Millisecond-level latency tracking across parallel and sequential branches.
* **Failure & State Inspector**: Complete visibility into prompt/output payloads, schema validation errors, retry history, and human approval gates.
* **Zero AI-Slop Design**: No gratuitous animations, no purple marketing gradients, no fake metrics.
