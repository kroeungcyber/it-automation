# tests/integration/test_auth_api.py
import os
import pytest
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("LOCAL_MODEL", "gemma3:latest")
os.environ.setdefault("CLOUD_MODEL", "claude-sonnet-4-6")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-integration")

from fastapi.testclient import TestClient
from src.auth.password import hash_password
from src.auth.tokens import CurrentUser, Role
from src.guardrail.models import PipelineResult, RiskTier

_MOCK_USER_PASSWORD = "correct-password"


def _mock_user():
    user = MagicMock()
    user.id = "00000000-0000-0000-0000-000000000001"
    user.username = "alice"
    user.hashed_password = hash_password(_MOCK_USER_PASSWORD)
    user.role = "it_admin"
    user.is_active = True
    return user


@pytest.fixture
def client():
    mock_user = _mock_user()
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_user

    mock_sync_factory = MagicMock()
    mock_sync_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_sync_factory.return_value.__exit__ = MagicMock(return_value=False)

    mock_redis = MagicMock()
    mock_redis.exists.return_value = 0

    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = PipelineResult(
        action_plan_id="test-plan-id", outcome="success", risk_tier=RiskTier.LOW, is_reversible=True,
    )

    with patch("src.guardrail.app.build_pipeline", return_value=mock_pipeline), \
         patch("src.guardrail.app.get_engine"), \
         patch("src.guardrail.app.get_session_factory"), \
         patch("src.guardrail.app.get_sync_engine"), \
         patch("src.guardrail.app.get_sync_session_factory", return_value=mock_sync_factory), \
         patch("src.guardrail.app.Redis") as MockRedis:
        MockRedis.from_url.return_value = mock_redis
        from src.guardrail.app import create_app
        app = create_app()
        yield TestClient(app), mock_redis


def test_login_with_valid_credentials_returns_token(client):
    tc, _ = client
    resp = tc.post("/auth/login", json={"username": "alice", "password": _MOCK_USER_PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 28800


def test_login_with_wrong_password_returns_401(client):
    tc, _ = client
    resp = tc.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401


def test_me_endpoint_requires_auth(client):
    tc, _ = client
    resp = tc.get("/auth/me")
    assert resp.status_code == 401


def test_me_returns_user_info_with_valid_token(client):
    tc, _ = client
    login = tc.post("/auth/login", json={"username": "alice", "password": _MOCK_USER_PASSWORD})
    token = login.json()["access_token"]
    resp = tc.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"
    assert resp.json()["role"] == "it_admin"


def test_logout_revokes_token(client):
    tc, mock_redis = client
    login = tc.post("/auth/login", json={"username": "alice", "password": _MOCK_USER_PASSWORD})
    token = login.json()["access_token"]
    resp = tc.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204
    mock_redis.setex.assert_called_once()


def test_token_gates_guardrail_endpoint(client):
    tc, _ = client
    resp = tc.post("/guardrail/authorize", json={
        "task_id": "00000000-0000-0000-0000-000000000001",
        "action_type": "ssh_exec",
        "target": {"host": "server-dev-01", "scope": "single", "count": 1},
        "parameters": {"command": "ls /tmp"},
        "requested_by": {"user_id": "U1", "org_role": "it_admin", "task_source": "cli"},
    })
    assert resp.status_code == 401


def test_it_admin_token_accesses_guardrail(client):
    tc, _ = client
    login = tc.post("/auth/login", json={"username": "alice", "password": _MOCK_USER_PASSWORD})
    token = login.json()["access_token"]
    resp = tc.post(
        "/guardrail/authorize",
        json={
            "task_id": "00000000-0000-0000-0000-000000000001",
            "action_type": "ssh_exec",
            "target": {"host": "server-dev-01", "scope": "single", "count": 1},
            "parameters": {"command": "ls /tmp"},
            "requested_by": {"user_id": "U1", "org_role": "it_admin", "task_source": "cli"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    # Pipeline is mocked — just verify auth passed (not 401/403)
    assert resp.status_code in (200, 202, 503)
