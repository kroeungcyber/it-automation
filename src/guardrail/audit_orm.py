# src/guardrail/audit_orm.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.guardrail.audit import AuditRecord


class Base(DeclarativeBase):
    pass


class AuditRecordORM(Base):
    __tablename__ = "guardrail_audit"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    prev_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    action_plan_id: Mapped[str] = mapped_column(Text, nullable=False)
    task_id: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    risk_tier: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    outcome: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    @classmethod
    def from_record(cls, record: AuditRecord) -> "AuditRecordORM":
        return cls(
            id=uuid.UUID(record.id),
            prev_id=uuid.UUID(record.prev_id) if record.prev_id else None,
            action_plan_id=record.action_plan_id,
            task_id=record.task_id,
            event_type=record.event_type.value,
            risk_tier=record.risk_tier.value if record.risk_tier else None,
            actor=record.actor,
            outcome=record.outcome,
            detail=record.detail,
            content_hash=record.content_hash,
            created_at=record.created_at,
        )


def make_db_write_fn(session_factory) -> Callable[[AuditRecord], None]:
    def db_write(record: AuditRecord) -> None:
        with session_factory() as session:
            session.add(AuditRecordORM.from_record(record))
            session.commit()
    return db_write
