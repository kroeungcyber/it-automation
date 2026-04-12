import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("LOCAL_MODEL", "gemma3:latest")
os.environ.setdefault("CLOUD_MODEL", "claude-sonnet-4-6")


@pytest.fixture
def client():
    sensitive_q = MagicMock()
    cloud_q = MagicMock()

    with patch("src.router.app.get_engine"), \
         patch("src.router.app.get_session_factory"), \
         patch("src.router.app.get_queues") as mock_gq:

        mock_gq.return_value = {"sensitive": sensitive_q, "cloud": cloud_q}

        from src.router.app import create_app
        from src.router import routes

        app = create_app()
        routes.task_store.clear()
        tc = TestClient(app)
        yield tc, sensitive_q, cloud_q
        routes.task_store.clear()


def test_ad_password_reset_routes_local(client):
    tc, sensitive_q, cloud_q = client
    resp = tc.post("/tasks", json={
        "source": "slack", "user_id": "U1", "org_role": "admin",
        "raw_input": "Reset Alice's AD password",
    })
    assert resp.status_code == 202
    assert resp.json()["route"] == "local"
    sensitive_q.enqueue.assert_called_once()
    cloud_q.enqueue.assert_not_called()


def test_backup_routes_local(client):
    tc, sensitive_q, cloud_q = client
    resp = tc.post("/tasks", json={
        "source": "cli", "user_id": "admin", "org_role": "admin",
        "raw_input": "Run backup job on server-02",
    })
    assert resp.status_code == 202
    assert resp.json()["route"] == "local"
    sensitive_q.enqueue.assert_called_once()


def test_vpn_guide_routes_cloud(client):
    tc, sensitive_q, cloud_q = client
    resp = tc.post("/tasks", json={
        "source": "portal", "user_id": "U2", "org_role": "employee",
        "raw_input": "What's our VPN setup guide?",
    })
    assert resp.json()["route"] == "cloud"
    cloud_q.enqueue.assert_called_once()
    sensitive_q.enqueue.assert_not_called()


def test_wifi_issue_routes_cloud(client):
    tc, sensitive_q, cloud_q = client
    resp = tc.post("/tasks", json={
        "source": "teams", "user_id": "U3", "org_role": "employee",
        "raw_input": "My laptop can't connect to WiFi",
    })
    assert resp.json()["route"] == "cloud"
    cloud_q.enqueue.assert_called_once()
    sensitive_q.enqueue.assert_not_called()


def test_secret_payload_reroutes_local(client):
    tc, sensitive_q, cloud_q = client
    resp = tc.post("/tasks", json={
        "source": "portal", "user_id": "U4", "org_role": "employee",
        "raw_input": "password=hunter2 is not working",
    })
    assert resp.json()["route"] == "local"
    sensitive_q.enqueue.assert_called_once()
    cloud_q.enqueue.assert_not_called()


def test_ambiguous_input_failsafe_local(client):
    tc, sensitive_q, cloud_q = client
    resp = tc.post("/tasks", json={
        "source": "slack", "user_id": "U5", "org_role": "employee",
        "raw_input": "Check server logs",
    })
    assert resp.json()["route"] == "local"
    sensitive_q.enqueue.assert_called_once()
    cloud_q.enqueue.assert_not_called()


def test_get_task_after_create(client):
    tc, _, _ = client
    post = tc.post("/tasks", json={
        "source": "jira", "user_id": "U6", "org_role": "it_admin",
        "raw_input": "How do I submit an IT request?",
    })
    task_id = post.json()["task_id"]
    get = tc.get(f"/tasks/{task_id}")
    assert get.status_code == 200
    assert get.json()["status"] == "queued"


def test_unknown_task_id_404(client):
    tc, _, _ = client
    assert tc.get("/tasks/00000000-0000-0000-0000-000000000000").status_code == 404
