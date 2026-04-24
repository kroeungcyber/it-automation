# tests/integration/test_audit_persistence.py
import os
import uuid
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("LOCAL_MODEL", "gemma3:latest")
os.environ.setdefault("CLOUD_MODEL", "claude-sonnet-4-6")

from src.guardrail.audit import GuardRailAuditLogger
from src.guardrail.audit_orm import AuditRecordORM, make_db_write_fn
from src.guardrail.models import AuditEventType, RiskTier


def _mock_session_factory():
    mock_session = MagicMock()
    mock_factory = MagicMock()
    mock_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_factory.return_value.__exit__ = MagicMock(return_value=False)
    return mock_factory, mock_session


def test_audit_logger_writes_to_db_on_log():
    mock_factory, mock_session = _mock_session_factory()
    write_fn = make_db_write_fn(mock_factory)
    logger = GuardRailAuditLogger(db_write_fn=write_fn)

    logger.log(
        action_plan_id=str(uuid.uuid4()),
        task_id=str(uuid.uuid4()),
        event_type=AuditEventType.EXECUTE,
        risk_tier=RiskTier.LOW,
        actor="system",
        outcome="success",
        detail={"exit_code": 0},
    )

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    orm_record = mock_session.add.call_args[0][0]
    assert isinstance(orm_record, AuditRecordORM)
    assert orm_record.event_type == AuditEventType.EXECUTE.value
    assert orm_record.content_hash != ""


def test_multiple_events_each_write_to_db():
    mock_factory, mock_session = _mock_session_factory()
    write_fn = make_db_write_fn(mock_factory)
    logger = GuardRailAuditLogger(db_write_fn=write_fn)

    for event in [AuditEventType.CLASSIFY, AuditEventType.DRYRUN, AuditEventType.EXECUTE]:
        logger.log(
            action_plan_id=str(uuid.uuid4()),
            task_id=str(uuid.uuid4()),
            event_type=event,
            actor="system",
        )

    assert mock_session.add.call_count == 3
    assert mock_session.commit.call_count == 3


def test_db_write_failure_does_not_corrupt_hash_chain():
    mock_factory, mock_session = _mock_session_factory()
    mock_session.commit.side_effect = [Exception("DB down"), None]
    write_fn = make_db_write_fn(mock_factory)
    logger = GuardRailAuditLogger(db_write_fn=write_fn)

    plan_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())

    try:
        logger.log(action_plan_id=plan_id, task_id=task_id,
                   event_type=AuditEventType.CLASSIFY, actor="system")
    except Exception:
        pass

    # Second log should still have a content_hash (chain continues even if DB write fails)
    record = logger.log(action_plan_id=plan_id, task_id=task_id,
                        event_type=AuditEventType.EXECUTE, actor="system")
    assert len(record.content_hash) == 64
