# Typed Workflow Contract Specification

**Document:** Workflow Definition, Task Schema & Execution Payload Contracts  
**Status:** Approved Architecture (Day 0)  

---

## 1. Workflow Definition Schema (Pydantic & JSON Schema)

```python
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class RetryPolicySpec(BaseModel):
    max_attempts: int = Field(default=3, ge=0, le=5)
    initial_interval_seconds: float = Field(default=2.0, ge=0.5, le=60.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=5.0)
    jitter: bool = Field(default=True)
    retryable_categories: List[str] = Field(
        default=["TRANSIENT_PROVIDER_ERROR", "RATE_LIMIT_ERROR", "TIMEOUT_ERROR"]
    )

class ApprovalGateSpec(BaseModel):
    required: bool = Field(default=False)
    approver_roles: List[str] = Field(default=["operator", "admin"])
    timeout_seconds: int = Field(default=86400) # 24 hours
    auto_action_on_timeout: str = Field(default="ESCALATE") # ESCALATE or FAIL

class EvaluationGateSpec(BaseModel):
    enabled: bool = Field(default=False)
    evaluator_name: str = Field(default="standard_quality_check")
    min_pass_score: float = Field(default=0.8, ge=0.0, le=1.0)
    rejection_policy: str = Field(default="RETRY") # RETRY, ESCALATE, FAIL

class TaskSpec(BaseModel):
    task_key: str = Field(..., description="Unique alphanumeric identifier for task within workflow")
    name: str = Field(..., description="Human-readable task label")
    agent_id: str = Field(..., description="Target agent in registry")
    depends_on: List[str] = Field(default_factory=list, description="List of parent task_keys")
    input_mappings: Dict[str, str] = Field(
        default_factory=dict, 
        description="JSONPath expressions mapping upstream task outputs to this task's inputs"
    )
    static_inputs: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    retry_policy: RetryPolicySpec = Field(default_factory=RetryPolicySpec)
    approval_gate: ApprovalGateSpec = Field(default_factory=ApprovalGateSpec)
    evaluation_gate: EvaluationGateSpec = Field(default_factory=EvaluationGateSpec)

class WorkflowSpec(BaseModel):
    name: str = Field(..., description="Unique workflow identifier, e.g. 'deep_research_synthesis'")
    version: int = Field(default=1, ge=1)
    description: str = Field(..., description="Summary of workflow capability")
    input_schema: Dict[str, Any] = Field(..., description="JSON Schema for initial workflow inputs")
    output_schema: Dict[str, Any] = Field(..., description="JSON Schema for final workflow outputs")
    tasks: List[TaskSpec] = Field(..., min_items=1)
    max_workflow_duration_seconds: int = Field(default=600, ge=30, le=3600)
    max_parallel_tasks: int = Field(default=5, ge=1, le=20)
```

---

## 2. Canonical Workflow Example (DAG Graph in JSON)

The following example represents the classic Planner -> Parallel Research/Analysis -> Reviewer -> Synthesizer workflow:

```json
{
  "name": "deep_analysis_and_synthesis",
  "version": 1,
  "description": "Decomposes a strategic topic, conducts parallel multi-source inquiry, critiques findings, and synthesizes final report.",
  "input_schema": {
    "type": "object",
    "required": ["topic", "depth"],
    "properties": {
      "topic": { "type": "string" },
      "depth": { "type": "string", "enum": ["brief", "comprehensive", "exhaustive"] }
    }
  },
  "output_schema": {
    "type": "object",
    "required": ["executive_summary", "detailed_body"],
    "properties": {
      "executive_summary": { "type": "string" },
      "detailed_body": { "type": "string" }
    }
  },
  "tasks": [
    {
      "task_key": "plan_phase",
      "name": "Decompose & Plan",
      "agent_id": "planner_agent",
      "depends_on": [],
      "static_inputs": { "constraints": ["focus on verifiable facts", "quantify risks"] },
      "input_mappings": { "objective": "$.workflow.inputs.topic" },
      "timeout_seconds": 45
    },
    {
      "task_key": "research_market",
      "name": "Market & Industry Inquiry",
      "agent_id": "researcher_agent",
      "depends_on": ["plan_phase"],
      "input_mappings": {
        "topic": "$.workflow.inputs.topic",
        "questions": "$.tasks.plan_phase.outputs.sub_tasks[0].questions"
      },
      "timeout_seconds": 60
    },
    {
      "task_key": "research_technical",
      "name": "Technical Architecture Inquiry",
      "agent_id": "researcher_agent",
      "depends_on": ["plan_phase"],
      "input_mappings": {
        "topic": "$.workflow.inputs.topic",
        "questions": "$.tasks.plan_phase.outputs.sub_tasks[1].questions"
      },
      "timeout_seconds": 60
    },
    {
      "task_key": "analyze_tradeoffs",
      "name": "Tradeoff & Cost Analysis",
      "agent_id": "analyst_agent",
      "depends_on": ["research_market", "research_technical"],
      "input_mappings": {
        "data_points": "$.tasks.research_technical.outputs.findings"
      },
      "timeout_seconds": 60
    },
    {
      "task_key": "review_and_audit",
      "name": "Quality & Factual Audit",
      "agent_id": "reviewer_agent",
      "depends_on": ["analyze_tradeoffs"],
      "input_mappings": {
        "proposed_output": "$.tasks.analyze_tradeoffs.outputs"
      },
      "approval_gate": {
        "required": true,
        "timeout_seconds": 3600
      },
      "timeout_seconds": 45
    },
    {
      "task_key": "final_synthesis",
      "name": "Executive Synthesis",
      "agent_id": "synthesizer_agent",
      "depends_on": ["review_and_audit"],
      "input_mappings": {
        "inputs_from_all_branches": "$.tasks.analyze_tradeoffs.outputs.insights"
      },
      "timeout_seconds": 60
    }
  ]
}
```
