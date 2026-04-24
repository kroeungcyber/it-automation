# tests/integration/test_guardrail_api.py
import os
import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("LOCAL_MODEL", "gemma3:latest")
os.environ.setdefault("CLOUD_MODEL", "claude-sonnet-4-6")

from src.auth.tokens import CurrentUser, Role
from src.guardrail.models import (
    ActionType, ApprovalDecision, CircuitState, PipelineResult, RiskTier,
)

_IT_ADMIN = CurrentUser(user_id="U1", username="alice", role=Role.IT_ADMIN, jti="jti-1", exp=9999999999)
_SUPER_ADMIN = CurrentUser(user_id="U2", username="bob", role=Role.SUPER_ADMIN, jti="jti-2", exp=9999999999)


def _plan(action_type="ssh_exec", host="server-dev-01", command="ls /tmp", scope="single", count=1) -> dict:
    return {
        "task_id": "00000000-0000-0000-0000-000000000001",
        "action_type": action_type,
        "target": {"host": host, "scope": scope, "count": count},
        "parameters": {"command": command} if command else {},
        "requested_by": {"user_id": "U1", "org_role": "admin", "task_source": "cli"},
    }


@pytest.fixture
def client():
    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = PipelineResult(
        action_plan_id="00000000-0000-0000-0000-000000000002",
        outcome="success", risk_tier=RiskTier.LOW, is_reversible=True,
    )
    with patch("src.guardrail.app.build_pipeline", return_value=mock_pipeline), \
         patch("src.guardrail.app.get_engine"), \
         patch("src.guardrail.app.get_session_factory"), \
         patch("src.guardrail.app.get_sync_engine"), \
         patch("src.guardrail.app.get_sync_session_factory"), \
         patch("src.guardrail.app.Redis"):
        from src.guardrail.app import create_app
        from src.auth.dependencies import _get_current_user
        app = create_app()
        app.dependency_overrides[_get_current_user] = lambda: _IT_ADMIN
        yield TestClient(app), mock_pipeline


# ── Authorization endpoint ───────────────────────────────────────────────────

def test_low_risk_success(client):
    tc, mock_pipeline = client
    mock_pipeline.run.return_value = PipelineResult(
        action_plan_id="plan-1", outcome="success", risk_tier=RiskTier.LOW, is_reversible=True,
    )
    resp = tc.post("/guardrail/authorize", json=_plan())
    assert resp.status_code == 202
    assert resp.json()["outcome"] == "success"
    assert resp.json()["risk_tier"] == "low"


def test_high_risk_approved(client):
    tc, mock_pipeline = client
    mock_pipeline.run.return_value = PipelineResult(
        action_plan_id="plan-2", outcome="success", risk_tier=RiskTier.HIGH, is_reversible=False,
    )
    resp = tc.post("/guardrail/authorize", json=_plan(action_type="ad_deprovision", scope="bulk", count=50, command=""))
    assert resp.status_code == 202
    assert resp.json()["outcome"] == "success"


def test_high_risk_denied(client):
    tc, mock_pipeline = client
    mock_pipeline.run.return_value = PipelineResult(
        action_plan_id="plan-3", outcome="denied", risk_tier=RiskTier.HIGH, is_reversible=False,
    )
    resp = tc.post("/guardrail/authorize", json=_plan(action_type="vault_write", command=""))
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "denied"


def test_high_risk_timeout(client):
    tc, mock_pipeline = client
    mock_pipeline.run.return_value = PipelineResult(
        action_plan_id="plan-4", outcome="timeout", risk_tier=RiskTier.HIGH, is_reversible=False,
    )
    resp = tc.post("/guardrail/authorize", json=_plan(action_type="vault_write", command=""))
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "timeout"


def test_circuit_open_returns_503(client):
    tc, mock_pipeline = client
    mock_pipeline.run.return_value = PipelineResult(
        action_plan_id="plan-5", outcome="circuit_open", risk_tier=RiskTier.HIGH, is_reversible=False,
    )
    resp = tc.post("/guardrail/authorize", json=_plan())
    assert resp.status_code == 503


def test_reversible_failure_with_rollback(client):
    tc, mock_pipeline = client
    mock_pipeline.run.return_value = PipelineResult(
        action_plan_id="plan-6", outcome="failure", risk_tier=RiskTier.LOW,
        is_reversible=True, error="connection refused", rollback_success=True,
    )
    resp = tc.post("/guardrail/authorize", json=_plan())
    body = resp.json()
    assert body["outcome"] == "failure"
    assert body["rollback_success"] is True


def test_irreversible_failure_no_rollback(client):
    tc, mock_pipeline = client
    mock_pipeline.run.return_value = PipelineResult(
        action_plan_id="plan-7", outcome="failure", risk_tier=RiskTier.HIGH,
        is_reversible=False, error="disk full", rollback_success=None,
    )
    resp = tc.post("/guardrail/authorize", json=_plan())
    body = resp.json()
    assert body["outcome"] == "failure"
    assert body["rollback_success"] is None

# ── Approval decision endpoint ───────────────────────────────────────────────

def test_record_approved_decision(client):
    tc, _ = client
    with patch("src.guardrail.routes.get_approval_gate") as mock_gate_fn:
        mock_gate = MagicMock()
        mock_gate_fn.return_value = mock_gate
        resp = tc.post(
            "/guardrail/approvals/00000000-0000-0000-0000-000000000099/decision",
            json={"decision": "approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "approved"
        mock_gate.record_decision.assert_called_once_with(
            "00000000-0000-0000-0000-000000000099", ApprovalDecision.APPROVED,
        )


def test_invalid_decision_returns_400(client):
    tc, _ = client
    resp = tc.post(
        "/guardrail/approvals/00000000-0000-0000-0000-000000000099/decision",
        json={"decision": "maybe"},
    )
    assert resp.status_code == 400


# ── Circuit breaker endpoints ────────────────────────────────────────────────

def test_circuit_breaker_status(client):
    tc, _ = client
    with patch("src.guardrail.routes.get_circuit_breaker") as mock_cb_fn:
        from src.guardrail.circuit_breaker import CircuitStatus
        mock_cb_fn.return_value.get_all_states.return_value = [
            CircuitStatus(state=CircuitState.CLOSED, failure_count=0, agent_type="ssh_exec")
        ]
        resp = tc.get("/guardrail/circuit-breaker/status")
        assert resp.status_code == 200
        states = resp.json()["states"]
        assert states[0]["state"] == "closed"


def test_circuit_breaker_reset(client):
    tc, _ = client
    from src.auth.dependencies import _get_current_user
    tc.app.dependency_overrides[_get_current_user] = lambda: _SUPER_ADMIN
    with patch("src.guardrail.routes.get_circuit_breaker") as mock_cb_fn:
        mock_cb = MagicMock()
        mock_cb_fn.return_value = mock_cb
        resp = tc.post("/guardrail/circuit-breaker/reset", json={"agent_type": "ssh_exec"})
        assert resp.status_code == 200
        mock_cb.reset.assert_called_once_with("ssh_exec")
    tc.app.dependency_overrides[_get_current_user] = lambda: _IT_ADMIN


def test_medium_risk_success(client):
    tc, mock_pipeline = client
    mock_pipeline.run.return_value = PipelineResult(
        action_plan_id="plan-8", outcome="success", risk_tier=RiskTier.MEDIUM, is_reversible=True,
    )
    resp = tc.post("/guardrail/authorize", json=_plan(host="db-prod-01", command="systemctl status"))
    assert resp.status_code == 202
    assert resp.json()["risk_tier"] == "medium"
