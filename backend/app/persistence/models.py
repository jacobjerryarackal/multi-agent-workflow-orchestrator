"""SQLAlchemy 2.x ORM models representing persistent database entities."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base
from ..domain.models.workflow import (
    WorkflowSpec,
    TaskSpec,
    RetryPolicySpec,
    ApprovalGateSpec,
    EvaluationGateSpec,
)
from ..domain.models.execution import (
    WorkflowExecution,
    WorkflowExecutionStatus,
    TaskExecution,
    TaskExecutionStatus,
)
from ..domain.models.event import WorkflowEvent, EventType
from ..domain.models.artifact import Artifact, ArtifactType

# Fallback JSON type for cross-dialect compatibility (Postgres uses JSONB, SQLite uses JSON)
from sqlalchemy.types import JSON


class WorkflowModel(Base):
    """Database table storing workflow specifications."""
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output_schema: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    max_workflow_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=600)
    max_parallel_tasks: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    tasks: Mapped[List["WorkflowTaskModel"]] = relationship(
        "WorkflowTaskModel",
        back_populates="workflow",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    executions: Mapped[List["WorkflowExecutionModel"]] = relationship(
        "WorkflowExecutionModel",
        back_populates="workflow",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_workflow_name_version"),
        Index("ix_workflows_name", "name"),
    )

    def to_domain(self) -> WorkflowSpec:
        """Converts this ORM model to a pure domain WorkflowSpec."""
        return WorkflowSpec(
            id=self.id,
            name=self.name,
            version=self.version,
            description=self.description,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
            tasks=[task.to_domain() for task in self.tasks],
            max_workflow_duration_seconds=self.max_workflow_duration_seconds,
            max_parallel_tasks=self.max_parallel_tasks,
            created_at=self.created_at,
        )

    @classmethod
    def from_domain(cls, spec: WorkflowSpec) -> "WorkflowModel":
        """Creates an ORM model instance from a pure domain WorkflowSpec."""
        return cls(
            id=spec.id,
            name=spec.name,
            version=spec.version,
            description=spec.description,
            input_schema=spec.input_schema,
            output_schema=spec.output_schema,
            max_workflow_duration_seconds=spec.max_workflow_duration_seconds,
            max_parallel_tasks=spec.max_parallel_tasks,
            created_at=spec.created_at,
            tasks=[WorkflowTaskModel.from_domain(t, spec.id) for t in spec.tasks],
        )


class WorkflowTaskModel(Base):
    """Database table storing task definitions within a workflow."""
    __tablename__ = "workflow_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    task_key: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False)
    depends_on: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    input_mappings: Mapped[Dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    static_inputs: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    retry_policy: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    approval_gate: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    evaluation_gate: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    workflow: Mapped["WorkflowModel"] = relationship("WorkflowModel", back_populates="tasks")

    __table_args__ = (
        UniqueConstraint("workflow_id", "task_key", name="uq_workflow_task_key"),
        Index("ix_workflow_tasks_workflow_id", "workflow_id"),
    )

    def to_domain(self) -> TaskSpec:
        return TaskSpec(
            task_key=self.task_key,
            name=self.name,
            agent_id=self.agent_id,
            depends_on=self.depends_on,
            input_mappings=self.input_mappings,
            static_inputs=self.static_inputs,
            timeout_seconds=self.timeout_seconds,
            retry_policy=RetryPolicySpec(**self.retry_policy) if self.retry_policy else RetryPolicySpec(),
            approval_gate=ApprovalGateSpec(**self.approval_gate) if self.approval_gate else ApprovalGateSpec(),
            evaluation_gate=EvaluationGateSpec(**self.evaluation_gate) if self.evaluation_gate else EvaluationGateSpec(),
        )

    @classmethod
    def from_domain(cls, spec: TaskSpec, workflow_id: str) -> "WorkflowTaskModel":
        return cls(
            workflow_id=workflow_id,
            task_key=spec.task_key,
            name=spec.name,
            agent_id=spec.agent_id,
            depends_on=spec.depends_on,
            input_mappings=spec.input_mappings,
            static_inputs=spec.static_inputs,
            timeout_seconds=spec.timeout_seconds,
            retry_policy=spec.retry_policy.model_dump(),
            approval_gate=spec.approval_gate.model_dump(),
            evaluation_gate=spec.evaluation_gate.model_dump(),
        )


class WorkflowExecutionModel(Base):
    """Database table storing workflow execution runtime instances."""
    __tablename__ = "workflow_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    initial_inputs: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    final_outputs: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    execution_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    workflow: Mapped["WorkflowModel"] = relationship("WorkflowModel", back_populates="executions")
    task_executions: Mapped[List["TaskExecutionModel"]] = relationship(
        "TaskExecutionModel",
        back_populates="workflow_execution",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    events: Mapped[List["WorkflowEventModel"]] = relationship(
        "WorkflowEventModel",
        back_populates="workflow_execution",
        cascade="all, delete-orphan",
        lazy="select",
    )
    artifacts: Mapped[List["ArtifactModel"]] = relationship(
        "ArtifactModel",
        back_populates="workflow_execution",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        Index("ix_workflow_executions_status", "status"),
        Index("ix_workflow_executions_workflow_id", "workflow_id"),
        Index(
            "uq_workflow_executions_idempotency",
            "workflow_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
            sqlite_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    def to_domain(self) -> WorkflowExecution:
        return WorkflowExecution(
            id=self.id,
            workflow_id=self.workflow_id,
            status=WorkflowExecutionStatus(self.status),
            trigger_type=self.trigger_type,
            idempotency_key=self.idempotency_key,
            initial_inputs=self.initial_inputs,
            final_outputs=self.final_outputs,
            error_summary=self.error_summary,
            started_at=self.started_at,
            completed_at=self.completed_at,
            execution_duration_ms=self.execution_duration_ms,
            created_at=self.created_at,
            tasks={t.task_key: t.to_domain() for t in self.task_executions},
        )

    @classmethod
    def from_domain(cls, domain: WorkflowExecution) -> "WorkflowExecutionModel":
        return cls(
            id=domain.id,
            workflow_id=domain.workflow_id,
            status=domain.status.value,
            trigger_type=domain.trigger_type,
            idempotency_key=domain.idempotency_key,
            initial_inputs=domain.initial_inputs,
            final_outputs=domain.final_outputs,
            error_summary=domain.error_summary,
            started_at=domain.started_at,
            completed_at=domain.completed_at,
            execution_duration_ms=domain.execution_duration_ms,
            created_at=domain.created_at,
            task_executions=[TaskExecutionModel.from_domain(t) for t in domain.tasks.values()],
        )


class TaskExecutionModel(Base):
    """Database table storing task execution states."""
    __tablename__ = "task_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False
    )
    task_key: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revision_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    evaluation_history: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    error_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    execution_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[Dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)
    lease_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    leased_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    workflow_execution: Mapped["WorkflowExecutionModel"] = relationship(
        "WorkflowExecutionModel", back_populates="task_executions"
    )

    __table_args__ = (
        UniqueConstraint("workflow_execution_id", "task_key", name="uq_execution_task_key"),
        Index("ix_task_executions_status", "status"),
        Index("ix_task_executions_exec_id", "workflow_execution_id"),
        Index("ix_task_executions_lease", "status", "lease_until"),
    )

    def to_domain(self) -> TaskExecution:
        return TaskExecution(
            id=self.id,
            workflow_execution_id=self.workflow_execution_id,
            task_key=self.task_key,
            agent_id=self.agent_id,
            status=TaskExecutionStatus(self.status),
            attempt_count=self.attempt_count,
            revision_count=self.revision_count,
            input_data=self.input_data,
            output_data=self.output_data,
            evaluation_history=self.evaluation_history,
            error_details=self.error_details,
            started_at=self.started_at,
            completed_at=self.completed_at,
            execution_duration_ms=self.execution_duration_ms,
            token_usage=self.token_usage,
        )

    @classmethod
    def from_domain(cls, domain: TaskExecution) -> "TaskExecutionModel":
        return cls(
            id=domain.id,
            workflow_execution_id=domain.workflow_execution_id,
            task_key=domain.task_key,
            agent_id=domain.agent_id,
            status=domain.status.value,
            attempt_count=domain.attempt_count,
            revision_count=domain.revision_count,
            input_data=domain.input_data,
            output_data=domain.output_data,
            evaluation_history=domain.evaluation_history,
            error_details=domain.error_details,
            started_at=domain.started_at,
            completed_at=domain.completed_at,
            execution_duration_ms=domain.execution_duration_ms,
            token_usage=domain.token_usage,
        )


class WorkflowEventModel(Base):
    """Database table storing the append-only workflow event history."""
    __tablename__ = "workflow_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id: Mapped[str] = mapped_column(String(36), nullable=False)
    task_execution_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    task_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    agent_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="system")

    workflow_execution: Mapped["WorkflowExecutionModel"] = relationship(
        "WorkflowExecutionModel", back_populates="events"
    )

    __table_args__ = (
        Index("ix_workflow_events_exec_id", "workflow_execution_id"),
        Index("ix_workflow_events_timestamp", "timestamp"),
        Index("ix_workflow_events_type", "event_type"),
    )

    def to_domain(self) -> WorkflowEvent:
        return WorkflowEvent(
            id=self.id,
            workflow_execution_id=self.workflow_execution_id,
            workflow_id=self.workflow_id,
            task_execution_id=self.task_execution_id,
            task_key=self.task_key,
            agent_id=self.agent_id,
            event_type=EventType(self.event_type),
            timestamp=self.timestamp,
            payload=self.payload,
            actor=self.actor,
        )

    @classmethod
    def from_domain(cls, domain: WorkflowEvent) -> "WorkflowEventModel":
        return cls(
            id=domain.id,
            workflow_execution_id=domain.workflow_execution_id,
            workflow_id=domain.workflow_id,
            task_execution_id=domain.task_execution_id,
            task_key=domain.task_key,
            agent_id=domain.agent_id,
            event_type=domain.event_type.value,
            timestamp=domain.timestamp,
            payload=domain.payload,
            actor=domain.actor,
        )


class ArtifactModel(Base):
    """Database table storing workflow artifact references and integrity hashes."""
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False
    )
    task_key: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False, default="json")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    workflow_execution: Mapped["WorkflowExecutionModel"] = relationship(
        "WorkflowExecutionModel", back_populates="artifacts"
    )

    __table_args__ = (
        Index("ix_artifacts_exec_id", "workflow_execution_id"),
        Index("ix_artifacts_task_key", "task_key"),
        Index("ix_artifacts_checksum", "checksum_sha256"),
    )

    def to_domain(self) -> Artifact:
        return Artifact(
            id=self.id,
            workflow_execution_id=self.workflow_execution_id,
            task_key=self.task_key,
            name=self.name,
            artifact_type=ArtifactType(self.artifact_type),
            content=self.content,
            checksum_sha256=self.checksum_sha256,
            metadata=self.artifact_metadata,
            created_at=self.created_at,
        )

    @classmethod
    def from_domain(cls, domain: Artifact) -> "ArtifactModel":
        return cls(
            id=domain.id,
            workflow_execution_id=domain.workflow_execution_id,
            task_key=domain.task_key,
            name=domain.name,
            artifact_type=domain.artifact_type.value,
            content=domain.content,
            checksum_sha256=domain.checksum_sha256,
            artifact_metadata=domain.metadata,
            created_at=domain.created_at,
        )
