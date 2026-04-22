# tests/unit/test_guardrail_routes_unit.py
import os
import pytest
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("LOCAL_MODEL", "gemma3:latest")
os.environ.setdefault("CLOUD_MODEL", "claude-sonnet-4-6")

from fastapi.testclient import TestClient
from src.guardrail.models import (
    ActionRequester, ActionType, ApprovalDecision,
    PipelineResult, RiskTier,
)


def _plan_payload(**kwargs) -> dict:
    defaults = {
        "task_id": "00000000-0000-0000-0000-000000000001",
        "action_type": "ssh_exec",
        "target": {"host": "server-dev-01", "scope": "single", "count": 1},
        "parameters": {"command": "ls /tmp"},
        "requested_by": {"user_id": "U1", "org_role": "admin", "task_source": "cli"},
    }
    defaults.update(kwargs)
    return defaults


def _make_pipeline_result(outcome="success", risk_tier=RiskTier.LOW) -> PipelineResult:
    return PipelineResult(
        action_plan_id="00000000-0000-0000-0000-000000000002",
        outcome=outcome,
        risk_tier=risk_tier,
        is_reversible=True,
    )


@pytest.fixture
def client():
    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = _make_pipeline_result()

    with patch("src.guardrail.app.build_pipeline", return_value=mock_pipeline), \
         patch("src.guardrail.app.get_engine"), \
         patch("src.guardrail.app.get_session_factory"), \
         patch("src.guardrail.app.Redis"):
        from src.guardrail.app import create_app
        app = create_app()
        yield TestClient(app), mock_pipeline


def test_authorize_returns_202_on_success(client):
    tc, _ = client
    resp = tc.post("/guardrail/authorize", json=_plan_payload())
    assert resp.status_code == 202
    assert resp.json()["outcome"] == "success"


def test_authorize_returns_action_plan_id(client):
    tc, _ = client
    resp = tc.post("/guardrail/authorize", json=_plan_payload())
    assert "action_plan_id" in resp.json()


def test_authorize_denied_returns_200_with_denied_outcome(client):
    tc, mock_pipeline = client
    mock_pipeline.run.return_value = _make_pipeline_result(outcome="denied", risk_tier=RiskTier.HIGH)
    resp = tc.post("/guardrail/authorize", json=_plan_payload())
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "denied"


def test_authorize_circuit_open_returns_503(client):
    tc, mock_pipeline = client
    mock_pipeline.run.return_value = _make_pipeline_result(outcome="circuit_open")
    resp = tc.post("/guardrail/authorize", json=_plan_payload())
    assert resp.status_code == 503


def test_record_approval_decision(client):
    tc, _ = client
    resp = tc.post(
        "/guardrail/approvals/00000000-0000-0000-0000-000000000002/decision",
        json={"decision": "approved"},
    )
    assert resp.status_code == 200


def test_circuit_breaker_status_endpoint(client):
    tc, _ = client
    with patch("src.guardrail.routes.get_circuit_breaker") as mock_cb:
        mock_cb.return_value.get_all_states.return_value = []
        resp = tc.get("/guardrail/circuit-breaker/status")
        assert resp.status_code == 200


def test_circuit_breaker_reset_endpoint(client):
    tc, _ = client
    with patch("src.guardrail.routes.get_circuit_breaker") as mock_cb:
        mock_cb.return_value.reset = MagicMock()
        resp = tc.post("/guardrail/circuit-breaker/reset", json={"agent_type": "ssh_exec"})
        assert resp.status_code == 200
