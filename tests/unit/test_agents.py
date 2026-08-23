"""Unit tests for the five built-in specialized agents."""

import pytest
from app.agents.builtins import (
    PlannerAgent,
    ResearcherAgent,
    AnalystAgent,
    ReviewerAgent,
    SynthesizerAgent,
)
from app.domain.models import AgentExecutionContext
from tests.conftest import MockModelProvider


# =============================================================================
# 1. PLANNER AGENT TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_planner_agent_execution():
    canned = {
        "PlanOutput": {
            "plan_summary": "Two-phase research strategy",
            "sub_tasks": [
                {
                    "task_key": "res_1",
                    "name": "Market Inquiry",
                    "description": "Analyze market trends",
                    "required_capability": "research",
                    "depends_on": [],
                    "expected_output_type": "json",
                }
            ],
            "risk_factors": ["Data availability"],
        }
    }
    provider = MockModelProvider(canned)
    planner = PlannerAgent(provider)

    context = AgentExecutionContext(
        workflow_execution_id="exec-1",
        workflow_id="wf-1",
        task_key="plan_node",
        input_payload={"objective": "Analyze cloud market", "constraints": ["focus on 2026"]},
    )
    result = await planner.execute(context)
    assert result.success is True
    assert result.structured_data["plan_summary"] == "Two-phase research strategy"
    assert len(result.structured_data["sub_tasks"]) == 1
    assert len(result.artifacts) == 1
    assert result.artifacts[0].name == "execution_plan.json"


# =============================================================================
# 2. RESEARCHER AGENT TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_researcher_agent_execution():
    canned = {
        "ResearchOutput": {
            "findings": [
                {
                    "topic": "Orchestration Engines",
                    "detail": "DAG engines provide deterministic execution guarantees.",
                    "sources_cited": ["Whitepaper 2026"],
                    "confidence": 0.95,
                }
            ],
            "assumptions": ["Standard PostgreSQL storage"],
            "uncertainties": [],
            "recommended_follow_up": ["Evaluate retry policies"],
        }
    }
    provider = MockModelProvider(canned)
    researcher = ResearcherAgent(provider)

    context = AgentExecutionContext(
        workflow_execution_id="exec-1",
        workflow_id="wf-1",
        task_key="research_node",
        input_payload={"objective": "Study DAG engines", "questions": ["What are the invariants?"]},
    )
    result = await researcher.execute(context)
    assert result.success is True
    assert len(result.structured_data["findings"]) == 1
    assert result.structured_data["findings"][0]["confidence"] == 0.95
    assert len(result.artifacts) == 1
    assert result.artifacts[0].name == "research_findings.json"


# =============================================================================
# 3. ANALYST AGENT TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_analyst_agent_execution():
    canned = {
        "AnalysisOutput": {
            "insights": ["Modular monolith outperforms microservices for v1."],
            "tradeoffs": [
                {
                    "option_name": "Modular Monolith",
                    "pros": ["Zero network serialization", "Simple transactions"],
                    "cons": ["Single process resource sharing"],
                    "impact_score": 0.9,
                }
            ],
            "conclusions": ["Adopt modular monolith architecture."],
            "confidence_score": 0.92,
        }
    }
    provider = MockModelProvider(canned)
    analyst = AnalystAgent(provider)

    context = AgentExecutionContext(
        workflow_execution_id="exec-1",
        workflow_id="wf-1",
        task_key="analyst_node",
        input_payload={
            "research_findings": [{"topic": "Architecture", "detail": "Monolith vs Microservices"}],
            "evaluation_criteria": ["Latency", "Maintainability"],
        },
    )
    result = await analyst.execute(context)
    assert result.success is True
    assert len(result.structured_data["tradeoffs"]) == 1
    assert result.structured_data["confidence_score"] == 0.92
    assert len(result.artifacts) == 1
    assert result.artifacts[0].name == "analysis_report.json"


# =============================================================================
# 4. REVIEWER AGENT TESTS (PASS, FAIL, REQUIRES_REVISION)
# =============================================================================

