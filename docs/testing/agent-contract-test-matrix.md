# Agent Contract Test Matrix

**Document:** Built-in Agent Specifications, Contracts, Artifacts, and Test Mappings  
**Phase:** Phase 3  
**Status:** Implemented & Verified  

---

## 1. Agent Contract Matrix

| Agent ID | Class Name | Capabilities | Input Model | Output Model | Emitted Artifact | Primary Test Coverage |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `planner_agent` | `PlannerAgent` | `PLANNING` | `PlanInput` | `PlanOutput` | `execution_plan.json` | `tests/unit/test_agents.py::test_planner_agent_execution` |
| `researcher_agent`| `ResearcherAgent`| `RESEARCH` | `ResearchInput` | `ResearchOutput` | `research_findings.json`| `tests/unit/test_agents.py::test_researcher_agent_execution` |
| `analyst_agent` | `AnalystAgent` | `DATA_ANALYSIS` | `AnalysisInput` | `AnalysisOutput` | `analysis_report.json` | `tests/unit/test_agents.py::test_analyst_agent_execution` |
| `reviewer_agent` | `ReviewerAgent` | `CRITIQUE`, `VALIDATION`| `ReviewInput` | `ReviewOutput` | `audit_report.json` | `tests/unit/test_agents.py::test_reviewer_agent_pass_decision`<br>`test_reviewer_agent_requires_revision_decision` |
| `synthesizer_agent`|`SynthesizerAgent`| `SYNTHESIS` | `SynthesisInput` | `SynthesisOutput`| `final_synthesis.json` | `tests/unit/test_agents.py::test_synthesizer_agent_with_clean_review`<br>`test_synthesizer_agent_reflects_review_warnings` |

---

## 2. Invariants & Contract Enforcement

1. **Structured Input/Output Pydantic Validation**:
   - Inputs are strictly validated against `input_schema` before prompt construction.
   - Any validation error returns `AgentResult(success=False, error_category='contract_validation_failure')` without crashing.
2. **Model Decoupling via `ModelProvider` Protocol**:
   - Zero agent classes import `google.genai` or vendor SDKs.
   - All model interaction is mediated via `generate_structured(prompt, system_instruction, response_schema)`.
3. **Deterministic Artifact Production**:
   - Every agent outputs a typed `ProducedArtifact` with a SHA-256 integrity hash for downstream DAG nodes to consume.
4. **Adversarial Reviewer Gating**:
   - The Reviewer agent outputs structured `ReviewDecision` enum values (`PASS`, `FAIL`, `REQUIRES_REVISION`).
   - The Synthesizer explicitly captures review status in its `review_acknowledgment` field.
