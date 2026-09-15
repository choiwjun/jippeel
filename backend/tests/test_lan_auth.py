"""LAN 인증·인가 테스트 — JIPPEEL_LAN_AUTH=1 opt-in 계약."""
import json
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.lan_auth import (
    SESSION_COOKIE, _hash_password, issue_session_token, load_config,
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


def test_health_unauthenticated(lan_client):
    """실행 스크립트의 health probe는 인증 없이 동작한다."""
    assert lan_client.get("/health").status_code == 200


def test_api_blocked_without_session(lan_client):
    resp = lan_client.get("/api/v1/projects")
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


def test_status_endpoint_reports_enabled(lan_client):
    resp = lan_client.get("/api/v1/auth/status")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


def test_disabled_by_default(client):
    """기본값(미설정)은 비활성 — localhost 개발이 막히지 않는다."""
    assert client.get("/api/v1/projects").status_code == 200
