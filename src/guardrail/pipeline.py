from __future__ import annotations

import structlog
from typing import Callable

from src.guardrail.approval_gate import ApprovalGate
from src.guardrail.audit import GuardRailAuditLogger
from src.guardrail.circuit_breaker import CircuitBreaker
from src.guardrail.dry_run import DryRunExecutor, ExecutionAgent
from src.guardrail.models import (
    ActionPlan, ApprovalDecision, AuditEventType, DryRunPreview,
    PipelineResult, RiskTier,
)
from src.guardrail.reversibility import ReversibilityChecker
from src.guardrail.risk_classifier import RiskClassifier

log = structlog.get_logger()


class EnforcementPipeline:
    def __init__(
        self,
        risk_classifier: RiskClassifier,
        dry_run_executor: DryRunExecutor,
        reversibility_checker: ReversibilityChecker,
        approval_gate: ApprovalGate,
        circuit_breaker: CircuitBreaker,
        audit_logger: GuardRailAuditLogger,
        agents: dict[str, ExecutionAgent],
        notify_fn: Callable,
    ) -> None:
        self._classifier = risk_classifier
        self._dry_run_executor = dry_run_executor
        self._reversibility_checker = reversibility_checker
        self._approval_gate = approval_gate
        self._circuit_breaker = circuit_breaker
        self._audit_logger = audit_logger
        self._agents = agents
        self._notify_fn = notify_fn

    def run(self, plan: ActionPlan) -> PipelineResult:
        plan_id = str(plan.id)
        task_id = str(plan.task_id)
        agent_type = plan.action_type.value

        # ① Circuit breaker check
        if self._circuit_breaker.is_open(agent_type):
            self._audit_logger.log(
                action_plan_id=plan_id, task_id=task_id,
                event_type=AuditEventType.CIRCUIT_TRIP, actor="system",
                outcome="circuit_open",
                detail={"agent_type": agent_type, "state": self._circuit_breaker.get_state(agent_type).state.value},
            )
            log.warning("guardrail.circuit_open", agent_type=agent_type)
            return PipelineResult(
                action_plan_id=plan_id, outcome="circuit_open",
                risk_tier=RiskTier.HIGH, is_reversible=False,
            )

        # ② Risk classification
        classification = self._classifier.classify(plan)
        self._audit_logger.log(
            action_plan_id=plan_id, task_id=task_id,
            event_type=AuditEventType.CLASSIFY, risk_tier=classification.tier,
            actor="system", outcome="classified",
            detail={"method": classification.method, "reason": classification.reason,
                    "ai_self_assessment": plan.ai_self_assessment.value},
        )

        # ③ Dry-run for MEDIUM and HIGH
        preview: DryRunPreview | None = None
        if classification.tier in (RiskTier.MEDIUM, RiskTier.HIGH):
            preview = self._dry_run_executor.run(plan)
            self._audit_logger.log(
                action_plan_id=plan_id, task_id=task_id,
                event_type=AuditEventType.DRYRUN, risk_tier=classification.tier,
                actor="system", outcome="preview_generated",
                detail={"would_affect": preview.would_affect, "raw_preview": preview.raw_preview},
            )

        # ④ Reversibility check (before execution)
        is_reversible = self._reversibility_checker.is_reversible(
            plan, preview or _null_preview(plan_id, agent_type)
        )

        # ⑤ Approval gate for HIGH risk
        if classification.tier == RiskTier.HIGH:
            assert preview is not None
            self._approval_gate.request_approval(
                plan, preview, is_reversible, self._notify_fn
            )
            decision = self._approval_gate.poll(plan)

            if decision == ApprovalDecision.APPROVED:
                self._audit_logger.log(
                    action_plan_id=plan_id, task_id=task_id,
                    event_type=AuditEventType.APPROVE, risk_tier=classification.tier,
                    actor="admin", outcome="approved", detail={},
                )
            elif decision == ApprovalDecision.DENIED:
                self._audit_logger.log(
                    action_plan_id=plan_id, task_id=task_id,
                    event_type=AuditEventType.DENY, risk_tier=classification.tier,
                    actor="admin", outcome="denied", detail={},
                )
                return PipelineResult(
                    action_plan_id=plan_id, outcome="denied",
                    risk_tier=classification.tier, is_reversible=is_reversible,
                    dry_run_preview=preview,
                )
            else:  # TIMEOUT
                self._audit_logger.log(
                    action_plan_id=plan_id, task_id=task_id,
                    event_type=AuditEventType.TIMEOUT, risk_tier=classification.tier,
                    actor="system", outcome="timeout", detail={},
                )
                return PipelineResult(
                    action_plan_id=plan_id, outcome="timeout",
                    risk_tier=classification.tier, is_reversible=is_reversible,
                    dry_run_preview=preview,
                )

        # ⑥ Execute
        agent = self._agents.get(agent_type)
        try:
            execution_result = agent.execute(plan) if agent else {}
            self._circuit_breaker.record_success(agent_type)
            self._audit_logger.log(
                action_plan_id=plan_id, task_id=task_id,
                event_type=AuditEventType.EXECUTE, risk_tier=classification.tier,
                actor="system", outcome="success",
                detail={"result": execution_result},
            )
            return PipelineResult(
                action_plan_id=plan_id, outcome="success",
                risk_tier=classification.tier, is_reversible=is_reversible,
                dry_run_preview=preview, execution_result=execution_result,
            )
        except Exception as exc:
            self._circuit_breaker.record_failure(agent_type)
            error_msg = str(exc)

            if is_reversible and agent:
                rollback_ok = self._rollback(plan, agent, plan_id, task_id, classification.tier, error_msg)
                return PipelineResult(
                    action_plan_id=plan_id, outcome="failure",
                    risk_tier=classification.tier, is_reversible=True,
                    dry_run_preview=preview, error=error_msg,
                    rollback_success=rollback_ok,
                )
            else:
                self._escalate(plan_id, task_id, classification.tier, error_msg)
                return PipelineResult(
                    action_plan_id=plan_id, outcome="failure",
                    risk_tier=classification.tier, is_reversible=False,
                    dry_run_preview=preview, error=error_msg,
                    rollback_success=None,
                )

    def _rollback(self, plan: ActionPlan, agent: ExecutionAgent, plan_id, task_id, tier, error_msg) -> bool:
        try:
            success = agent.rollback(plan_id)
            self._audit_logger.log(
                action_plan_id=plan_id, task_id=task_id,
                event_type=AuditEventType.ROLLBACK, risk_tier=tier,
                actor="system", outcome="success" if success else "failure",
                detail={"original_error": error_msg, "rollback_succeeded": success},
            )
            return success
        except Exception as rb_exc:
            self._audit_logger.log(
                action_plan_id=plan_id, task_id=task_id,
                event_type=AuditEventType.ROLLBACK, risk_tier=tier,
                actor="system", outcome="failure",
                detail={"original_error": error_msg, "rollback_error": str(rb_exc)},
            )
            return False

    def _escalate(self, plan_id, task_id, tier, error_msg) -> None:
        self._audit_logger.log(
            action_plan_id=plan_id, task_id=task_id,
            event_type=AuditEventType.ESCALATE, risk_tier=tier,
            actor="system", outcome="escalated",
            detail={"error": error_msg, "reason": "irreversible_failure"},
        )
        log.error("guardrail.escalate", plan_id=plan_id, error=error_msg)


def _null_preview(action_plan_id: str, agent: str) -> DryRunPreview:
    return DryRunPreview(
        action_plan_id=action_plan_id, agent=agent,
        would_affect=[], estimated_reversible=True, raw_preview="",
    )
