# src/guardrail/audit_read_routes.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException

from src.auth.dependencies import require_role
from src.auth.tokens import CurrentUser, Role
from src.guardrail.audit_orm import AuditRecordORM

log = structlog.get_logger()
router = APIRouter(prefix="/audit")

_session_factory = None


def set_session_factory(factory) -> None:
    global _session_factory
    _session_factory = factory


@router.get("/log", status_code=200)
def get_audit_log(
    action_plan_id: Optional[str] = None,
    before: Optional[str] = None,
    limit: int = 100,
    _: CurrentUser = require_role(Role.SUPER_ADMIN),
) -> dict:
    if limit > 500:
        raise HTTPException(status_code=400, detail="limit cannot exceed 500")

    with _session_factory() as session:
        query = session.query(AuditRecordORM).order_by(AuditRecordORM.created_at.desc())

        if action_plan_id:
            query = query.filter(AuditRecordORM.action_plan_id == action_plan_id)

        if before:
            try:
                before_dt = datetime.fromisoformat(before)
            except ValueError:
                raise HTTPException(status_code=400, detail="before must be ISO8601 datetime")
            query = query.filter(AuditRecordORM.created_at < before_dt)

        rows = query.limit(limit).all()

    records = [
        {
            "id": str(r.id),
            "prev_id": str(r.prev_id) if r.prev_id else None,
            "action_plan_id": r.action_plan_id,
            "task_id": r.task_id,
            "event_type": r.event_type,
            "risk_tier": r.risk_tier,
            "actor": r.actor,
            "outcome": r.outcome,
            "detail": r.detail,
            "content_hash": r.content_hash,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]

    next_before = records[-1]["created_at"] if len(records) == limit else None

    return {"records": records, "total": len(records), "next_before": next_before}
