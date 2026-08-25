"""AiEndpoint·PromptPreset CRUD API 테스트 (M4, Sprint 3)."""
import httpx
import openai
import pytest

from app.routers import ai_panel


# ---------- AiEndpoint CRUD ----------
def test_create_endpoint_without_key(client):
    resp = client.post("/api/v1/ai/endpoints", json={
        "name": "local-lmstudio",
        "base_url": "http://localhost:1234/v1",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["has_api_key"] is False
    assert body["is_default"] is False
    assert body["temperature"] == 0.7


def test_endpoint_crud_roundtrip(client):
    created = client.post("/api/v1/ai/endpoints", json={
        "name": "cloud-a", "base_url": "https://api.a.com/v1",
        "api_key": "k1", "default_model": "m1",
    }).json()

    listed = client.get("/api/v1/ai/endpoints").json()
    assert [r["name"] for r in listed] == ["cloud-a"]

    patched = client.patch(f"/api/v1/ai/endpoints/{created['id']}", json={
        "temperature": 0.2, "api_key": "k2-new",
    })
    assert patched.status_code == 200
    assert patched.json()["temperature"] == 0.2
    assert patched.json()["has_api_key"] is True  # 재암호화 후에도 플래그 유지

    # api_key를 빈 문자열로 보내면 제거
    cleared = client.patch(f"/api/v1/ai/endpoints/{created['id']}", json={"api_key": ""})
    assert cleared.json()["has_api_key"] is False

    assert client.delete(f"/api/v1/ai/endpoints/{created['id']}").status_code == 204
    assert client.get("/api/v1/ai/endpoints").json() == []


def test_default_flag_exclusive(client):
    a = client.post("/api/v1/ai/endpoints", json={
        "name": "a", "base_url": "http://a/v1", "is_default": True}).json()
    b = client.post("/api/v1/ai/endpoints", json={
        "name": "b", "base_url": "http://b/v1", "is_default": True}).json()
    listed = {r["name"]: r for r in client.get("/api/v1/ai/endpoints").json()}
    assert listed["b"]["is_default"] is True
    assert listed["a"]["is_default"] is False  # 기본값은 하나만(FR-407)


def test_endpoint_404(client):
    assert client.get("/api/v1/ai/endpoints/999/models").status_code == 404


# ---------- PromptPreset CRUD ----------
def test_preset_crud(client):
    created = client.post("/api/v1/ai/presets", json={
        "name": "장면 생성",
        "template_text": "다음 컨텍스트로 장면을 써줘.",
        "context_flags": ["chapter", "characters"],
    }).json()
    assert created["context_flags"] == ["chapter", "characters"]

    updated = client.patch(f"/api/v1/ai/presets/{created['id']}",
                           json={"context_flags": ["lore"]}).json()
    assert updated["context_flags"] == ["lore"]

    assert len(client.get("/api/v1/ai/presets").json()) == 1
    assert client.delete(f"/api/v1/ai/presets/{created['id']}").status_code == 204


def test_preset_invalid_context_flag_rejected(client):
    resp = client.post("/api/v1/ai/presets", json={
        "name": "bad", "template_text": "x", "context_flags": ["nope"]})
    assert resp.status_code == 422


# ---------- models 프록시 ----------
class _FakeModels:
    def __init__(self, ids):
        self.data = [type("M", (), {"id": i})() for i in ids]


class _FakeClientModels:
    def __init__(self, ids):
        self._ids = ids
        self.models = type("NS", (), {"list": lambda self, _ids=ids: _FakeModels(_ids)})()


@pytest.fixture()
def fake_models_client(monkeypatch):
    holder = {}

    def _make_client(base_url, api_key_encrypted):
        holder["called_with"] = (base_url, api_key_encrypted)
        return _FakeClientModels(["m-a", "m-b"])

    monkeypatch.setattr(ai_panel.llm, "make_client", _make_client)
    return holder


def test_models_proxy_masks_key(client, fake_models_client):
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "p", "base_url": "http://p/v1", "api_key": "topsecret"}).json()

    resp = client.get(f"/api/v1/ai/endpoints/{ep['id']}/models")
    assert resp.status_code == 200
    assert [m["id"] for m in resp.json()["data"]] == ["m-a", "m-b"]
    base_url, key_arg = fake_models_client["called_with"]
    assert base_url == "http://p/v1"
    assert key_arg and "topsecret" not in key_arg  # 복호문이 아니라 내부 처리만


def test_generate_requires_endpoint_and_prompt_source(client):
    # 존재하지 않는 엔드포인트
    r = client.post("/api/v1/ai/generate", json={"endpoint_id": 999})
    assert r.status_code == 404
    # preset도 override도 없음 → 400
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "x", "base_url": "http://x/v1"}).json()
    r = client.post("/api/v1/ai/generate", json={"endpoint_id": ep["id"]})
    assert r.status_code == 400
