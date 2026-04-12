# src/models/task.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskSource(str, Enum):
    SLACK = "slack"
    TEAMS = "teams"
    JIRA = "jira"
    SERVICENOW = "servicenow"
    PORTAL = "portal"
    CLI = "cli"
    SCHEDULER = "scheduler"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class RouteDecision(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"


class TaskRequest(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source: TaskSource
    user_id: str
    org_role: str
    raw_input: str
    context: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskRecord(BaseModel):
    request: TaskRequest
    status: TaskStatus = TaskStatus.QUEUED
    route: RouteDecision | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
