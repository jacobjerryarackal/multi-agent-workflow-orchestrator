# ADR-003: Strongly-Typed Agent Contracts via Pydantic Schemas

**Status:** Accepted  
**Date:** 2026-08-23  

---

## Context

In multi-agent systems, agents frequently exchange unstructured text. This leads to common failure modes:
1. Downstream agents hallucinating missing fields.
2. Incompatible data structures causing runtime exceptions.
3. Inability to validate task outputs before advancing DAG branches.

We evaluated:
1. **Unstructured String Message Passing**: Pass raw strings between agents.
2. **Dict / Dynamic JSON Passing**: Pass arbitrary Python dictionaries without static validation.
3. **Strongly-Typed Pydantic Contracts**: Require every agent to define typed Pydantic models for inputs (`input_schema`) and outputs (`output_schema`), validating data at runtime before and after invocation.

---

## Decision

We chose **Option 3: Strongly-Typed Pydantic Contracts**.

1. **Deterministic Data Flow**: Tasks specify explicit JSONPath mappings to upstream task outputs. The engine validates that produced data satisfies the consumer agent's input schema before dispatching.
2. **Automated Reflection on Mismatch**: If an LLM generates invalid fields, the Pydantic `ValidationError` diff is immediately fed back into a self-correction reflection prompt.
3. **Clean Developer Experience**: Auto-generates OpenAPI 3.1 and TypeScript interfaces for the frontend control plane.

---

## Consequences

* **Positive**:
  - Strict compile-time and runtime type safety across the multi-agent pipeline.
  - Clear contracts for testing and mocking agents.
  - Zero ambiguity in frontend inspector views.
* **Negative / Trade-offs**:
  - Requires agents to conform to structured output generation (supported natively by Google Gemini structured outputs / response schema).
