"""LAN 인증·인가 — 단일 사용자 앱의 로컬 네트워크 노출 보호.

기본값: 비활성(localhost 단독 사용). `JIPPEEL_LAN_AUTH=1`일 때만 세션을 요구한다.
- 비밀번호는 PBKDF2-HMAC-SHA256 해시로만 저장(평문·로그 금지)
- 세션은 서명된 쿠키 + 만료 + SameSite=Lax
- 상태 변경 요청은 Origin/Referer가 동일 origin일 때만 허용(CSRF 방어)
- /health는 인증 없이 유지(실행 스크립트의 health probe 계약)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

_ENV_ENABLE = "JIPPEEL_LAN_AUTH"
_ENV_PASSWORD = "JIPPEEL_LAN_PASSWORD"
_ENV_PASSWORD_FILE = "JIPPEEL_LAN_PASSWORD_FILE"
_ENV_SECRET = "JIPPEEL_LAN_SESSION_SECRET"
_ENV_SECRET_FILE = "JIPPEEL_LAN_SESSION_SECRET_FILE"
_ENV_SECURE_COOKIE = "JIPPEEL_LAN_SECURE_COOKIE"
_ENV_SESSION_TTL = "JIPPEEL_LAN_SESSION_TTL_SECONDS"
_ENV_ALLOWED_ORIGINS = "JIPPEEL_LAN_ALLOWED_ORIGINS"

SESSION_COOKIE = "jippeel_lan_session"
_PBKDF2_ITERATIONS = 120_000
_DEFAULT_TTL_SECONDS = 12 * 60 * 60
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
_generated_session_secret: bytes | None = None
_password_hash_cache: tuple[bytes, str] | None = None


def _default_session_secret() -> bytes:
    global _generated_session_secret
    if _generated_session_secret is None:
        _generated_session_secret = secrets.token_hex(32).encode("utf-8")
    return _generated_session_secret


def _stable_password_hash(password: str) -> str:
    """Keep one salted hash per configured password without retaining plaintext."""
    global _password_hash_cache
    fingerprint = hashlib.sha256(password.encode("utf-8")).digest()
    if _password_hash_cache is not None:
        cached_fingerprint, cached_hash = _password_hash_cache
        if hmac.compare_digest(cached_fingerprint, fingerprint):
            return cached_hash
    hashed = _hash_password(password)
    _password_hash_cache = (fingerprint, hashed)
    return hashed


@dataclass(frozen=True)
class LanAuthConfig:
    enabled: bool
    password_hash: str | None
    secret: bytes | None
    session_ttl_seconds: int = _DEFAULT_TTL_SECONDS
    secure_cookie: bool = False
    allowed_origins: tuple[str, ...] = ()


def _read_secret_file(path: str | None) -> str | None:
    if not path:
        return None
    try:
        value = Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def _hash_password(password: str, *, salt_hex: str | None = None) -> str:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"pbkdf2-sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        _scheme, iterations, salt_hex, digest_hex = stored.split("$", 3)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"),
            bytes.fromhex(salt_hex), int(iterations),
        ).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except (ValueError, AttributeError):
        return False


def load_config() -> LanAuthConfig:
    enabled = os.environ.get(_ENV_ENABLE, "").strip() in {"1", "true", "yes"}
    password = (
        _read_secret_file(os.environ.get(_ENV_PASSWORD_FILE))
        or os.environ.get(_ENV_PASSWORD)
    )
    configured_secret = (
        _read_secret_file(os.environ.get(_ENV_SECRET_FILE))
        or os.environ.get(_ENV_SECRET)
    )
    secret = configured_secret.encode("utf-8") if configured_secret else _default_session_secret()
    allowed = tuple(
        item.strip() for item in os.environ.get(_ENV_ALLOWED_ORIGINS, "").split(",")
        if item.strip()
    )
    try:
        ttl = int(os.environ.get(_ENV_SESSION_TTL, _DEFAULT_TTL_SECONDS))
    except ValueError:
        ttl = _DEFAULT_TTL_SECONDS
    return LanAuthConfig(
        enabled=enabled,
        password_hash=_stable_password_hash(password) if password else None,
        secret=secret,
        session_ttl_seconds=max(ttl, 60),
        secure_cookie=os.environ.get(_ENV_SECURE_COOKIE, "").strip() in {"1", "true", "yes"},
        allowed_origins=allowed,
    )


def _sign(secret: bytes, payload: bytes) -> str:
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def issue_session_token(secret: bytes, ttl_seconds: int) -> str:
    payload = json.dumps(
        {"sub": "owner", "iat": int(time.time()), "exp": int(time.time()) + ttl_seconds},
        separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    return f"{base64.urlsafe_b64encode(payload).decode()}.{_sign(secret, payload)}"


def verify_session_token(secret: bytes, token: str | None) -> bool:
    if not token or "." not in token:
        return False
    encoded, signature = token.rsplit(".", 1)
    try:
        payload = base64.urlsafe_b64decode(encoded.encode())
    except (ValueError, TypeError):
        return False
    if not hmac.compare_digest(_sign(secret, payload), signature):
        return False
    try:
        claims = json.loads(payload)
    except (TypeError, ValueError):
        return False
    exp = claims.get("exp")
    return isinstance(exp, int) and exp > int(time.time())


def _origin_allowed(request: Request, config: LanAuthConfig) -> bool:
    if request.method.upper() in _SAFE_METHODS:
        return True
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return True  # CLI/동일 프로세스 요청은 Origin이 없다
    host = request.headers.get("host", "")
    allowed = {f"{request.url.scheme}://{host}", f"http://{host}", f"https://{host}"}
    allowed.update(config.allowed_origins)
    normalized_origin = origin.rstrip("/")
    if normalized_origin in {item.rstrip("/") for item in allowed}:
        return True
    if request.headers.get("origin") is None:
        parsed = urlparse(origin)
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/") in {
            item.rstrip("/") for item in allowed
        }
    return False


class LanAuthMiddleware(BaseHTTPMiddleware):
    """LAN 인증 미들웨어 — 활성 시 /api·정적 자산을 세션으로 보호한다.

    config는 app 생성 시점의 스냅샷이지만, 요청마다 env를 재확인해
    테스트·운영 재시작 없이도 설정 변경이 반영되도록 한다.
    """

    def __init__(self, app, config: LanAuthConfig):
        super().__init__(app)
        self.config = config

    async def dispatch(self, request: Request, call_next):
        config = load_config()  # 요청 시점 재확인 — 테스트 monkeypatch 호환
        if not config.enabled:
            return await call_next(request)

        path = request.url.path
        # The SPA shell and static assets must load before authentication so
        # LoginGate can render the password form. API routes remain protected.
        if request.method.upper() == "OPTIONS":
            return await call_next(request)
        if (
            path == "/health"
            or path.startswith("/api/v1/auth/")
            or (
                not path.startswith("/api/v1/")
                and request.method.upper() in {"GET", "HEAD"}
            )
        ):
            return await call_next(request)

        if not config.password_hash or not config.secret:
            return JSONResponse(
                status_code=503,
                content={"detail": "LAN auth enabled but password is not configured"},
            )

        if not _origin_allowed(request, config):
            return JSONResponse(status_code=403, content={"detail": "forbidden origin"})

        token = request.cookies.get(SESSION_COOKIE)
        if not verify_session_token(config.secret, token):
            return JSONResponse(status_code=401, content={"detail": "authentication required"})

        return await call_next(request)


def set_session_cookie(response: Response, config: LanAuthConfig, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=config.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=config.secure_cookie,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def authenticate(config: LanAuthConfig, password: str) -> str | None:
    """비밀번호 검증 후 세션 토큰 발급. 실패 시 None."""
    if not config.password_hash or not config.secret:
        return None
    if not _verify_password(password, config.password_hash):
        return None
    return issue_session_token(config.secret, config.session_ttl_seconds)
