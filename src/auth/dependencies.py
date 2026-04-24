# src/auth/dependencies.py
from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from src.auth.tokens import CurrentUser, Role, verify_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_secret: str | None = None
_redis = None


def set_auth_config(secret: str, redis) -> None:
    global _secret, _redis
    _secret = secret
    _redis = redis


def _get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    if _secret is None or _redis is None:
        raise RuntimeError("Auth not initialized — call set_auth_config() in app factory")
    try:
        return verify_token(token, _secret, _redis)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


def require_role(minimum: Role):
    def _check(user: CurrentUser = Depends(_get_current_user)) -> CurrentUser:
        if user.role < minimum:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return Depends(_check)
