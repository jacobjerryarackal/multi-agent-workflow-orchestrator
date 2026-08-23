"""Unit tests verifying Pydantic schema validation and domain contracts."""

import pytest
from pydantic import ValidationError
from app.domain.models import (
    WorkflowSpec,
    TaskSpec,
    RetryPolicySpec,
    ApprovalGateSpec,
    EvaluationGateSpec,
    AgentMetadata,
    AgentCapability,
    AgentResult,
    ProducedArtifact,
    Artifact,
    ArtifactType,
    WorkflowEvent,
    EventType,
    FailureRecord,
    FailureCategory,
    FailureSeverity,
    RecoveryActionType,
)


def test_valid_task_spec_creation():
    task = TaskSpec(
        task_key="research_node",
        name="Market Research",
        agent_id="researcher_agent",
        depends_on=["plan_node"],
        input_mappings={"topic": "$.workflow.inputs.topic"},
        static_inputs={"depth": "comprehensive"},
        timeout_seconds=45,
        retry_policy=RetryPolicySpec(max_attempts=4, backoff_multiplier=2.0),
        approval_gate=ApprovalGateSpec(required=False),
        evaluation_gate=EvaluationGateSpec(enabled=True, min_pass_score=0.85),
    )
    assert task.task_key == "research_node"
    assert task.timeout_seconds == 45
    assert task.retry_policy.max_attempts == 4
    assert task.evaluation_gate.min_pass_score == 0.85


def test_task_spec_validation_failure():
    # timeout_seconds < 5 should fail ge=5 validation
    with pytest.raises(ValidationError):
        TaskSpec(
            task_key="invalid_task",
            name="Invalid Task",
            agent_id="planner",
            timeout_seconds=2,
        )


def test_valid_workflow_spec_creation(sample_task_spec: TaskSpec):
    workflow = WorkflowSpec(
        name="test_pipeline",
        version=2,
        description="A test workflow pipeline",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        tasks=[sample_task_spec],
        max_parallel_tasks=8,
    )
    assert workflow.name == "test_pipeline"
    assert workflow.version == 2
    assert len(workflow.tasks) == 1
    assert workflow.max_parallel_tasks == 8


def test_workflow_spec_empty_tasks_rejected():
    with pytest.raises(ValidationError):
        WorkflowSpec(
            name="empty_pipeline",
            version=1,
            description="Empty tasks list",
            input_schema={},
            output_schema={},
            tasks=[],  # min_items=1
        )


def test_agent_result_contract():
    result = AgentResult(
        success=True,
        structured_data={"summary": "Detailed analysis result", "confidence": 0.95},
        artifacts=[
            ProducedArtifact(
                name="findings.json",
                artifact_type="json",
                content_or_uri='{"key": "value"}',
                checksum_sha256="abc123hash",
            )
        ],
        execution_duration_ms=1250,
    )
    assert result.success is True
    assert result.structured_data["confidence"] == 0.95
    assert len(result.artifacts) == 1
    assert result.execution_duration_ms == 1250


def test_artifact_integrity_verification():
    raw_data = {"key": "test_value", "number": 42}
    artifact = Artifact.create_from_data(
        workflow_execution_id="exec-123",
        task_key="task-a",
        name="output.json",
        data=raw_data,
        artifact_type=ArtifactType.JSON,
    )
    assert artifact.verify_integrity() is True

    # Tamper with content and verify failure
    artifact.content = artifact.content + "tampered"
    assert artifact.verify_integrity() is False


def test_workflow_event_contract():
    event = WorkflowEvent(
        workflow_execution_id="exec-abc",
        workflow_id="wf-123",
        task_key="task_1",
        event_type=EventType.TASK_STARTED,
        payload={"worker_id": "worker-pool-01"},
    )
    assert event.event_type == EventType.TASK_STARTED
    assert event.actor == "system"
    assert event.payload["worker_id"] == "worker-pool-01"


def test_failure_record_contract():
    failure = FailureRecord(
        workflow_execution_id="exec-999",
        task_key="analyst_task",
        category=FailureCategory.INFRASTRUCTURE_PROVIDER_FAILURE,
        severity=FailureSeverity.HIGH,
        error_type="GoogleAPIError",
        error_message="503 Service Unavailable",
        retryable=True,
        attempt_number=2,
        recovery_action=RecoveryActionType.RETRY_WITH_BACKOFF,
    )
    assert failure.category == FailureCategory.INFRASTRUCTURE_PROVIDER_FAILURE
    assert failure.retryable is True
    assert failure.recovery_action == RecoveryActionType.RETRY_WITH_BACKOFF
