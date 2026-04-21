from __future__ import annotations

import json
from dataclasses import dataclass

from redis import Redis

from src.guardrail.models import ActionType, CircuitState

FAILURE_THRESHOLD = 3
WINDOW_SECONDS = 600  # 10 minutes
_KEY_PREFIX = "guardrail:circuit:"


@dataclass
class CircuitStatus:
    state: CircuitState
    failure_count: int
    agent_type: str


class CircuitBreaker:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def get_state(self, agent_type: str) -> CircuitStatus:
        raw = self._redis.get(f"{_KEY_PREFIX}{agent_type}")
        if raw is None:
            return CircuitStatus(state=CircuitState.CLOSED, failure_count=0, agent_type=agent_type)
        data = json.loads(raw)
        return CircuitStatus(
            state=CircuitState(data["state"]),
            failure_count=data["failure_count"],
            agent_type=agent_type,
        )

    def is_open(self, agent_type: str) -> bool:
        state = self.get_state(agent_type).state
        return state in (CircuitState.OPEN, CircuitState.HALF_OPEN)

    def record_failure(self, agent_type: str) -> CircuitStatus:
        key = f"{_KEY_PREFIX}{agent_type}"
        raw = self._redis.get(key)
        data = json.loads(raw) if raw else {"state": CircuitState.CLOSED.value, "failure_count": 0}
        # HALF_OPEN + failure → immediately back to OPEN
        if data["state"] == CircuitState.HALF_OPEN.value:
            data["state"] = CircuitState.OPEN.value
            data["failure_count"] = FAILURE_THRESHOLD
            self._redis.setex(key, WINDOW_SECONDS, json.dumps(data))
            return CircuitStatus(state=CircuitState.OPEN, failure_count=FAILURE_THRESHOLD, agent_type=agent_type)
        data["failure_count"] += 1
        if data["failure_count"] >= FAILURE_THRESHOLD:
            data["state"] = CircuitState.OPEN.value
        self._redis.setex(key, WINDOW_SECONDS, json.dumps(data))
        return CircuitStatus(
            state=CircuitState(data["state"]),
            failure_count=data["failure_count"],
            agent_type=agent_type,
        )

    def record_success(self, agent_type: str) -> CircuitStatus:
        key = f"{_KEY_PREFIX}{agent_type}"
        raw = self._redis.get(key)
        if raw is None:
            return CircuitStatus(state=CircuitState.CLOSED, failure_count=0, agent_type=agent_type)
        data = json.loads(raw)
        if data["state"] == CircuitState.HALF_OPEN.value:
            self._redis.delete(key)
            return CircuitStatus(state=CircuitState.CLOSED, failure_count=0, agent_type=agent_type)
        return CircuitStatus(
            state=CircuitState(data["state"]),
            failure_count=data["failure_count"],
            agent_type=agent_type,
        )

    def reset(self, agent_type: str) -> None:
        key = f"{_KEY_PREFIX}{agent_type}"
        raw = self._redis.get(key)
        data = json.loads(raw) if raw else {"state": CircuitState.OPEN.value, "failure_count": FAILURE_THRESHOLD}
        data["state"] = CircuitState.HALF_OPEN.value
        data["failure_count"] = 0
        self._redis.setex(key, WINDOW_SECONDS, json.dumps(data))

    def get_all_states(self) -> list[CircuitStatus]:
        return [self.get_state(at.value) for at in ActionType]
