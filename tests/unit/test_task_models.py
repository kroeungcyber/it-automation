# tests/unit/test_task_models.py
import pytest
from uuid import UUID
from datetime import datetime
from src.models.task import TaskRequest, TaskRecord, TaskStatus, RouteDecision, TaskSource


def test_task_request_valid():
    req = TaskRequest(
        source=TaskSource.SLACK,
        user_id="U123",
        org_role="employee",
        raw_input="Reset my password",
    )
    assert isinstance(req.id, UUID)
    assert isinstance(req.timestamp, datetime)
    assert req.context == {}


def test_task_request_with_context():
    req = TaskRequest(
        source=TaskSource.JIRA,
        user_id="U456",
        org_role="admin",
        raw_input="Provision new user",
        context={"ticket_id": "IT-42", "urgency": "high"},
    )
    assert req.context["ticket_id"] == "IT-42"


def test_task_request_missing_required_fields():
    with pytest.raises(Exception):
        TaskRequest(source=TaskSource.CLI)  # missing user_id, org_role, raw_input


def test_task_record_defaults():
    req = TaskRequest(
        source=TaskSource.PORTAL,
        user_id="U789",
        org_role="employee",
        raw_input="Check VPN guide",
    )
    record = TaskRecord(request=req)
    assert record.status == TaskStatus.QUEUED
    assert record.route is None
    assert record.result is None
    assert record.error is None


def test_task_record_with_route():
    req = TaskRequest(
        source=TaskSource.CLI,
        user_id="U001",
        org_role="admin",
        raw_input="SSH into db-prod",
    )
    record = TaskRecord(request=req, route=RouteDecision.LOCAL)
    assert record.route == RouteDecision.LOCAL


def test_all_task_sources_valid():
    for source in TaskSource:
        req = TaskRequest(source=source, user_id="u", org_role="r", raw_input="x")
        assert req.source == source
