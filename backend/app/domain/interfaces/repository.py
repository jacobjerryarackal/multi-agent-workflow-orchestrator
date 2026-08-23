"""Abstract repository interfaces for workflow persistence."""

from typing import List, Optional, Protocol
from ..models.workflow import WorkflowSpec
from ..models.execution import WorkflowExecution, TaskExecution
from ..models.event import WorkflowEvent
from ..models.artifact import Artifact


class WorkflowRepository(Protocol):
    """Protocol for persisting and retrieving workflow definitions."""

    async def save_workflow_spec(self, spec: WorkflowSpec) -> WorkflowSpec:
        ...

    async def get_workflow_spec(self, workflow_id: str) -> Optional[WorkflowSpec]:
        ...

    async def list_workflow_specs(self, limit: int = 50, offset: int = 0) -> List[WorkflowSpec]:
        ...


class ExecutionRepository(Protocol):
    """Protocol for persisting and updating runtime execution instances."""

    async def create_workflow_execution(self, execution: WorkflowExecution) -> WorkflowExecution:
        ...

    async def get_workflow_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        ...

    async def update_workflow_execution(self, execution: WorkflowExecution) -> WorkflowExecution:
        ...

    async def update_task_execution(self, task_exec: TaskExecution) -> TaskExecution:
        ...

    async def claim_task_for_execution(
        self, workflow_execution_id: str, task_key: str
    ) -> Optional[TaskExecution]:
        """Atomically locks and claims a READY task for execution using row-level locking."""
        ...


class EventRepository(Protocol):
    """Protocol for appending and querying immutable workflow telemetry events."""

    async def append_event(self, event: WorkflowEvent) -> WorkflowEvent:
        ...

    async def list_events_for_execution(self, execution_id: str) -> List[WorkflowEvent]:
        ...


class ArtifactRepository(Protocol):
    """Protocol for storing and retrieving produced workflow artifacts."""

    async def save_artifact(self, artifact: Artifact) -> Artifact:
        ...

    async def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        ...

    async def list_artifacts_for_execution(self, execution_id: str) -> List[Artifact]:
        ...
