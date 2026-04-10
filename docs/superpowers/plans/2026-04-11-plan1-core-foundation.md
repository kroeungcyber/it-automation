# IT Automation System — Plan 1: Core Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational layer of the IT Automation System — project structure, Pydantic models, PostgreSQL persistence, Redis queues, two-pass classifier, and the Task Router API that accepts requests and dispatches them to the correct queue.

**Architecture:** A FastAPI service exposes `POST /tasks` and `GET /tasks/{id}`. All adapters (Slack, Teams, etc.) normalize input to a `TaskRequest` schema and POST it here. The router runs a two-pass classifier (keyword/regex rules → spaCy fallback; fail-safe = LOCAL), persists the task in PostgreSQL, and pushes to either `sensitive-queue` or `cloud-queue` in Redis. A payload scanner blocks any secret patterns from reaching the cloud queue.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy (async), asyncpg, PostgreSQL 16, Redis 7, RQ, spaCy (en_core_web_sm), structlog, PyYAML, pytest, httpx, Docker Compose

---

## File Map

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Dependencies and tool config |
| `.env.example` | Environment variable template |
| `Dockerfile` | Container build |
| `docker-compose.yml` | PostgreSQL + Redis + app for dev |
| `config/classification_rules.yaml` | Keyword/regex routing rules (configurable, no code change needed to tune) |
| `src/config.py` | App settings loaded from environment via pydantic-settings |
| `src/shared/logging.py` | structlog configuration |
| `src/models/task.py` | `TaskRequest`, `TaskRecord`, `TaskStatus`, `RouteDecision`, `TaskSource` enums |
| `src/db/connection.py` | SQLAlchemy async engine + session factory + context manager |
| `src/db/migrations/001_initial.sql` | `tasks` table schema |
| `src/queue/redis_queues.py` | RQ `Queue` wrappers: `sensitive-queue` and `cloud-queue` |
| `src/router/rules.py` | `RuleEngine` — loads YAML rules, runs regex pass 1 |
| `src/router/payload_scanner.py` | `PayloadScanner` — detects secret patterns in text |
| `src/router/classifier.py` | `Classifier` — two-pass: rules → spaCy → fail-safe LOCAL |
| `src/router/routes.py` | `POST /tasks`, `GET /tasks/{id}` FastAPI route handlers |
| `src/router/app.py` | FastAPI app factory — wires classifier, queues, DB, routes |
| `tests/conftest.py` | Shared pytest fixtures |
| `tests/unit/test_config.py` | Settings load from env |
| `tests/unit/test_task_models.py` | TaskRequest/TaskRecord validation |
| `tests/unit/test_db_connection.py` | Engine factory unit test |
| `tests/unit/test_redis_queues.py` | Queue name and construction |
| `tests/unit/test_rules.py` | Rule engine golden dataset |
| `tests/unit/test_payload_scanner.py` | Secret pattern detection |
| `tests/unit/test_classifier.py` | Classifier golden dataset (CI-blocking) |
| `tests/unit/test_routes_unit.py` | Route handler unit tests with mocked deps |
| `tests/integration/conftest.py` | Integration-level fixtures |
| `tests/integration/test_router_api.py` | End-to-end routing integration tests |

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: all `__init__.py` files and directories

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "it-automation"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.2.1",
    "sqlalchemy[asyncio]>=2.0.29",
    "asyncpg>=0.29.0",
    "redis>=5.0.3",
    "rq>=1.16.2",
    "spacy>=3.7.4",
    "structlog>=24.1.0",
    "python-dotenv>=1.0.1",
    "pyyaml>=6.0.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.1.1",
    "pytest-asyncio>=0.23.6",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create .env.example**

```env
DATABASE_URL=postgresql+asyncpg://itauto:itauto@localhost:5432/itauto
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://localhost:11434
LOCAL_MODEL=gemma3:latest
CLOUD_MODEL=claude-sonnet-4-6
LOG_LEVEL=INFO
```

- [ ] **Step 3: Create Dockerfile**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e ".[dev]"
RUN python -m spacy download en_core_web_sm
COPY . .
```

- [ ] **Step 4: Create docker-compose.yml**

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: itauto
      POSTGRES_PASSWORD: itauto
      POSTGRES_DB: itauto
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./src/db/migrations:/docker-entrypoint-initdb.d

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - postgres
      - redis
    command: uvicorn src.router.app:app --host 0.0.0.0 --port 8000 --reload

volumes:
  postgres_data:
```

