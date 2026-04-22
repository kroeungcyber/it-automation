from __future__ import annotations
import structlog
from fastapi import FastAPI
from redis import Redis
from src.config import Settings
from src.db.connection import get_engine, get_session_factory
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


def build_pipeline(settings: Settings, redis: Redis) -> EnforcementPipeline:
    classifier = RiskClassifier.from_yaml("config/guardrail_rules.yaml")
    dry_run_executor = DryRunExecutor(agents={})
    reversibility_checker = ReversibilityChecker()
    approval_gate = ApprovalGate(redis)
    circuit_breaker = CircuitBreaker(redis)
    audit_logger = GuardRailAuditLogger(db_write_fn=None)
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
    get_session_factory(engine)
    redis = Redis.from_url(settings.redis_url)
    pipeline = build_pipeline(settings, redis)
    approval_gate = ApprovalGate(redis)
    circuit_breaker = CircuitBreaker(redis)
    guardrail_routes._pipeline = pipeline
    guardrail_routes._approval_gate = approval_gate
    guardrail_routes._circuit_breaker = circuit_breaker
    app = FastAPI(title="GuardRail Gate", version="0.1.0")
    app.include_router(guardrail_routes.router)
    return app
# NO module-level app = create_app() — would run before test patches
