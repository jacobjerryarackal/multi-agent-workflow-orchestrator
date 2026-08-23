# ADR-001: Orchestration Model Selection (Modular Monolith DAG Engine)

**Status:** Accepted  
**Date:** 2026-08-23  

---

## Context

We need an orchestration engine to coordinate heterogeneous AI agents across serial, parallel, and conditional execution paths. We considered three potential architectural approaches:
1. **Unconstrained Conversational / Multi-Agent Debate (GroupChat)**: Agents send messages back and forth in an open chat room.
2. **Microservices Choreography**: Every agent is an independent HTTP service communicating via distributed event brokers (Kafka/RabbitMQ).
3. **Modular Monolith DAG Orchestration Engine**: A centralized, asynchronous Directed Acyclic Graph (DAG) state machine executing typed agent functions in-process with persistent state in PostgreSQL.

---

## Decision

We chose **Option 3: Modular Monolith DAG Orchestration Engine**.

1. **Determinism & Reproducibility**: Workflows must have explicit dependencies, guaranteed execution orders, and strict input/output contracts. Conversational group chats lack deterministic guarantees and are prone to infinite debate loops.
2. **Operational Simplicity**: A modular monolith with clean internal domain boundaries eliminates distributed transaction overhead, network serialization latency, and deployment complexity for v1.
3. **Direct Integration with Portfolio**: Clean interfaces (`EvaluationProvider`, `ContextProvider`, `ExecutionProvider`) allow seamless future connections to EvalForge, MemoryOps AI, and Symphony.

---

## Consequences

* **Positive**:
  - Deterministic dependency resolution via Kahn's algorithm.
  - Straightforward transaction management and checkpointing in PostgreSQL.
  - Zero network overhead between orchestrator and agent runners in v1.
  - Highly testable with fast in-memory test fixtures.
* **Negative / Trade-offs**:
  - All built-in agents run in the same backend runtime process; CPU-intensive agents could compete for async event loop time (mitigated by running model calls asynchronously via non-blocking I/O).
