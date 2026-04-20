from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    SSH_EXEC = "ssh_exec"
    VAULT_READ = "vault_read"
    VAULT_WRITE = "vault_write"
    BACKUP_TRIGGER = "backup_trigger"
    AD_PROVISION = "ad_provision"
    AD_DEPROVISION = "ad_deprovision"
    LDAP_MODIFY = "ldap_modify"


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, RiskTier):
            raise TypeError(
                f"'<' not supported between instances of 'RiskTier' and '{type(other).__name__}'"
            )
        return _TIER_ORDER[self] < _TIER_ORDER[other]

    def __le__(self, other: object) -> bool:
        if not isinstance(other, RiskTier):
            raise TypeError(
                f"'<=' not supported between instances of 'RiskTier' and '{type(other).__name__}'"
            )
        return _TIER_ORDER[self] <= _TIER_ORDER[other]

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, RiskTier):
            raise TypeError(
                f"'>' not supported between instances of 'RiskTier' and '{type(other).__name__}'"
            )
        return _TIER_ORDER[self] > _TIER_ORDER[other]

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, RiskTier):
            raise TypeError(
                f"'>=' not supported between instances of 'RiskTier' and '{type(other).__name__}'"
            )
        return _TIER_ORDER[self] >= _TIER_ORDER[other]


_TIER_ORDER: dict[RiskTier, int] = {RiskTier.LOW: 0, RiskTier.MEDIUM: 1, RiskTier.HIGH: 2}


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"
    PENDING = "pending"


class AuditEventType(str, Enum):
    CLASSIFY = "classify"
    DRYRUN = "dryrun"
    APPROVE = "approve"
    DENY = "deny"
    EXECUTE = "execute"
    ROLLBACK = "rollback"
    ESCALATE = "escalate"
    CIRCUIT_TRIP = "circuit_trip"
    TIMEOUT = "timeout"
    CANCEL = "cancel"


class ActionTarget(BaseModel):
    host: str = ""
    scope: Literal["single", "bulk"] = "single"
    count: int = Field(default=1, ge=1)


class ActionRequester(BaseModel):
    user_id: str
    org_role: str
    task_source: str


class ActionPlan(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    task_id: uuid.UUID
    action_type: ActionType
    target: ActionTarget = Field(default_factory=ActionTarget)
    parameters: dict[str, Any] = Field(default_factory=dict)
    ai_self_assessment: RiskTier = RiskTier.LOW  # hint only — gate never trusts this
    requested_by: ActionRequester
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DryRunPreview:
    action_plan_id: str
    agent: str
    would_affect: list[str]
    estimated_reversible: bool
    raw_preview: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PipelineResult:
    action_plan_id: str
    outcome: Literal["success", "failure", "cancelled", "timeout", "denied", "circuit_open"]
    risk_tier: RiskTier
    is_reversible: bool
    dry_run_preview: DryRunPreview | None = None
    execution_result: dict[str, Any] | None = None
    error: str | None = None
    rollback_success: bool | None = None
