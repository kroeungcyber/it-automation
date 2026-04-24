# tests/unit/test_auth_tokens.py
import time
import pytest
from unittest.mock import MagicMock
from src.auth.tokens import CurrentUser, Role, issue_token, revoke_token, verify_token

SECRET = "test-secret-key-for-unit-tests"


def _redis(revoked: bool = False) -> MagicMock:
    mock = MagicMock()
    mock.exists.return_value = 1 if revoked else 0
    return mock


def test_issue_and_verify_returns_correct_user():
    token = issue_token("U1", "alice", Role.IT_ADMIN, SECRET, expiry_seconds=3600)
    user = verify_token(token, SECRET, _redis())
    assert user.user_id == "U1"
    assert user.username == "alice"
    assert user.role == Role.IT_ADMIN


def test_verify_populates_jti_and_exp():
    token = issue_token("U1", "alice", Role.EMPLOYEE, SECRET, expiry_seconds=3600)
    user = verify_token(token, SECRET, _redis())
    assert user.jti != ""
    assert user.exp > int(time.time())


def test_expired_token_raises():
    token = issue_token("U1", "alice", Role.EMPLOYEE, SECRET, expiry_seconds=-1)
    with pytest.raises(ValueError, match="expired"):
        verify_token(token, SECRET, _redis())


def test_tampered_token_raises():
    token = issue_token("U1", "alice", Role.EMPLOYEE, SECRET, expiry_seconds=3600)
    with pytest.raises(ValueError, match="Invalid"):
        verify_token(token + "x", SECRET, _redis())


def test_wrong_secret_raises():
    token = issue_token("U1", "alice", Role.EMPLOYEE, SECRET, expiry_seconds=3600)
    with pytest.raises(ValueError, match="Invalid"):
        verify_token(token, "completely-wrong-secret", _redis())


def test_revoked_token_raises():
    token = issue_token("U1", "alice", Role.EMPLOYEE, SECRET, expiry_seconds=3600)
    with pytest.raises(ValueError, match="revoked"):
        verify_token(token, SECRET, _redis(revoked=True))


def test_revoke_sets_redis_key_with_positive_ttl():
    redis = MagicMock()
    exp = int(time.time()) + 3600
    revoke_token("some-jti", exp, redis)
    redis.setex.assert_called_once()
    key, ttl, value = redis.setex.call_args[0]
    assert "some-jti" in key
    assert ttl > 0


def test_role_hierarchy_ordering():
    assert Role.EMPLOYEE < Role.IT_ADMIN < Role.SUPER_ADMIN
