# src/auth/tokens.py
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from enum import IntEnum

import jwt
from redis import Redis

_ALGORITHM = "HS256"
_REVOCATION_PREFIX = "guardrail:revoked:"


class Role(IntEnum):
    EMPLOYEE = 1
    IT_ADMIN = 2
    SUPER_ADMIN = 3


@dataclass
class CurrentUser:
    user_id: str
    username: str
    role: Role
    jti: str
    exp: int


def issue_token(
    user_id: str,
    username: str,
    role: Role,
    secret: str,
    expiry_seconds: int,
) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "username": username,
        "role": role.value,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + expiry_seconds,
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def verify_token(token: str, secret: str, redis: Redis) -> CurrentUser:
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")

    jti = payload["jti"]
    if redis.exists(f"{_REVOCATION_PREFIX}{jti}"):
        raise ValueError("Token revoked")

    return CurrentUser(
        user_id=payload["sub"],
        username=payload["username"],
        role=Role(payload["role"]),
        jti=jti,
        exp=payload["exp"],
    )


def revoke_token(jti: str, exp: int, redis: Redis) -> None:
    ttl = exp - int(time.time())
    if ttl > 0:
        redis.setex(f"{_REVOCATION_PREFIX}{jti}", ttl, "1")
