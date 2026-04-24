# tests/unit/test_auth_dependencies.py
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.auth.tokens import CurrentUser, Role, issue_token
from src.auth import dependencies as deps

SECRET = "test-secret-unit"


def _make_redis() -> MagicMock:
    mock = MagicMock()
    mock.exists.return_value = 0
    return mock


def _make_app(minimum_role: Role) -> FastAPI:
    app = FastAPI()

    @app.get("/protected")
    def protected(_: CurrentUser = deps.require_role(minimum_role)):
        return {"ok": True}

    return app


def _auth_header(role: Role) -> dict:
    token = issue_token("U1", "alice", role, SECRET, expiry_seconds=3600)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _setup():
    deps.set_auth_config(SECRET, _make_redis())
    yield
    deps._secret = None
    deps._redis = None


def test_employee_blocked_from_it_admin_route():
    tc = TestClient(_make_app(Role.IT_ADMIN))
    resp = tc.get("/protected", headers=_auth_header(Role.EMPLOYEE))
    assert resp.status_code == 403


def test_it_admin_allowed_on_it_admin_route():
    tc = TestClient(_make_app(Role.IT_ADMIN))
    resp = tc.get("/protected", headers=_auth_header(Role.IT_ADMIN))
    assert resp.status_code == 200


def test_super_admin_inherits_it_admin_permission():
    tc = TestClient(_make_app(Role.IT_ADMIN))
    resp = tc.get("/protected", headers=_auth_header(Role.SUPER_ADMIN))
    assert resp.status_code == 200


def test_missing_token_returns_401():
    tc = TestClient(_make_app(Role.EMPLOYEE))
    resp = tc.get("/protected")
    assert resp.status_code == 401


def test_invalid_token_returns_401():
    tc = TestClient(_make_app(Role.EMPLOYEE))
    resp = tc.get("/protected", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
