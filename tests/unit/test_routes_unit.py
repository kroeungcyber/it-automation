# tests/unit/test_routes_unit.py
import os
import pytest
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("LOCAL_MODEL", "gemma3:latest")
os.environ.setdefault("CLOUD_MODEL", "claude-sonnet-4-6")


@pytest.fixture
def client_with_mocks():
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

        from fastapi.testclient import TestClient
        yield TestClient(app), sensitive_q, cloud_q, routes

        routes.task_store.clear()


def test_ssh_routes_to_sensitive_queue(client_with_mocks):
    client, sensitive_q, cloud_q, _ = client_with_mocks
    resp = client.post("/tasks", json={
        "source": "cli",
        "user_id": "admin01",
        "org_role": "admin",
        "raw_input": "SSH into db-prod and restart nginx",
    })
    assert resp.status_code == 202
    assert resp.json()["route"] == "local"
    sensitive_q.enqueue.assert_called_once()
    cloud_q.enqueue.assert_not_called()


def test_vpn_guide_routes_to_cloud_queue(client_with_mocks):
    client, sensitive_q, cloud_q, _ = client_with_mocks
    resp = client.post("/tasks", json={
        "source": "slack",
        "user_id": "user42",
        "org_role": "employee",
        "raw_input": "What's our VPN setup guide?",
    })
    assert resp.status_code == 202
    assert resp.json()["route"] == "cloud"
    cloud_q.enqueue.assert_called_once()
    sensitive_q.enqueue.assert_not_called()


def test_response_has_task_id_and_status(client_with_mocks):
    client, _, _, _ = client_with_mocks
    resp = client.post("/tasks", json={
        "source": "portal",
        "user_id": "u1",
        "org_role": "employee",
        "raw_input": "How do I submit an IT request?",
    })
    body = resp.json()
    assert "task_id" in body
    assert body["status"] == "queued"


def test_get_task_returns_record(client_with_mocks):
    client, _, _, _ = client_with_mocks
    post_resp = client.post("/tasks", json={
        "source": "jira",
        "user_id": "it_staff",
        "org_role": "it_admin",
        "raw_input": "What's the VPN guide?",
    })
    task_id = post_resp.json()["task_id"]

    get_resp = client.get(f"/tasks/{task_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["request"]["id"] == task_id


def test_get_unknown_task_returns_404(client_with_mocks):
    client, _, _, _ = client_with_mocks
    resp = client.get("/tasks/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_secret_in_payload_reroutes_to_sensitive(client_with_mocks):
    client, sensitive_q, cloud_q, _ = client_with_mocks
    resp = client.post("/tasks", json={
        "source": "portal",
        "user_id": "user99",
        "org_role": "employee",
        "raw_input": "My password=hunter2 is not working",
    })
    assert resp.status_code == 202
    assert resp.json()["route"] == "local"
    sensitive_q.enqueue.assert_called_once()
    cloud_q.enqueue.assert_not_called()
