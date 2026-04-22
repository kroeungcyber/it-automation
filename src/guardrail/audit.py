from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import structlog

from src.guardrail.models import AuditEventType, RiskTier

log = structlog.get_logger()


@dataclass
class AuditRecord:
    id: str
    prev_id: Optional[str]
    action_plan_id: str
    task_id: str
    event_type: AuditEventType
    risk_tier: Optional[RiskTier]
    actor: str
    outcome: Optional[str]
    detail: dict[str, Any]
    content_hash: str
    prev_hash: str  # used during hash computation, not stored in DB
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def compute_hash(record: AuditRecord) -> str:
    content = json.dumps(
        {
            "prev_hash": record.prev_hash,
            "id": record.id,
            "action_plan_id": record.action_plan_id,
            "task_id": record.task_id,
            "event_type": record.event_type.value,
            "outcome": record.outcome,
            "detail": record.detail,
            "created_at": record.created_at.isoformat(),
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


class GuardRailAuditLogger:
    def __init__(self, db_write_fn: Optional[Callable[[AuditRecord], None]]) -> None:
        self._db_write_fn = db_write_fn
        self._last_id: Optional[str] = None
        self._last_hash: str = "0" * 64  # genesis hash

    def log(
        self,
        action_plan_id: str,
        task_id: str,
        event_type: AuditEventType,
        risk_tier: Optional[RiskTier] = None,
        actor: str = "system",
        outcome: Optional[str] = None,
        detail: Optional[dict[str, Any]] = None,
    ) -> AuditRecord:
        record = AuditRecord(
            id=str(uuid.uuid4()),
            prev_id=self._last_id,
            action_plan_id=action_plan_id,
            task_id=task_id,
            event_type=event_type,
            risk_tier=risk_tier,
            actor=actor,
            outcome=outcome,
            detail=detail or {},
            content_hash="",
            prev_hash=self._last_hash,
        )
        record.content_hash = compute_hash(record)
        self._last_id = record.id
        self._last_hash = record.content_hash

        log.info(
            "guardrail.audit",
            event_type=event_type.value,
            action_plan_id=action_plan_id,
            outcome=outcome,
            hash=record.content_hash[:12],
        )
        if self._db_write_fn is not None:
            self._db_write_fn(record)
        return record