@pytest.mark.asyncio
async def test_reviewer_agent_pass_decision():
    canned = {
        "ReviewOutput": {
            "decision": "PASS",
            "passed_checks": ["Factual accuracy", "Contract adherence"],
            "failed_checks": [],
            "issues": [],
            "required_changes": [],
            "confidence": 0.95,
        }
    }
    provider = MockModelProvider(canned)
    reviewer = ReviewerAgent(provider)

    context = AgentExecutionContext(
        workflow_execution_id="exec-1",
        workflow_id="wf-1",
        task_key="review_node",
        input_payload={"target_content": {"key": "valid findings"}},
    )
    result = await reviewer.execute(context)
    assert result.success is True
    assert result.structured_data["decision"] == "PASS"
    assert len(result.structured_data["passed_checks"]) == 2


@pytest.mark.asyncio
async def test_reviewer_agent_requires_revision_decision():
    canned = {
        "ReviewOutput": {
            "decision": "REQUIRES_REVISION",
            "passed_checks": ["Completeness"],
            "failed_checks": ["Citation verification"],
            "issues": [{"description": "Missing source for claim X", "severity": "HIGH"}],
            "required_changes": ["Add primary citations"],
            "confidence": 0.88,
        }
    }
    provider = MockModelProvider(canned)
    reviewer = ReviewerAgent(provider)

    context = AgentExecutionContext(
        workflow_execution_id="exec-1",
        workflow_id="wf-1",
        task_key="review_node",
        input_payload={"target_content": {"key": "unverified findings"}},
    )
    result = await reviewer.execute(context)
    assert result.success is True
    assert result.structured_data["decision"] == "REQUIRES_REVISION"
    assert len(result.structured_data["issues"]) == 1


# =============================================================================
# 5. SYNTHESIZER AGENT TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_synthesizer_agent_with_clean_review():
    canned = {
        "SynthesisOutput": {
            "title": "Comprehensive Strategy Report",
            "executive_summary": "Synthesized executive findings.",
            "key_conclusions": ["Conclusion 1", "Conclusion 2"],
            "detailed_report": "# Comprehensive Report\nDetails here...",
            "review_acknowledgment": "Review audit verified all quality standards with status PASS.",
        }
    }
    provider = MockModelProvider(canned)
    synthesizer = SynthesizerAgent(provider)

    context = AgentExecutionContext(
        workflow_execution_id="exec-1",
        workflow_id="wf-1",
        task_key="synthesizer_node",
        input_payload={
            "planner_summary": "Strategic Plan",
            "research_findings": [{"topic": "A", "detail": "Data"}],
            "analysis_insights": ["Insight 1"],
            "review_decision": "PASS",
        },
    )
    result = await synthesizer.execute(context)
    assert result.success is True
    assert result.structured_data["title"] == "Comprehensive Strategy Report"
    assert "PASS" in result.structured_data["review_acknowledgment"]
    assert len(result.artifacts) == 1
    assert result.artifacts[0].name == "final_synthesis.json"


@pytest.mark.asyncio
async def test_synthesizer_agent_reflects_review_warnings():
    canned = {
        "SynthesisOutput": {
            "title": "Provisional Strategy Report",
            "executive_summary": "Provisional findings with noted caveats.",
            "key_conclusions": ["Provisional Takeaway"],
            "detailed_report": "Details...",
            "review_acknowledgment": "WARNING: Reviewer audit returned REQUIRES_REVISION due to missing citations.",
        }
    }
    provider = MockModelProvider(canned)
    synthesizer = SynthesizerAgent(provider)

    context = AgentExecutionContext(
        workflow_execution_id="exec-1",
        workflow_id="wf-1",
        task_key="synthesizer_node",
        input_payload={
            "review_decision": "REQUIRES_REVISION",
            "review_issues": ["Missing source citations"],
        },
    )
    result = await synthesizer.execute(context)
    assert result.success is True
    assert "WARNING" in result.structured_data["review_acknowledgment"]
