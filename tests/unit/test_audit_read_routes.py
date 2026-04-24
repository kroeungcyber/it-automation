# tests/unit/test_audit_read_routes.py
import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("LOCAL_MODEL", "gemma3:latest")
os.environ.setdefault("CLOUD_MODEL", "claude-sonnet-4-6")

from src.auth.tokens import CurrentUser, Role
from src.guardrail import audit_read_routes

_SUPER_ADMIN = CurrentUser(user_id="U2", username="bob", role=Role.SUPER_ADMIN, jti="jti-2", exp=9999999999)
_IT_ADMIN = CurrentUser(user_id="U1", username="alice", role=Role.IT_ADMIN, jti="jti-1", exp=9999999999)


def _make_app():
    app = FastAPI()
    app.include_router(audit_read_routes.router)
    return app


@pytest.fixture
def client():
    mock_session = MagicMock()
    mock_session.query.return_value.order_by.return_value.filter.return_value.limit.return_value.all.return_value = []
    mock_session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    mock_factory = MagicMock()
    mock_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_factory.return_value.__exit__ = MagicMock(return_value=False)

    audit_read_routes._session_factory = mock_factory
    from src.auth.dependencies import _get_current_user
    app = _make_app()
    app.dependency_overrides[_get_current_user] = lambda: _SUPER_ADMIN
    yield TestClient(app), mock_session


def test_audit_log_returns_200_for_super_admin(client):
    tc, _ = client
    resp = tc.get("/audit/log")
    assert resp.status_code == 200
    assert "records" in resp.json()


def test_audit_log_returns_list(client):
    tc, _ = client
    resp = tc.get("/audit/log")
    assert isinstance(resp.json()["records"], list)


def test_audit_log_rejects_it_admin():
    from src.auth.dependencies import _get_current_user
    app = _make_app()
    app.dependency_overrides[_get_current_user] = lambda: _IT_ADMIN
    tc = TestClient(app)
    resp = tc.get("/audit/log")
    assert resp.status_code == 403


def test_audit_log_accepts_action_plan_id_filter(client):
    tc, mock_session = client
    resp = tc.get("/audit/log?action_plan_id=00000000-0000-0000-0000-000000000001")
    assert resp.status_code == 200
