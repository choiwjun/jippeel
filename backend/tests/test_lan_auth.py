"""LAN 인증·인가 테스트 — JIPPEEL_LAN_AUTH=1 opt-in 계약."""
import json
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.lan_auth import (
    SESSION_COOKIE, _hash_password, authenticate, issue_session_token, load_config,
    verify_session_token,
)


@pytest.fixture()
def lan_client(monkeypatch):
    monkeypatch.setenv("JIPPEEL_LAN_AUTH", "1")
    monkeypatch.setenv("JIPPEEL_LAN_PASSWORD", "test-password-123")
    monkeypatch.setenv("JIPPEEL_LAN_SESSION_SECRET", "test-secret-key-for-signing")
    monkeypatch.delenv("JIPPEEL_LAN_ALLOWED_ORIGINS", raising=False)
    with TestClient(app) as c:
        yield c


def test_generated_session_secret_and_password_hash_are_stable(monkeypatch):
    monkeypatch.setenv("JIPPEEL_LAN_AUTH", "1")
    monkeypatch.setenv("JIPPEEL_LAN_PASSWORD", "test-password-123")
    monkeypatch.delenv("JIPPEEL_LAN_SESSION_SECRET", raising=False)
    monkeypatch.delenv("JIPPEEL_LAN_SESSION_SECRET_FILE", raising=False)
    monkeypatch.delenv("JIPPEEL_LAN_PASSWORD_FILE", raising=False)

    first = load_config()
    second = load_config()

    assert first.secret == second.secret
    assert first.password_hash == second.password_hash
    token = authenticate(first, "test-password-123")
    assert token is not None
    assert verify_session_token(first.secret, token)


def test_health_unauthenticated(lan_client):
    """실행 스크립트의 health probe는 인증 없이 동작한다."""
    assert lan_client.get("/health").status_code == 200


def test_api_blocked_without_session(lan_client):
    resp = lan_client.get("/api/v1/projects")
    assert resp.status_code == 401


def test_login_shell_is_loadable_without_session(lan_client):
    resp = lan_client.get("/")
    assert resp.status_code == 200, resp.text
    assert "Jippeel" in resp.text


def test_cors_preflight_is_not_blocked_by_session_auth(lan_client):
    resp = lan_client.options(
        "/api/v1/projects",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_non_get_non_api_requests_remain_protected(lan_client):
    resp = lan_client.post("/unexpected-non-api-path", json={"x": 1})
    assert resp.status_code == 401


def test_login_sets_session_cookie(lan_client):
    resp = lan_client.post("/api/v1/auth/login", json={"password": "test-password-123"})
    assert resp.status_code == 200
    assert SESSION_COOKIE in lan_client.cookies


def test_authenticated_request_succeeds(lan_client):
    lan_client.post("/api/v1/auth/login", json={"password": "test-password-123"})
    resp = lan_client.get("/api/v1/projects")
    assert resp.status_code == 200


def test_wrong_password_rejected(lan_client):
    resp = lan_client.post("/api/v1/auth/login", json={"password": "wrong"})
    assert resp.status_code == 401
    assert SESSION_COOKIE not in lan_client.cookies


def test_logout_clears_session(lan_client):
    lan_client.post("/api/v1/auth/login", json={"password": "test-password-123"})
    lan_client.post("/api/v1/auth/logout")
    assert lan_client.get("/api/v1/projects").status_code == 401


def test_forged_cookie_rejected(lan_client):
    lan_client.cookies.set(SESSION_COOKIE, "forged.token")
    assert lan_client.get("/api/v1/projects").status_code == 401


def test_expired_token_rejected(lan_client):
    token = issue_session_token(b"test-secret-key-for-signing", -1)
    lan_client.cookies.set(SESSION_COOKIE, token)
    assert lan_client.get("/api/v1/projects").status_code == 401


def test_cross_origin_write_blocked(lan_client):
    lan_client.post("/api/v1/auth/login", json={"password": "test-password-123"})
    resp = lan_client.post(
        "/api/v1/projects",
        json={"title": "x"},
        headers={"Origin": "https://evil.example.com"},
    )
    assert resp.status_code == 403


def test_same_origin_referer_with_path_allows_write(lan_client):
    lan_client.post("/api/v1/auth/login", json={"password": "test-password-123"})
    resp = lan_client.post(
        "/api/v1/projects",
        json={"title": "referer project"},
        headers={"Referer": "http://testserver/projects/1/write"},
    )
    assert resp.status_code == 201, resp.text


def test_status_endpoint_reports_enabled(lan_client):
    resp = lan_client.get("/api/v1/auth/status")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


def test_disabled_by_default(client):
    """기본값(미설정)은 비활성 — localhost 개발이 막히지 않는다."""
    assert client.get("/api/v1/projects").status_code == 200
