# tests/unit/test_audit_orm.py
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.guardrail.audit import AuditRecord
from src.guardrail.audit_orm import AuditRecordORM, make_db_write_fn
from src.guardrail.models import AuditEventType, RiskTier


def _record() -> AuditRecord:
    return AuditRecord(
        id=str(uuid.uuid4()),
        prev_id=None,
        action_plan_id=str(uuid.uuid4()),
        task_id=str(uuid.uuid4()),
        event_type=AuditEventType.EXECUTE,
        risk_tier=RiskTier.LOW,
        actor="system",
        outcome="success",
        detail={"exit_code": 0},
        content_hash="a" * 64,
        prev_hash="0" * 64,
        created_at=datetime.now(timezone.utc),
    )


def test_from_record_maps_fields():
    rec = _record()
    orm = AuditRecordORM.from_record(rec)
    assert orm.id == uuid.UUID(rec.id)
    assert orm.action_plan_id == rec.action_plan_id
    assert orm.event_type == rec.event_type.value
    assert orm.content_hash == rec.content_hash


def test_from_record_with_prev_id():
    rec = _record()
    prev_id = str(uuid.uuid4())
    rec.prev_id = prev_id
    orm = AuditRecordORM.from_record(rec)
    assert orm.prev_id == uuid.UUID(prev_id)


def test_make_db_write_fn_calls_session():
    mock_session = MagicMock()
    mock_factory = MagicMock()
    mock_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_factory.return_value.__exit__ = MagicMock(return_value=False)

    write_fn = make_db_write_fn(mock_factory)
    write_fn(_record())

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
