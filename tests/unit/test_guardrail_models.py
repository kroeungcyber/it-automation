import pytest
from uuid import UUID
from datetime import datetime
from src.guardrail.models import (
    ActionPlan, ActionTarget, ActionRequester, ActionType,
    RiskTier, CircuitState, ApprovalDecision, AuditEventType,
    DryRunPreview, PipelineResult,
)


def _make_plan(**kwargs) -> ActionPlan:
    defaults = dict(
        task_id="00000000-0000-0000-0000-000000000001",
        action_type=ActionType.SSH_EXEC,
        requested_by=ActionRequester(user_id="U1", org_role="admin", task_source="cli"),
    )
    defaults.update(kwargs)
    return ActionPlan(**defaults)


def test_action_plan_generates_id():
    plan = _make_plan()
    assert isinstance(plan.id, UUID)


def test_action_plan_default_target():
    plan = _make_plan()
    assert plan.target.scope == "single"
    assert plan.target.count == 1


def test_action_plan_ai_self_assessment_default():
    plan = _make_plan()
    assert plan.ai_self_assessment == RiskTier.LOW


def test_action_plan_bulk_target():
    plan = _make_plan(target=ActionTarget(host="server-01", scope="bulk", count=50))
    assert plan.target.scope == "bulk"
    assert plan.target.count == 50


def test_all_action_types_valid():
    for at in ActionType:
        plan = _make_plan(action_type=at)
        assert plan.action_type == at


def test_risk_tier_values():
    assert RiskTier.LOW.value == "low"
    assert RiskTier.MEDIUM.value == "medium"
    assert RiskTier.HIGH.value == "high"


def test_circuit_state_values():
    assert CircuitState.CLOSED.value == "closed"
    assert CircuitState.OPEN.value == "open"
    assert CircuitState.HALF_OPEN.value == "half_open"


def test_approval_decision_pending():
    assert ApprovalDecision.PENDING.value == "pending"


def test_dry_run_preview_fields():
    preview = DryRunPreview(
        action_plan_id="abc",
        agent="ssh_exec",
        would_affect=["server-01: restart nginx"],
        estimated_reversible=True,
        raw_preview="systemctl restart nginx",
    )
    assert preview.estimated_reversible is True
    assert len(preview.would_affect) == 1
    assert isinstance(preview.generated_at, datetime)


def test_pipeline_result_success():
    result = PipelineResult(
        action_plan_id="abc",
        outcome="success",
        risk_tier=RiskTier.LOW,
        is_reversible=True,
    )
    assert result.outcome == "success"
    assert result.error is None
