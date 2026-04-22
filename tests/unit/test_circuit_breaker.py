import json
import pytest
from unittest.mock import MagicMock
from src.guardrail.circuit_breaker import CircuitBreaker, CircuitStatus, FAILURE_THRESHOLD
from src.guardrail.models import CircuitState


def _make_redis(stored: dict | None = None) -> MagicMock:
    mock = MagicMock()
    mock.get.return_value = json.dumps(stored).encode() if stored else None
    return mock


def test_initial_state_is_closed_when_no_redis_key():
    cb = CircuitBreaker(_make_redis())
    status = cb.get_state("ssh_exec")
    assert status.state == CircuitState.CLOSED
    assert status.failure_count == 0


def test_record_failure_increments_count():
    redis = _make_redis()
    cb = CircuitBreaker(redis)
    status = cb.record_failure("ssh_exec")
    assert status.failure_count == 1
    assert status.state == CircuitState.CLOSED


def test_threshold_failures_open_circuit():
    redis = MagicMock()
    stored = {"state": CircuitState.CLOSED.value, "failure_count": FAILURE_THRESHOLD - 1}
    redis.get.return_value = json.dumps(stored).encode()
    cb = CircuitBreaker(redis)
    status = cb.record_failure("ssh_exec")
    assert status.state == CircuitState.OPEN
    assert status.failure_count == FAILURE_THRESHOLD


def test_is_open_returns_true_when_open():
    redis = _make_redis({"state": CircuitState.OPEN.value, "failure_count": FAILURE_THRESHOLD})
    cb = CircuitBreaker(redis)
    assert cb.is_open("ssh_exec") is True


def test_is_open_returns_true_when_half_open():
    redis = _make_redis({"state": CircuitState.HALF_OPEN.value, "failure_count": 0})
    cb = CircuitBreaker(redis)
    assert cb.is_open("ssh_exec") is True


def test_is_open_returns_false_when_closed():
    cb = CircuitBreaker(_make_redis())
    assert cb.is_open("ssh_exec") is False


def test_reset_transitions_open_to_half_open():
    redis = MagicMock()
    stored = {"state": CircuitState.OPEN.value, "failure_count": FAILURE_THRESHOLD}
    redis.get.return_value = json.dumps(stored).encode()
    cb = CircuitBreaker(redis)
    cb.reset("ssh_exec")
    call_args = redis.setex.call_args
    written = json.loads(call_args[0][2])
    assert written["state"] == CircuitState.HALF_OPEN.value
    assert written["failure_count"] == 0


def test_success_in_half_open_returns_to_closed():
    redis = MagicMock()
    stored = {"state": CircuitState.HALF_OPEN.value, "failure_count": 0}
    redis.get.return_value = json.dumps(stored).encode()
    cb = CircuitBreaker(redis)
    status = cb.record_success("ssh_exec")
    assert status.state == CircuitState.CLOSED
    redis.delete.assert_called_once()


def test_circuit_breaker_is_per_agent_type():
    redis = _make_redis({"state": CircuitState.OPEN.value, "failure_count": FAILURE_THRESHOLD})
    cb = CircuitBreaker(redis)
    assert cb.is_open("ssh_exec") is True
    redis2 = _make_redis(None)
    cb2 = CircuitBreaker(redis2)
    assert cb2.is_open("vault_read") is False


def test_get_all_states_returns_one_per_action_type():
    cb = CircuitBreaker(_make_redis())
    states = cb.get_all_states()
    from src.guardrail.models import ActionType
    assert len(states) == len(ActionType)


def test_failure_in_half_open_reopens_circuit():
    redis = MagicMock()
    stored = {"state": CircuitState.HALF_OPEN.value, "failure_count": 0}
    redis.get.return_value = json.dumps(stored).encode()
    cb = CircuitBreaker(redis)
    status = cb.record_failure("ssh_exec")
    assert status.state == CircuitState.OPEN
    assert status.failure_count == FAILURE_THRESHOLD
