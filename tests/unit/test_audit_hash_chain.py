import hashlib
import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.guardrail.models import ActionType, AuditEventType, RiskTier
from src.guardrail.audit import GuardRailAuditLogger, AuditRecord, compute_hash


def _make_record(prev_hash: str = "0" * 64) -> AuditRecord:
    return AuditRecord(
        id=str(uuid.uuid4()),
        prev_id=None,
        action_plan_id=str(uuid.uuid4()),
        task_id=str(uuid.uuid4()),
        event_type=AuditEventType.CLASSIFY,
        risk_tier=RiskTier.LOW,
        actor="system",
        outcome="success",
        detail={"method": "rules"},
        content_hash="",
        prev_hash=prev_hash,
    )


def test_compute_hash_is_deterministic():
    record = _make_record()
    h1 = compute_hash(record)
    h2 = compute_hash(record)
    assert h1 == h2


def test_compute_hash_is_64_hex_chars():
    record = _make_record()
    h = compute_hash(record)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_compute_hash_changes_with_prev_hash():
    record_a = _make_record(prev_hash="a" * 64)
    record_b = _make_record(prev_hash="b" * 64)
    # Use same id/fields for both, only prev_hash differs
    record_b.id = record_a.id
    record_b.action_plan_id = record_a.action_plan_id
    record_b.task_id = record_a.task_id
    assert compute_hash(record_a) != compute_hash(record_b)


def test_tampered_record_hash_mismatch():
    record = _make_record()
    original_hash = compute_hash(record)
    record.outcome = "tampered"
    tampered_hash = compute_hash(record)
    assert original_hash != tampered_hash


def test_audit_logger_appends_entry_with_hash(monkeypatch):
    logger = GuardRailAuditLogger(db_write_fn=None)
    written = []

    def fake_write(record: AuditRecord) -> None:
        written.append(record)

    logger._db_write_fn = fake_write
    logger.log(
        action_plan_id="plan-1",
        task_id="task-1",
        event_type=AuditEventType.EXECUTE,
        risk_tier=RiskTier.LOW,
        actor="system",
        outcome="success",
        detail={"exit_code": 0},
    )
    assert len(written) == 1
    assert len(written[0].content_hash) == 64


def test_audit_logger_links_entries_via_prev_id(monkeypatch):
    logger = GuardRailAuditLogger(db_write_fn=None)
    written: list[AuditRecord] = []
    logger._db_write_fn = written.append

    for _ in range(3):
        logger.log(
            action_plan_id="plan-1",
            task_id="task-1",
            event_type=AuditEventType.CLASSIFY,
            risk_tier=RiskTier.LOW,
            actor="system",
            outcome="success",
            detail={},
        )

    assert written[1].prev_id == written[0].id
    assert written[2].prev_id == written[1].id