- [ ] **Step 5: Create directories and __init__.py files**

```bash
mkdir -p src/{models,db/migrations,queue,router,shared} \
         tests/{unit,integration} \
         config

touch src/__init__.py \
      src/models/__init__.py \
      src/db/__init__.py \
      src/queue/__init__.py \
      src/router/__init__.py \
      src/shared/__init__.py \
      tests/__init__.py \
      tests/unit/__init__.py \
      tests/integration/__init__.py \
      tests/conftest.py \
      tests/integration/conftest.py
```

- [ ] **Step 6: Install dependencies and download spaCy model**

```bash
pip install -e ".[dev]" && python -m spacy download en_core_web_sm
```

Expected: no errors; last line shows spaCy model download confirmation.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .env.example Dockerfile docker-compose.yml src/ tests/ config/
git commit -m "chore: project scaffold — dependencies, Docker, directory structure"
```

---

### Task 2: Config and logging

**Files:**
- Create: `src/config.py`
- Create: `src/shared/logging.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_config.py
import importlib
import pytest


def _load_settings(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("LOCAL_MODEL", "gemma3:latest")
    monkeypatch.setenv("CLOUD_MODEL", "claude-sonnet-4-6")
    import src.config as cfg
    importlib.reload(cfg)
    return cfg.Settings()


def test_settings_load_from_env(monkeypatch):
    settings = _load_settings(monkeypatch)
    assert settings.database_url == "postgresql+asyncpg://u:p@localhost/db"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.anthropic_api_key == "sk-test"


def test_settings_log_level_default(monkeypatch):
    settings = _load_settings(monkeypatch)
    assert settings.log_level == "INFO"


def test_settings_model_defaults(monkeypatch):
    settings = _load_settings(monkeypatch)
    assert settings.local_model == "gemma3:latest"
    assert settings.cloud_model == "claude-sonnet-4-6"
```

- [ ] **Step 2: Run test to confirm failure**

```bash
pytest tests/unit/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 3: Implement src/config.py**

```python
# src/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    anthropic_api_key: str
    ollama_base_url: str
    local_model: str = "gemma3:latest"
    cloud_model: str = "claude-sonnet-4-6"
    log_level: str = "INFO"
```

- [ ] **Step 4: Implement src/shared/logging.py**

```python
# src/shared/logging.py
import logging
import structlog


def configure_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/config.py src/shared/logging.py tests/unit/test_config.py
git commit -m "feat: config via pydantic-settings and structlog setup"
```

---

### Task 3: TaskRequest and TaskRecord models

**Files:**
- Create: `src/models/task.py`
- Create: `tests/unit/test_task_models.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/unit/test_task_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.models.task'`

- [ ] **Step 3: Implement src/models/task.py**

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_task_models.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/models/task.py tests/unit/test_task_models.py
git commit -m "feat: TaskRequest and TaskRecord Pydantic models"
```

---

### Task 4: PostgreSQL schema and connection

**Files:**
- Create: `src/db/migrations/001_initial.sql`
- Create: `src/db/connection.py`
- Create: `tests/unit/test_db_connection.py`

- [ ] **Step 1: Create src/db/migrations/001_initial.sql**

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY,
    source VARCHAR(20) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    org_role VARCHAR(255) NOT NULL,
    raw_input TEXT NOT NULL,
    context JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    route VARCHAR(10),
    result JSONB,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);
```

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/test_db_connection.py
from unittest.mock import MagicMock, patch


def test_get_engine_calls_create_async_engine():
    with patch("src.db.connection.create_async_engine") as mock_create:
        mock_engine = MagicMock()
        mock_create.return_value = mock_engine

        from src.db.connection import get_engine
        engine = get_engine("postgresql+asyncpg://u:p@localhost/db")

        mock_create.assert_called_once_with(
            "postgresql+asyncpg://u:p@localhost/db", echo=False
        )
        assert engine is mock_engine


def test_get_session_factory_returns_sessionmaker():
    from unittest.mock import MagicMock, patch
    with patch("src.db.connection.async_sessionmaker") as mock_sm:
        mock_factory = MagicMock()
        mock_sm.return_value = mock_factory
        mock_engine = MagicMock()

        from src.db.connection import get_session_factory
        factory = get_session_factory(mock_engine)

        mock_sm.assert_called_once_with(mock_engine, expire_on_commit=False)
        assert factory is mock_factory
```

- [ ] **Step 3: Run tests to confirm failure**

```bash
pytest tests/unit/test_db_connection.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.db.connection'`

- [ ] **Step 4: Implement src/db/connection.py**

```python
# src/db/connection.py
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def get_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    return create_async_engine(database_url, echo=echo)


def get_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_db_connection.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/db/migrations/001_initial.sql src/db/connection.py tests/unit/test_db_connection.py
git commit -m "feat: PostgreSQL schema and async SQLAlchemy connection"
```

---

### Task 5: Redis queue setup

**Files:**
- Create: `src/queue/redis_queues.py`
- Create: `tests/unit/test_redis_queues.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_redis_queues.py
from unittest.mock import MagicMock, patch


def test_get_queues_returns_sensitive_and_cloud_keys():
    with patch("src.queue.redis_queues.Redis") as mock_redis_cls, \
         patch("src.queue.redis_queues.Queue") as mock_queue_cls:
        mock_redis_cls.from_url.return_value = MagicMock()
        mock_queue_cls.side_effect = lambda name, connection: MagicMock(name=name)

        from src.queue.redis_queues import get_queues
        queues = get_queues("redis://localhost:6379/0")

        assert "sensitive" in queues
        assert "cloud" in queues


def test_get_queues_uses_correct_queue_names():
    names_used = []
    with patch("src.queue.redis_queues.Redis") as mock_redis_cls, \
         patch("src.queue.redis_queues.Queue") as mock_queue_cls:
        mock_redis_cls.from_url.return_value = MagicMock()
        mock_queue_cls.side_effect = lambda name, connection: names_used.append(name) or MagicMock()

        from src.queue.redis_queues import get_queues
        get_queues("redis://localhost:6379/0")

        assert "sensitive-queue" in names_used
        assert "cloud-queue" in names_used


def test_get_queues_connects_with_provided_url():
    with patch("src.queue.redis_queues.Redis") as mock_redis_cls, \
         patch("src.queue.redis_queues.Queue"):
        mock_redis_cls.from_url.return_value = MagicMock()

        from src.queue.redis_queues import get_queues
        get_queues("redis://myhost:6379/1")

        mock_redis_cls.from_url.assert_called_with("redis://myhost:6379/1")
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/unit/test_redis_queues.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.queue.redis_queues'`

- [ ] **Step 3: Implement src/queue/redis_queues.py**

```python
# src/queue/redis_queues.py
from redis import Redis
from rq import Queue

SENSITIVE_QUEUE_NAME = "sensitive-queue"
CLOUD_QUEUE_NAME = "cloud-queue"


def get_queues(redis_url: str) -> dict[str, Queue]:
    conn = Redis.from_url(redis_url)
    return {
        "sensitive": Queue(SENSITIVE_QUEUE_NAME, connection=conn),
        "cloud": Queue(CLOUD_QUEUE_NAME, connection=conn),
    }
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_redis_queues.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/queue/redis_queues.py tests/unit/test_redis_queues.py
git commit -m "feat: Redis RQ queue setup (sensitive-queue, cloud-queue)"
```

---

### Task 6: Keyword rule engine

**Files:**
- Create: `config/classification_rules.yaml`
- Create: `src/router/rules.py`
- Create: `tests/unit/test_rules.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_rules.py
import pytest
from src.router.rules import RuleEngine, RuleMatch


@pytest.fixture
def engine():
    return RuleEngine.from_yaml("config/classification_rules.yaml")


def test_local_ad_password_reset(engine):
    assert engine.classify("Reset Alice's AD password") == RuleMatch.LOCAL


def test_local_ssh(engine):
    assert engine.classify("SSH into db-prod and check disk") == RuleMatch.LOCAL


def test_local_backup(engine):
    assert engine.classify("Run backup job on server-02") == RuleMatch.LOCAL


def test_local_provision_user(engine):
    assert engine.classify("Provision new user account in AD") == RuleMatch.LOCAL


def test_local_audit_log(engine):
    assert engine.classify("Show me the audit log for user jsmith") == RuleMatch.LOCAL


def test_cloud_vpn_guide(engine):
    assert engine.classify("What's our VPN setup guide?") == RuleMatch.CLOUD


def test_cloud_wifi_issue(engine):
    assert engine.classify("My laptop can't connect to WiFi") == RuleMatch.CLOUD


def test_cloud_doc_request(engine):
    assert engine.classify("How do I submit an IT request?") == RuleMatch.CLOUD


def test_ambiguous_server_logs_returns_none(engine):
    assert engine.classify("Check server logs") is None


def test_ambiguous_onboarding_returns_none(engine):
    assert engine.classify("Help me with onboarding") is None


def test_case_insensitive_local(engine):
    assert engine.classify("RESET my AD PASSWORD") == RuleMatch.LOCAL


def test_case_insensitive_cloud(engine):
    assert engine.classify("VPN GUIDE PLEASE") == RuleMatch.CLOUD
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/unit/test_rules.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.router.rules'`

- [ ] **Step 3: Create config/classification_rules.yaml**

```yaml
# config/classification_rules.yaml
# Tune patterns here — no code changes needed.
# local rules are checked first; cloud second; no match = ambiguous (fail-safe → LOCAL)

local:
  - pattern: "\\b(reset|change|rotate|expire|update)\\b.{0,40}\\b(password|credential|cert|certificate|secret|api[_\\s]?key)\\b"
    description: "Credential management"
  - pattern: "\\b(ssh|sftp|scp|remote exec(ution)?)\\b"
    description: "SSH / remote access"
  - pattern: "\\b(backup|restore|snapshot)\\b.{0,30}\\b(job|run|trigger|start|server|volume|db|database|disk)\\b"
    description: "Backup operations"
  - pattern: "\\b(provision|deprovision|create|disable|enable|unlock|add|remove)\\b.{0,40}\\b(user|account|group member)\\b"
    description: "User account management"
  - pattern: "\\b(ad|ldap|active directory)\\b.{0,40}\\b(password|account|user|group|access)\\b"
    description: "AD/LDAP operations"
  - pattern: "\\baudit log\\b"
    description: "Audit log access"

cloud:
  - pattern: "\\b(how (do|to|can)|what('s| is)|explain|guide|documentation|doc|tutorial|steps|instructions)\\b"
    description: "Knowledge / documentation requests"
  - pattern: "\\b(vpn|wi-fi|wifi|wireless|printer|outlook|email client)\\b.{0,40}\\b(setup|guide|help|issue|problem|error|not working|can't connect|configure)\\b"
    description: "Common self-service IT help"
  - pattern: "\\b(laptop|desktop|computer|device|machine)\\b.{0,40}\\b(can't|cannot|won't|not working|slow|issue|broken|error|freeze|crash)\\b"
    description: "Device troubleshooting (non-exec)"
  - pattern: "\\bonboarding\\b.{0,30}\\b(guide|checklist|process|steps|document|form)\\b"
    description: "Onboarding documentation"
  - pattern: "\\b(ticket status|my ticket|status of my|it request status)\\b"
    description: "Ticket status queries"
  - pattern: "\\bhow do i submit\\b"
    description: "Request submission help"
```

- [ ] **Step 4: Implement src/router/rules.py**

```python
# src/router/rules.py
from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class RuleMatch(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"


class RuleEngine:
    def __init__(
        self,
        local_patterns: list[re.Pattern],
        cloud_patterns: list[re.Pattern],
    ) -> None:
        self._local = local_patterns
        self._cloud = cloud_patterns

    @classmethod
    def from_yaml(cls, path: str) -> "RuleEngine":
        data = yaml.safe_load(Path(path).read_text())
        local_patterns = [
            re.compile(rule["pattern"], re.IGNORECASE)
            for rule in data.get("local", [])
        ]
        cloud_patterns = [
            re.compile(rule["pattern"], re.IGNORECASE)
            for rule in data.get("cloud", [])
        ]
        return cls(local_patterns, cloud_patterns)

    def classify(self, text: str) -> Optional[RuleMatch]:
        """Return LOCAL, CLOUD, or None (ambiguous — caller applies fail-safe)."""
        for pattern in self._local:
            if pattern.search(text):
                return RuleMatch.LOCAL
        for pattern in self._cloud:
            if pattern.search(text):
                return RuleMatch.CLOUD
        return None
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_rules.py -v
```

Expected: 12 passed. If any regex test fails, adjust the matching pattern in `config/classification_rules.yaml` (not in `rules.py`) and re-run until all pass.

- [ ] **Step 6: Commit**

```bash
git add config/classification_rules.yaml src/router/rules.py tests/unit/test_rules.py
git commit -m "feat: keyword rule engine with YAML-driven classification rules"
```

---

### Task 7: Payload scanner

**Files:**
- Create: `src/router/payload_scanner.py`
- Create: `tests/unit/test_payload_scanner.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_payload_scanner.py
import pytest
from src.router.payload_scanner import PayloadScanner, ScanResult


@pytest.fixture
def scanner():
    return PayloadScanner()


def test_clean_text_passes(scanner):
    assert scanner.scan("My laptop can't connect to WiFi") == ScanResult.CLEAN


def test_password_equals_detected(scanner):
    assert scanner.scan("password=abc123") == ScanResult.SENSITIVE


def test_password_json_field_detected(scanner):
    assert scanner.scan('{"password": "hunter2"}') == ScanResult.SENSITIVE


def test_api_key_detected(scanner):
    assert scanner.scan("api_key=sk-abc1234567890") == ScanResult.SENSITIVE


def test_bearer_token_detected(scanner):
    assert scanner.scan("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc.def") == ScanResult.SENSITIVE


def test_private_key_pem_detected(scanner):
    assert scanner.scan("-----BEGIN RSA PRIVATE KEY-----") == ScanResult.SENSITIVE


def test_aws_access_key_detected(scanner):
    assert scanner.scan("AKIAIOSFODNN7EXAMPLE") == ScanResult.SENSITIVE


def test_secret_colon_detected(scanner):
    assert scanner.scan("secret: mysupersecretvalue") == ScanResult.SENSITIVE


def test_empty_string_is_clean(scanner):
    assert scanner.scan("") == ScanResult.CLEAN


def test_normal_it_request_clean(scanner):
    assert scanner.scan("How do I connect to the VPN from home?") == ScanResult.CLEAN
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/unit/test_payload_scanner.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.router.payload_scanner'`

- [ ] **Step 3: Implement src/router/payload_scanner.py**

```python
# src/router/payload_scanner.py
from __future__ import annotations

import re
from enum import Enum


class ScanResult(str, Enum):
    CLEAN = "clean"
    SENSITIVE = "sensitive"


_SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r"password\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r'"password"\s*:\s*"[^"]+"', re.IGNORECASE),
    re.compile(r"api[_\-\s]?key\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"secret\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=.]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"token\s*[=:]\s*[A-Za-z0-9\-_\.]{20,}", re.IGNORECASE),
]


class PayloadScanner:
    def scan(self, text: str) -> ScanResult:
        for pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                return ScanResult.SENSITIVE
        return ScanResult.CLEAN
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_payload_scanner.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/router/payload_scanner.py tests/unit/test_payload_scanner.py
git commit -m "feat: payload scanner — blocks secret patterns before cloud dispatch"
```

---

### Task 8: Classifier (two-pass: rules → spaCy → fail-safe LOCAL)

**Files:**
- Create: `src/router/classifier.py`
- Create: `tests/unit/test_classifier.py`

- [ ] **Step 1: Write the failing tests (CI-blocking golden dataset)**

```python
# tests/unit/test_classifier.py
import pytest
from src.router.classifier import Classifier, ClassificationResult


@pytest.fixture
def classifier():
    return Classifier.from_config("config/classification_rules.yaml")


# ── Golden dataset (CI-blocking) ────────────────────────────────────────────

def test_golden_reset_ad_password(classifier):
    result = classifier.classify("Reset Alice's AD password")
    assert result.route == "local"


def test_golden_backup_job(classifier):
    result = classifier.classify("Run backup job on server-02")
    assert result.route == "local"


def test_golden_ssh(classifier):
    result = classifier.classify("SSH into db-prod and check disk")
    assert result.route == "local"


def test_golden_vpn_guide(classifier):
    result = classifier.classify("What's our VPN setup guide?")
    assert result.route == "cloud"


def test_golden_wifi_issue(classifier):
    result = classifier.classify("My laptop can't connect to WiFi")
    assert result.route == "cloud"


def test_golden_ambiguous_server_logs_is_failsafe_local(classifier):
    """Ambiguous input MUST route LOCAL — security boundary."""
    result = classifier.classify("Check server logs")
    assert result.route == "local"
    assert result.method == "failsafe"


def test_golden_ambiguous_onboarding_is_failsafe_local(classifier):
    result = classifier.classify("Help me with onboarding")
    assert result.route == "local"
    assert result.method == "failsafe"


def test_golden_secret_in_payload_still_local(classifier):
    """Classifier itself doesn't scan; payload scanner handles this upstream."""
    result = classifier.classify("password=abc123 not working")
    # 'password' triggers local credential rule
    assert result.route == "local"


# ── Method tracking ─────────────────────────────────────────────────────────

def test_rule_match_sets_rules_method(classifier):
    result = classifier.classify("SSH into server-01")
    assert result.method == "rules"


def test_failsafe_sets_failsafe_method(classifier):
    result = classifier.classify("what should i do about the thing")
    assert result.method == "failsafe"
    assert result.route == "local"


def test_classification_result_has_confidence(classifier):
    result = classifier.classify("SSH into db-prod")
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/unit/test_classifier.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.router.classifier'`

- [ ] **Step 3: Implement src/router/classifier.py**

```python
# src/router/classifier.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import structlog

from src.router.rules import RuleEngine, RuleMatch

log = structlog.get_logger()

_EXECUTION_VERBS = {"execute", "run", "restart", "stop", "start", "kill", "deploy", "install"}
_INFO_VERBS = {"find", "show", "get", "explain", "describe", "list", "help", "know", "understand"}


@dataclass
class ClassificationResult:
    route: Literal["local", "cloud"]
    method: Literal["rules", "spacy", "failsafe"]
    confidence: float = 1.0


class Classifier:
    def __init__(self, rule_engine: RuleEngine) -> None:
        self._rules = rule_engine
        self._nlp = None  # lazy-loaded on first ambiguous request

    @classmethod
    def from_config(cls, rules_yaml_path: str) -> "Classifier":
        return cls(RuleEngine.from_yaml(rules_yaml_path))

    def classify(self, text: str) -> ClassificationResult:
        # Pass 1: keyword/regex rules — fast and deterministic
        rule_result = self._rules.classify(text)
        if rule_result == RuleMatch.LOCAL:
            log.debug("classifier.local", method="rules", input=text[:80])
            return ClassificationResult(route="local", method="rules", confidence=1.0)
        if rule_result == RuleMatch.CLOUD:
            log.debug("classifier.cloud", method="rules", input=text[:80])
            return ClassificationResult(route="cloud", method="rules", confidence=1.0)

        # Pass 2: spaCy heuristic — only for ambiguous cases
        spacy_route = self._spacy_classify(text)
        if spacy_route is not None:
            log.debug("classifier.spacy", route=spacy_route, input=text[:80])
            return ClassificationResult(route=spacy_route, method="spacy", confidence=0.7)

        # Fail-safe: ambiguous → LOCAL (security boundary — never route unknown to cloud)
        log.info("classifier.failsafe.local", input=text[:80])
        return ClassificationResult(route="local", method="failsafe", confidence=0.5)

    def _spacy_classify(self, text: str) -> Literal["local", "cloud"] | None:
        if self._nlp is None:
            import spacy
            self._nlp = spacy.load("en_core_web_sm")
        doc = self._nlp(text.lower())
        root_lemmas = {token.lemma_ for token in doc if token.dep_ == "ROOT"}
        if root_lemmas & _EXECUTION_VERBS:
            return "local"
        if root_lemmas & _INFO_VERBS:
            return "cloud"
        return None
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_classifier.py -v
```

Expected: 11 passed. If any golden dataset test fails, adjust `config/classification_rules.yaml` patterns only — do not change the classifier logic.

- [ ] **Step 5: Commit**

```bash
git add src/router/classifier.py tests/unit/test_classifier.py
git commit -m "feat: two-pass classifier (rules → spaCy → fail-safe LOCAL)"
```

---

### Task 9: FastAPI router — POST /tasks and GET /tasks/{id}

**Files:**
- Create: `src/router/routes.py`
- Create: `src/router/app.py`
- Create: `tests/unit/test_routes_unit.py`

- [ ] **Step 1: Write the failing unit tests**

```python
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
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/unit/test_routes_unit.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.router.routes'`

- [ ] **Step 3: Implement src/router/routes.py**

```python
# src/router/routes.py
from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.models.task import RouteDecision, TaskRecord, TaskRequest, TaskStatus
from src.router.classifier import Classifier, ClassificationResult
from src.router.payload_scanner import PayloadScanner, ScanResult

log = structlog.get_logger()
router = APIRouter()
scanner = PayloadScanner()

# Set by create_app() at startup
classifier: Classifier | None = None
queues: dict[str, Any] | None = None
session_factory: Any | None = None

# In-memory store; replaced by DB writes in Plan 2
task_store: dict[str, TaskRecord] = {}


class TaskCreateResponse(BaseModel):
    task_id: str
    route: str
    status: str


@router.post("/tasks", status_code=202, response_model=TaskCreateResponse)
async def create_task(request: TaskRequest) -> TaskCreateResponse:
    log.info("task.received", source=request.source, user=request.user_id)

    # Payload scanner runs before classification — any secret match → LOCAL
    if scanner.scan(request.raw_input) == ScanResult.SENSITIVE:
        log.warning("task.scanner.hit.rerouted_local", user=request.user_id)
        classification = ClassificationResult(route="local", method="failsafe")
    else:
        classification = classifier.classify(request.raw_input)

    route = RouteDecision.LOCAL if classification.route == "local" else RouteDecision.CLOUD
    record = TaskRecord(request=request, status=TaskStatus.QUEUED, route=route)
    task_store[str(request.id)] = record

    queue_key = "sensitive" if route == RouteDecision.LOCAL else "cloud"
    # Worker function path — implemented in Plan 2. Tasks will queue here until workers are deployed.
    queues[queue_key].enqueue("src.workers.process_task", record.model_dump_json())

    log.info(
        "task.enqueued",
        task_id=str(request.id),
        route=route.value,
        method=classification.method,
    )
    return TaskCreateResponse(
        task_id=str(request.id),
        route=route.value,
        status=TaskStatus.QUEUED.value,
    )


@router.get("/tasks/{task_id}", response_model=TaskRecord)
async def get_task(task_id: str) -> TaskRecord:
    record = task_store.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return record
```

- [ ] **Step 4: Implement src/router/app.py**

```python
# src/router/app.py
from __future__ import annotations

from fastapi import FastAPI

from src.config import Settings
from src.db.connection import get_engine, get_session_factory
from src.queue.redis_queues import get_queues
from src.router import routes
from src.router.classifier import Classifier
from src.shared.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    configure_logging(settings.log_level)

    engine = get_engine(settings.database_url)
    session_factory = get_session_factory(engine)
    classifier = Classifier.from_config("config/classification_rules.yaml")
    app_queues = get_queues(settings.redis_url)

    routes.classifier = classifier
    routes.queues = app_queues
    routes.session_factory = session_factory

    app = FastAPI(title="IT Automation Router", version="0.1.0")
    app.include_router(routes.router)
    return app


app = create_app()
```

- [ ] **Step 5: Run unit tests**

```bash
pytest tests/unit/test_routes_unit.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add src/router/routes.py src/router/app.py tests/unit/test_routes_unit.py
git commit -m "feat: FastAPI router — POST /tasks and GET /tasks/{id}"
```

---

### Task 10: Full test suite verification

**Files:**
- Modify: `tests/integration/test_router_api.py` (create)

- [ ] **Step 1: Write integration tests**

```python
# tests/integration/test_router_api.py
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
```

- [ ] **Step 2: Run integration tests**

```bash
pytest tests/integration/test_router_api.py -v
```

Expected: 8 passed.

- [ ] **Step 3: Run the full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: all tests pass. If any golden dataset classifier test fails, update `config/classification_rules.yaml` only.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_router_api.py
git commit -m "test: integration tests — end-to-end task routing coverage"
```

---

## Summary

| Task | Deliverable | Tests |
|------|-------------|-------|
| 1 | Project scaffold (pyproject.toml, Docker Compose, Dockerfile) | — |
| 2 | Config (pydantic-settings) + structlog | 3 unit |
| 3 | TaskRequest / TaskRecord Pydantic models | 6 unit |
| 4 | PostgreSQL schema + async SQLAlchemy connection | 2 unit |
| 5 | Redis RQ queue setup (sensitive-queue, cloud-queue) | 3 unit |
| 6 | Keyword rule engine (YAML-driven) | 12 unit |
| 7 | Payload scanner (secret pattern detection) | 10 unit |
| 8 | Two-pass Classifier (rules → spaCy → fail-safe LOCAL) | 11 unit |
| 9 | FastAPI router: POST /tasks, GET /tasks/{id} | 6 unit |
| 10 | Integration tests: full routing coverage | 8 integration |

**Next:** Plan 2 — Local AI Worker (Gemma 4/Ollama) + execution agents (Vault, SSH, Backup, AD/LDAP)
