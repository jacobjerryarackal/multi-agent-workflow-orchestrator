# Workflow Event & Telemetry Contract Specification

**Document:** Event Schema, Event Sourcing & Real-time Stream Contracts  
**Status:** Approved Architecture (Day 0)  

---

## 1. Event Model & Schema

Every state transition, execution lifecycle event, failure, retry, and approval generates an immutable `WorkflowEvent`.

```python
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import uuid

class EventType(str, Enum):
    # Workflow Level
    WORKFLOW_SUBMITTED = "WORKFLOW_SUBMITTED"
    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_PAUSED = "WORKFLOW_PAUSED"
    WORKFLOW_RESUMED = "WORKFLOW_RESUMED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    WORKFLOW_CANCELLED = "WORKFLOW_CANCELLED"
    WORKFLOW_TIMED_OUT = "WORKFLOW_TIMED_OUT"

    # Task Level
    TASK_SCHEDULED = "TASK_SCHEDULED"
    TASK_READY = "TASK_READY"
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    TASK_RETRIED = "TASK_RETRIED"
    TASK_CANCELLED = "TASK_CANCELLED"
    TASK_TIMED_OUT = "TASK_TIMED_OUT"

    # Quality & Human Gate
    TASK_WAITING_APPROVAL = "TASK_WAITING_APPROVAL"
    APPROVAL_DECISION_RECORDED = "APPROVAL_DECISION_RECORDED"
    EVALUATION_GATE_SCORED = "EVALUATION_GATE_SCORED"

    # Data & System
    ARTIFACT_PRODUCED = "ARTIFACT_PRODUCED"
    CIRCUIT_BREAKER_TRIGGERED = "CIRCUIT_BREAKER_TRIGGERED"
    STATE_CHECKPOINT_SAVED = "STATE_CHECKPOINT_SAVED"

class WorkflowEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_execution_id: str
    workflow_id: str
    task_execution_id: Optional[str] = None
    task_key: Optional[str] = None
    agent_id: Optional[str] = None
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: Dict[str, Any] = Field(default_factory=dict)
    actor: str = Field(default="system", description="e.g. 'system', 'worker-1', or user email for approvals")
```

---

## 2. Event Sourcing & Real-Time SSE Stream

The backend provides Server-Sent Events (SSE) and WebSockets over `GET /api/v1/executions/{id}/events/stream`:

```json
event: TASK_COMPLETED
data: {
  "id": "evt-7a91bf52-19e0",
  "workflow_execution_id": "exec-992a01",
  "task_key": "research_technical",
  "agent_id": "researcher_agent",
  "event_type": "TASK_COMPLETED",
  "timestamp": "2026-08-23T11:05:00.123Z",
  "payload": {
    "execution_duration_ms": 2410,
    "token_metrics": {
      "prompt_tokens": 450,
      "completion_tokens": 620,
      "total_tokens": 1070
    },
    "output_summary": "Extracted 4 technical findings and 2 architecture tradeoffs."
  }
}
```
