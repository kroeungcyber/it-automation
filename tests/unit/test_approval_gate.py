import json
import pytest
from unittest.mock import MagicMock, patch
from src.guardrail.models import (
    ActionPlan, ActionRequester, ActionType, ApprovalDecision, DryRunPreview,
)
from src.guardrail.approval_gate import ApprovalGate

_REQUESTER = ActionRequester(user_id="U1", org_role="admin", task_source="slack")


def _plan() -> ActionPlan:
    return ActionPlan(
        task_id="00000000-0000-0000-0000-000000000001",
        action_type=ActionType.AD_DEPROVISION,
        requested_by=_REQUESTER,
    )


def _preview() -> DryRunPreview:
    return DryRunPreview(
        action_plan_id="abc",
        agent="ad_deprovision",
        would_affect=["alice", "bob"],
        estimated_reversible=False,
        raw_preview="2 accounts would be deprovisioned",
    )


def _make_redis(decision: ApprovalDecision | None) -> MagicMock:
    mock = MagicMock()
    if decision is None:
        mock.get.return_value = None
    else:
        mock.get.return_value = json.dumps({"decision": decision.value}).encode()
    return mock


def test_request_approval_stores_pending_in_redis():
    redis = MagicMock()
    gate = ApprovalGate(redis, approval_window_seconds=30)
    notify_fn = MagicMock()
    gate.request_approval(_plan(), _preview(), is_reversible=False, notify_fn=notify_fn)
    redis.setex.assert_called_once()
    call_args = redis.setex.call_args[0]
    stored = json.loads(call_args[2])
    assert stored["decision"] == ApprovalDecision.PENDING.value


def test_request_approval_calls_notify_fn():
    redis = MagicMock()
    gate = ApprovalGate(redis, approval_window_seconds=30)
    notify_fn = MagicMock()
    plan = _plan()
    preview = _preview()
    gate.request_approval(plan, preview, is_reversible=False, notify_fn=notify_fn)
    notify_fn.assert_called_once_with(plan, preview, False)


def test_record_decision_writes_to_redis():
    redis = MagicMock()
    gate = ApprovalGate(redis, approval_window_seconds=30)
    plan = _plan()
    gate.record_decision(str(plan.id), ApprovalDecision.APPROVED)
    redis.set.assert_called_once()
    key, value = redis.set.call_args[0]
    assert ApprovalDecision.APPROVED.value in value


def test_poll_returns_approved_immediately():
    plan = _plan()
    redis = _make_redis(ApprovalDecision.APPROVED)
    gate = ApprovalGate(redis, approval_window_seconds=30)
    result = gate.poll(plan)
    assert result == ApprovalDecision.APPROVED


def test_poll_returns_denied():
    plan = _plan()
    redis = _make_redis(ApprovalDecision.DENIED)
    gate = ApprovalGate(redis, approval_window_seconds=30)
    result = gate.poll(plan)
    assert result == ApprovalDecision.DENIED


def test_poll_returns_timeout_when_key_missing():
    plan = _plan()
    redis = _make_redis(None)
    gate = ApprovalGate(redis, approval_window_seconds=0)  # immediate timeout
    result = gate.poll(plan)
    assert result == ApprovalDecision.TIMEOUT


def test_poll_returns_timeout_after_window_expires():
    plan = _plan()
    redis = MagicMock()
    # Always returns PENDING
    redis.get.return_value = json.dumps({"decision": ApprovalDecision.PENDING.value}).encode()
    gate = ApprovalGate(redis, approval_window_seconds=0)  # zero window = immediate timeout
    result = gate.poll(plan)
    assert result == ApprovalDecision.TIMEOUT
