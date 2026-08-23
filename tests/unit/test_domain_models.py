"""Unit tests verifying domain execution and state models."""

import pytest
from app.domain.models import (
    WorkflowExecution,
    WorkflowExecutionStatus,
    TaskExecution,
    TaskExecutionStatus,
    AgentMetadata,
    AgentCapability,
)


def test_task_execution_state_defaults():
    task_exec = TaskExecution(
        workflow_execution_id="exec-1",
        task_key="task_planner",
        agent_id="planner_agent",
    )
    assert task_exec.status == TaskExecutionStatus.PENDING
    assert task_exec.attempt_count == 0
    assert task_exec.input_data == {}
    assert task_exec.output_data == {}


def test_workflow_execution_lifecycle_initialization():
    workflow_exec = WorkflowExecution(
        workflow_id="wf-research-01",
        trigger_type="api",
        initial_inputs={"topic": "Agentic AI"},
    )
    assert workflow_exec.status == WorkflowExecutionStatus.QUEUED
    assert workflow_exec.initial_inputs["topic"] == "Agentic AI"
    assert workflow_exec.final_outputs == {}
    assert workflow_exec.error_summary is None


def test_agent_metadata_specification():
    metadata = AgentMetadata(
        agent_id="synthesizer_agent",
        name="Synthesizer Agent",
        version="1.0.0",
        description="Aggregates and synthesizes multi-perspective findings",
        capabilities=[AgentCapability.SYNTHESIS, AgentCapability.DATA_ANALYSIS],
        system_instruction="You are an expert synthesizer. Combine inputs logically.",
        temperature=0.1,
    )
    assert metadata.agent_id == "synthesizer_agent"
    assert AgentCapability.SYNTHESIS in metadata.capabilities
    assert metadata.temperature == 0.1
