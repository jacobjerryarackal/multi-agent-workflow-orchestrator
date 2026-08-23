# Typed Agent Contract Specification

**Document:** Agent Definition, Input/Output Contracts & Execution Result  
**Status:** Approved Architecture (Day 0)  

---

## 1. BaseAgent Domain Specification

Every agent registered in the system is defined by an immutable `AgentDefinition` and implements the `BaseAgent` interface.

```python
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field

class AgentCapability(str):
    PLANNING = "planning"
    RESEARCH = "research"
    DATA_ANALYSIS = "data_analysis"
    CRITIQUE = "critique"
    SYNTHESIS = "synthesis"
    TRANSFORMATION = "transformation"
    VALIDATION = "validation"

class AgentMetadata(BaseModel):
    agent_id: str = Field(..., description="Unique agent identifier, e.g. 'planner_agent'")
    name: str = Field(..., description="Human-readable agent name")
    version: str = Field(default="1.0.0", description="Semantic version of agent specification")
    description: str = Field(..., description="Concise description of agent purpose and role")
    capabilities: List[AgentCapability] = Field(default_factory=list)
    system_instruction: str = Field(..., description="Core system prompt/instructions")
    default_model: str = Field(default="gemini-2.5-flash", description="Target Gemini model")
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    timeout_seconds: int = Field(default=60, ge=1, le=300)
    max_retries: int = Field(default=3, ge=0, le=5)
```

---

## 2. Agent Execution Context Contract

When the orchestrator invokes an agent, it supplies a deterministic, scoped `AgentExecutionContext`:

```python
class ArtifactReference(BaseModel):
    artifact_id: str
    name: str
    artifact_type: str
    uri: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AgentExecutionContext(BaseModel):
    workflow_execution_id: str
    workflow_id: str
    task_key: str
    attempt_number: int = 1
    input_payload: Dict[str, Any] = Field(default_factory=dict)
    upstream_artifacts: List[ArtifactReference] = Field(default_factory=list)
    execution_context_vars: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = 60
```

---

## 3. Agent Execution Result Contract

The agent returns a strongly typed `AgentResult` model:

```python
class TokenUsageMetrics(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class ProducedArtifact(BaseModel):
    name: str
    artifact_type: str  # e.g., "json", "markdown", "text", "csv", "binary"
    content_or_uri: str
    checksum_sha256: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AgentResult(BaseModel):
    success: bool = Field(..., description="True if agent completed successfully")
    structured_data: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Structured JSON matching agent's output_schema"
    )
    artifacts: List[ProducedArtifact] = Field(
        default_factory=list, 
        description="Artifacts generated during task run"
    )
    error_message: Optional[str] = Field(
        default=None, 
        description="Detailed error message if success is False"
    )
    error_category: Optional[str] = Field(
        default=None, 
        description="Classification code if failed"
    )
    execution_duration_ms: int = Field(
        ..., 
        description="Elapsed wall-clock time in milliseconds"
    )
    token_metrics: TokenUsageMetrics = Field(default_factory=TokenUsageMetrics)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

---

## 4. Built-in Agent Specializations (Initial 5 Agents)

| Agent ID | Role & Purpose | Input Schema | Output Schema |
| :--- | :--- | :--- | :--- |
| `planner_agent` | Decomposes user goals into actionable sub-questions & strategy | `{ "objective": str, "constraints": list[str] }` | `{ "plan_summary": str, "sub_tasks": list[dict], "risk_factors": list[str] }` |
| `researcher_agent` | Conducts structured multi-perspective inquiry & extraction | `{ "topic": str, "questions": list[str], "scope": str }` | `{ "findings": list[dict], "sources_cited": list[str], "confidence": float }` |
| `analyst_agent` | Performs qualitative & quantitative reasoning on findings | `{ "data_points": list[dict], "evaluation_criteria": list[str] }` | `{ "insights": list[dict], "tradeoffs": list[dict], "recommendations": list[str] }` |
| `reviewer_agent` | Evaluates completeness, identifies contradictions and flaws | `{ "proposed_output": dict, "quality_standards": list[str] }` | `{ "is_acceptable": bool, "critique": list[str], "suggested_revisions": list[str] }` |
| `synthesizer_agent`| Integrates all upstream findings into a cohesive final deliverable | `{ "inputs_from_all_branches": list[dict], "target_format": str }` | `{ "executive_summary": str, "detailed_body": str, "key_conclusions": list[str] }` |
