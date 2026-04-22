import pytest
from unittest.mock import MagicMock
from src.guardrail.models import (
    ActionPlan, ActionTarget, ActionRequester, ActionType,
    ApprovalDecision, AuditEventType, DryRunPreview, RiskTier,
)
from src.guardrail.risk_classifier import ClassificationResult
from src.guardrail.circuit_breaker import CircuitStatus
from src.guardrail.models import CircuitState
from src.guardrail.pipeline import EnforcementPipeline

_REQUESTER = ActionRequester(user_id="U1", org_role="admin", task_source="slack")


def _plan(action_type=ActionType.SSH_EXEC, host="server-dev-01", command="ls /tmp") -> ActionPlan:
    return ActionPlan(
        task_id="00000000-0000-0000-0000-000000000001",
        action_type=action_type,
        target=ActionTarget(host=host),
        parameters={"command": command},
        requested_by=_REQUESTER,
    )


def _preview(reversible=True) -> DryRunPreview:
    return DryRunPreview(
        action_plan_id="abc",
        agent="ssh_exec",
        would_affect=["server-dev-01: ls /tmp"],
        estimated_reversible=reversible,
        raw_preview="ls /tmp",
    )


def _make_pipeline(
    risk_tier=RiskTier.LOW,
    circuit_open=False,
    dry_run_preview=None,
    reversible=True,
    approval_decision=ApprovalDecision.APPROVED,
    execute_result=None,
    execute_raises=None,
    rollback_success=True,
    notify_fn=None,
):
    classifier = MagicMock()
    classifier.classify.return_value = ClassificationResult(tier=risk_tier, method="rules", reason="test")

    cb = MagicMock()
    cb.is_open.return_value = circuit_open
    cb.get_state.return_value = CircuitStatus(
        state=CircuitState.OPEN if circuit_open else CircuitState.CLOSED,
        failure_count=3 if circuit_open else 0,
        agent_type="ssh_exec",
    )
    cb.record_failure.return_value = CircuitStatus(state=CircuitState.OPEN, failure_count=3, agent_type="ssh_exec")
    cb.record_success.return_value = CircuitStatus(state=CircuitState.CLOSED, failure_count=0, agent_type="ssh_exec")

    preview = dry_run_preview or _preview(reversible)
    dry_run_executor = MagicMock()
    dry_run_executor.run.return_value = preview

    rev_checker = MagicMock()
    rev_checker.is_reversible.return_value = reversible

    approval_gate = MagicMock()
    approval_gate.poll.return_value = approval_decision

    agent = MagicMock()
    if execute_raises:
        agent.execute.side_effect = execute_raises
    else:
        agent.execute.return_value = execute_result or {"exit_code": 0}
    agent.rollback.return_value = rollback_success

    audit = MagicMock()

    return EnforcementPipeline(
        risk_classifier=classifier,
        dry_run_executor=dry_run_executor,
        reversibility_checker=rev_checker,
        approval_gate=approval_gate,
        circuit_breaker=cb,
        audit_logger=audit,
        agents={ActionType.SSH_EXEC.value: agent},
        notify_fn=notify_fn or MagicMock(),
    ), audit


# ── Circuit breaker open ─────────────────────────────────────────────────────

def test_circuit_open_returns_circuit_open_outcome():
    pipeline, audit = _make_pipeline(circuit_open=True)
    result = pipeline.run(_plan())
    assert result.outcome == "circuit_open"
    audit.log.assert_called()


# ── LOW risk path ────────────────────────────────────────────────────────────

def test_low_risk_executes_without_dryrun_or_approval():
    pipeline, audit = _make_pipeline(risk_tier=RiskTier.LOW)
    result = pipeline.run(_plan())
    assert result.outcome == "success"
    assert result.risk_tier == RiskTier.LOW
    assert result.dry_run_preview is None


def test_low_risk_success_records_circuit_success():
    pipeline, _ = _make_pipeline(risk_tier=RiskTier.LOW)
    pipeline.run(_plan())
    pipeline._circuit_breaker.record_success.assert_called_once_with(ActionType.SSH_EXEC.value)


def test_low_risk_reversible_failure_triggers_rollback():
    pipeline, audit = _make_pipeline(
        risk_tier=RiskTier.LOW,
        execute_raises=RuntimeError("connection refused"),
    )
    result = pipeline.run(_plan())
    assert result.outcome == "failure"
    assert result.rollback_success is True


def test_low_risk_irreversible_failure_escalates():
    pipeline, audit = _make_pipeline(
        risk_tier=RiskTier.LOW,
        reversible=False,
        execute_raises=RuntimeError("disk full"),
    )
    result = pipeline.run(_plan())
    assert result.outcome == "failure"
    assert result.rollback_success is None  # no rollback attempted


# ── MEDIUM risk path ─────────────────────────────────────────────────────────

def test_medium_risk_runs_dryrun_then_executes():
    pipeline, _ = _make_pipeline(risk_tier=RiskTier.MEDIUM)
    result = pipeline.run(_plan())
    assert result.outcome == "success"
    assert result.dry_run_preview is not None
    pipeline._dry_run_executor.run.assert_called_once()


def test_medium_risk_no_approval_gate():
    pipeline, _ = _make_pipeline(risk_tier=RiskTier.MEDIUM)
    pipeline.run(_plan())
    pipeline._approval_gate.poll.assert_not_called()


def test_medium_risk_reversible_failure_triggers_rollback():
    pipeline, audit = _make_pipeline(
        risk_tier=RiskTier.MEDIUM,
        execute_raises=RuntimeError("ssh timeout"),
    )
    result = pipeline.run(_plan())
    assert result.outcome == "failure"
    assert result.dry_run_preview is not None  # dry-run ran before failure
    assert result.rollback_success is True


# ── HIGH risk path ───────────────────────────────────────────────────────────

def test_high_risk_runs_dryrun_and_approval():
    pipeline, _ = _make_pipeline(
        risk_tier=RiskTier.HIGH,
        approval_decision=ApprovalDecision.APPROVED,
    )
    result = pipeline.run(_plan())
    assert result.outcome == "success"
    pipeline._dry_run_executor.run.assert_called_once()
    pipeline._approval_gate.poll.assert_called_once()


def test_high_risk_denied_returns_denied_outcome():
    pipeline, _ = _make_pipeline(
        risk_tier=RiskTier.HIGH,
        approval_decision=ApprovalDecision.DENIED,
    )
    result = pipeline.run(_plan())
    assert result.outcome == "denied"
    pipeline._agents[ActionType.SSH_EXEC.value].execute.assert_not_called()


def test_high_risk_timeout_returns_timeout_outcome():
    pipeline, _ = _make_pipeline(
        risk_tier=RiskTier.HIGH,
        approval_decision=ApprovalDecision.TIMEOUT,
    )
    result = pipeline.run(_plan())
    assert result.outcome == "timeout"
    pipeline._agents[ActionType.SSH_EXEC.value].execute.assert_not_called()
