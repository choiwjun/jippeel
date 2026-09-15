"""LAN 인증 라우터 — 로그인/로그아웃/세션 상태."""
from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.services.lan_auth import (
    authenticate, clear_session_cookie, load_config, set_session_cookie,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


@router.get("/status")
def auth_status() -> dict:
    config = load_config()
    return {"enabled": config.enabled, "configured": bool(config.password_hash)}


@router.post("/login")
def login(payload: LoginRequest, response: Response) -> dict:
    config = load_config()
    if not config.enabled:
        return {"enabled": False}
    token = authenticate(config, payload.password)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid password",
        )
    set_session_cookie(response, config, token)
    return {"enabled": True, "authenticated": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    clear_session_cookie(response)
    return {"ok": True}
