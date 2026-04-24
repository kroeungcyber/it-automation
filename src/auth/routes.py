# src/auth/routes.py
from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.auth import dependencies as deps
from src.auth.models import UserORM
from src.auth.password import verify_password
from src.auth.tokens import CurrentUser, Role, issue_token, revoke_token

log = structlog.get_logger()
router = APIRouter(prefix="/auth")

# Injected by app factory
_session_factory = None
_redis = None
_secret: str | None = None
_expiry_seconds: int = 28800


def set_auth_singletons(session_factory, redis, secret: str, expiry_seconds: int) -> None:
    global _session_factory, _redis, _secret, _expiry_seconds
    _session_factory = session_factory
    _redis = redis
    _secret = secret
    _expiry_seconds = expiry_seconds


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    with _session_factory() as session:
        user = session.query(UserORM).filter_by(username=body.username, is_active=True).first()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = issue_token(
        str(user.id), user.username, Role[user.role.upper()], _secret, _expiry_seconds
    )
    log.info("auth.login", username=body.username, role=user.role)
    return TokenResponse(access_token=token, expires_in=_expiry_seconds)


@router.post("/logout", status_code=204)
def logout(current_user: CurrentUser = deps.require_role(Role.EMPLOYEE)) -> None:
    revoke_token(current_user.jti, current_user.exp, _redis)
    log.info("auth.logout", username=current_user.username)


@router.get("/me")
def me(current_user: CurrentUser = deps.require_role(Role.EMPLOYEE)) -> dict:
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "role": current_user.role.name.lower(),
    }
