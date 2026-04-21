from __future__ import annotations

import json
import time
from typing import Callable

from redis import Redis

from src.guardrail.models import ActionPlan, ApprovalDecision, DryRunPreview

_KEY_PREFIX = "guardrail:approval:"
_POLL_INTERVAL_SECONDS = 5


class ApprovalGate:
    def __init__(self, redis: Redis, approval_window_seconds: int = 1800) -> None:
        self._redis = redis
        self._window = approval_window_seconds

    def request_approval(
        self,
        plan: ActionPlan,
        preview: DryRunPreview,
        is_reversible: bool,
        notify_fn: Callable[[ActionPlan, DryRunPreview, bool], None],
    ) -> None:
        key = f"{_KEY_PREFIX}{plan.id}"
        self._redis.setex(
            key,
            max(self._window, 1),
            json.dumps({"decision": ApprovalDecision.PENDING.value}),
        )
        notify_fn(plan, preview, is_reversible)

    def record_decision(self, action_plan_id: str, decision: ApprovalDecision) -> None:
        key = f"{_KEY_PREFIX}{action_plan_id}"
        self._redis.set(key, json.dumps({"decision": decision.value}))

    def poll(self, plan: ActionPlan) -> ApprovalDecision:
        """Block until decision received or window expires. Returns final decision."""
        key = f"{_KEY_PREFIX}{plan.id}"
        deadline = time.monotonic() + self._window
        while time.monotonic() < deadline:
            raw = self._redis.get(key)
            if raw is None:
                return ApprovalDecision.TIMEOUT
            decision = ApprovalDecision(json.loads(raw)["decision"])
            if decision != ApprovalDecision.PENDING:
                self._redis.delete(key)
                return decision
            time.sleep(_POLL_INTERVAL_SECONDS)
        self._redis.delete(key)
        return ApprovalDecision.TIMEOUT
