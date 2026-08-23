"""Domain models for Agent definitions, capabilities, execution context, and execution results."""

from enum import Enum
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field
from .artifact import Artifact


class AgentCapability(str, Enum):
    """Categorized functional capabilities of specialized agents."""
    PLANNING = "planning"
    RESEARCH = "research"
    DATA_ANALYSIS = "data_analysis"
    CRITIQUE = "critique"
    SYNTHESIS = "synthesis"
    TRANSFORMATION = "transformation"
    VALIDATION = "validation"


class AgentMetadata(BaseModel):
    """Metadata describing a registered agent's identity and parameters."""
    agent_id: str = Field(..., description="Unique slug for agent, e.g. 'planner_agent'")
    name: str = Field(..., description="Human-readable name")
    version: str = Field(default="1.0.0", description="Semantic version")
    description: str = Field(..., description="Agent purpose and responsibilities")
    capabilities: List[AgentCapability] = Field(default_factory=list)
    system_instruction: str = Field(..., description="Core system prompt/instruction")
    default_model: str = Field(default="gemini-2.5-flash")
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    max_retries: int = Field(default=3, ge=0, le=5)


class AgentExecutionContext(BaseModel):
    """Deterministic context payload supplied to an agent on execution."""
    workflow_execution_id: str
    workflow_id: str
    task_key: str
    attempt_number: int = 1
    input_payload: Dict[str, Any] = Field(default_factory=dict)
    upstream_artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    execution_context_vars: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = 60


class TokenUsageMetrics(BaseModel):
    """Token consumption accounting for an agent execution."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ProducedArtifact(BaseModel):
    """Structured artifact metadata generated during task execution."""
    name: str
    artifact_type: str = "json"  # json, markdown, text, csv
    content_or_uri: str
    checksum_sha256: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Strongly-typed execution result produced by an agent."""
    success: bool = Field(..., description="True if agent execution succeeded")
    structured_data: Dict[str, Any] = Field(default_factory=dict, description="Output payload matching agent schema")
    artifacts: List[ProducedArtifact] = Field(default_factory=list)
    error_message: Optional[str] = None
    error_category: Optional[str] = None
    execution_duration_ms: int = Field(default=0, ge=0)
    token_metrics: TokenUsageMetrics = Field(default_factory=TokenUsageMetrics)
    metadata: Dict[str, Any] = Field(default_factory=dict)
