from __future__ import annotations
from typing import Any
import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from src.guardrail.approval_gate import ApprovalGate
from src.guardrail.circuit_breaker import CircuitBreaker
from src.guardrail.models import ActionPlan, ApprovalDecision, PipelineResult
from src.guardrail.pipeline import EnforcementPipeline

log = structlog.get_logger()
router = APIRouter(prefix="/guardrail")

# Injected by app factory
_pipeline: EnforcementPipeline | None = None
_approval_gate: ApprovalGate | None = None
_circuit_breaker: CircuitBreaker | None = None


def get_pipeline() -> EnforcementPipeline:
    assert _pipeline is not None
    return _pipeline

def get_approval_gate() -> ApprovalGate:
    assert _approval_gate is not None
    return _approval_gate

def get_circuit_breaker() -> CircuitBreaker:
    assert _circuit_breaker is not None
    return _circuit_breaker


class AuthorizeResponse(BaseModel):
    action_plan_id: str
    outcome: str
    risk_tier: str
    is_reversible: bool
    error: str | None = None
    rollback_success: bool | None = None

class DecisionRequest(BaseModel):
    decision: str  # "approved" | "denied"

class ResetRequest(BaseModel):
    agent_type: str


@router.post("/authorize")
def authorize(plan: ActionPlan) -> Any:
    pipeline = get_pipeline()
    result: PipelineResult = pipeline.run(plan)
    body = AuthorizeResponse(
        action_plan_id=result.action_plan_id,
        outcome=result.outcome,
        risk_tier=result.risk_tier.value,
        is_reversible=result.is_reversible,
        error=result.error,
        rollback_success=result.rollback_success,
    ).model_dump()
    if result.outcome == "circuit_open":
        raise HTTPException(status_code=503, detail=body)
    if result.outcome == "success":
        return JSONResponse(content=body, status_code=202)
    return JSONResponse(content=body, status_code=200)


@router.post("/approvals/{action_plan_id}/decision", status_code=200)
def record_decision(action_plan_id: str, body: DecisionRequest) -> dict:
    gate = get_approval_gate()
    try:
        decision = ApprovalDecision(body.decision)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid decision: {body.decision}. Use 'approved' or 'denied'.")
    gate.record_decision(action_plan_id, decision)
    return {"action_plan_id": action_plan_id, "decision": decision.value}


@router.get("/circuit-breaker/status", status_code=200)
def circuit_breaker_status() -> dict:
    cb = get_circuit_breaker()
    states = cb.get_all_states()
    return {"states": [{"agent_type": s.agent_type, "state": s.state.value, "failure_count": s.failure_count} for s in states]}


@router.post("/circuit-breaker/reset", status_code=200)
def circuit_breaker_reset(body: ResetRequest) -> dict:
    cb = get_circuit_breaker()
    cb.reset(body.agent_type)
    return {"agent_type": body.agent_type, "reset": True}
