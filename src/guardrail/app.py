# src/guardrail/app.py
from __future__ import annotations

import structlog
from fastapi import FastAPI
from redis import Redis

from src.auth import dependencies as auth_deps
from src.auth import routes as auth_routes
from src.config import Settings
from src.db.connection import get_engine, get_session_factory, get_sync_engine, get_sync_session_factory
from src.guardrail import routes as guardrail_routes
from src.guardrail.approval_gate import ApprovalGate
from src.guardrail.audit import GuardRailAuditLogger
from src.guardrail.circuit_breaker import CircuitBreaker
from src.guardrail.dry_run import DryRunExecutor
from src.guardrail.pipeline import EnforcementPipeline
from src.guardrail.reversibility import ReversibilityChecker
from src.guardrail.risk_classifier import RiskClassifier
from src.shared.logging import configure_logging

log = structlog.get_logger()


def _noop_notify(plan, preview, is_reversible) -> None:
    log.warning(
        "guardrail.approval.notify",
        plan_id=str(plan.id),
        would_affect=preview.would_affect,
        is_reversible=is_reversible,
        message="Approval notification — configure GUARDRAIL_APPROVAL_CHANNEL to send real notifications",
    )


def build_pipeline(
    settings: Settings,
    redis: Redis,
    approval_gate: ApprovalGate,
    circuit_breaker: CircuitBreaker,
    db_write_fn=None,
) -> EnforcementPipeline:
    classifier = RiskClassifier.from_yaml("config/guardrail_rules.yaml")
    dry_run_executor = DryRunExecutor(agents={})
    reversibility_checker = ReversibilityChecker()
    audit_logger = GuardRailAuditLogger(db_write_fn=db_write_fn)
    return EnforcementPipeline(
        risk_classifier=classifier,
        dry_run_executor=dry_run_executor,
        reversibility_checker=reversibility_checker,
        approval_gate=approval_gate,
        circuit_breaker=circuit_breaker,
        audit_logger=audit_logger,
        agents={},
        notify_fn=_noop_notify,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    configure_logging(settings.log_level)

    engine = get_engine(settings.database_url)
    get_session_factory(engine)  # side-effect: registers global session factory

    sync_engine = get_sync_engine(settings.database_url)
    sync_session_factory = get_sync_session_factory(sync_engine)

    redis = Redis.from_url(settings.redis_url)

    approval_gate = ApprovalGate(redis)
    circuit_breaker = CircuitBreaker(redis)

    from src.guardrail.audit_orm import make_db_write_fn
    db_write_fn = make_db_write_fn(sync_session_factory)

    pipeline = build_pipeline(settings, redis, approval_gate, circuit_breaker, db_write_fn=db_write_fn)

    guardrail_routes._pipeline = pipeline
    guardrail_routes._approval_gate = approval_gate
    guardrail_routes._circuit_breaker = circuit_breaker

    auth_deps.set_auth_config(settings.jwt_secret, redis)
    auth_routes.set_auth_singletons(
        sync_session_factory, redis, settings.jwt_secret, settings.jwt_expiry_seconds
    )

    from src.guardrail import audit_read_routes
    audit_read_routes.set_session_factory(sync_session_factory)

    app = FastAPI(title="GuardRail Gate", version="0.1.0")
    app.include_router(auth_routes.router)
    app.include_router(guardrail_routes.router)
    app.include_router(audit_read_routes.router)
    return app
# NO module-level app = create_app() — would run before test patches
