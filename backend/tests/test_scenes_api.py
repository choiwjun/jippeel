"""고도화 G-010~G-013 — 장면(Scene) CRUD·reorder·AI 주입 테스트."""
import json

import pytest

from tests.test_ai_generate_stream import (DEFAULT_CHUNKS, FakeAsyncOpenAI,
                                           _parse_sse)


@pytest.fixture()
def chapter(client):
    pid = client.post("/api/v1/projects", json={"title": "p"}).json()["id"]
    ch = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화"}).json()
    return ch


def _scene(client, chapter, title, sort_order, content="장면 본문"):
    return client.post(f"/api/v1/chapters/{chapter['id']}/scenes", json={
        "title": title, "sort_order": sort_order, "content_md": content}).json()


def test_scene_crud(client, chapter):
    s1 = _scene(client, chapter, "도입", 0.0)
    s2 = _scene(client, chapter, "전개", 1.0)
    rows = client.get(f"/api/v1/chapters/{chapter['id']}/scenes").json()
    assert [r["title"] for r in rows] == ["도입", "전개"]

    r = client.patch(f"/api/v1/scenes/{s1['id']}",
                     json={"content_md": "수정된 장면", "title": "도입(수정)"})
    assert r.status_code == 200
    assert r.json()["content_md"] == "수정된 장면"

    assert client.get(f"/api/v1/scenes/{s2['id']}").json()["title"] == "전개"
    assert client.delete(f"/api/v1/scenes/{s1['id']}").status_code == 204
    assert client.get(f"/api/v1/scenes/{s1['id']}").status_code == 404


def test_scene_reorder_atomic(client, chapter):
    s1 = _scene(client, chapter, "도입", 0.0)
    s2 = _scene(client, chapter, "전개", 1.0)
    # 정상 reorder
    r = client.patch(f"/api/v1/chapters/{chapter['id']}/scenes/order", json={
        "items": [{"id": s1["id"], "sort_order": 5.0}]})
    assert r.status_code == 200
    by_id = {row["id"]: row["sort_order"] for row in r.json()}
    assert by_id[s1["id"]] == 5.0

    # 중복 id → 422
    r = client.patch(f"/api/v1/chapters/{chapter['id']}/scenes/order", json={
        "items": [{"id": s1["id"], "sort_order": 1.0},
                  {"id": s1["id"], "sort_order": 2.0}]})
    assert r.status_code == 422

    # 존재하지 않는 id → 422 (부분 적용 없음)
    r = client.patch(f"/api/v1/chapters/{chapter['id']}/scenes/order", json={
        "items": [{"id": s1["id"], "sort_order": 0.0}, {"id": 99999}]})
    assert r.status_code == 422
    rows = client.get(f"/api/v1/chapters/{chapter['id']}/scenes").json()
    assert [r2["sort_order"] for r2 in rows if r2["id"] == s1["id"]] == [5.0]



def test_scene_context_injection(client, monkeypatch, chapter):
    from app.routers import ai_panel
    spec = {"chunks": list(DEFAULT_CHUNKS), "exc": None}
    holder = {"client": None}

    def _make_client(base_url, api_key_encrypted):
        holder["client"] = FakeAsyncOpenAI(base_url=base_url, api_key="x", spec=spec)
        return holder["client"]

    monkeypatch.setattr(ai_panel.llm, "make_client", _make_client)
    _make_client("http://x/v1", None)

    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    scene = _scene(client, chapter, "골목 대치", 0.0, "칼끝이 목을 겨눈다.")

    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이 장면을 다듬어줘",
        "context": {"scene_id": scene["id"]}})
    assert resp.status_code == 200
    user_text = holder["client"].last_kwargs["messages"][-1]["content"]
    assert "[현재 장면: 골목 대치" in user_text
    assert "칼끝이 목을 겨눈다." in user_text

    # 존재하지 않는 scene → 404
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "hi",
        "context": {"scene_id": 99999}})
    assert resp.status_code == 404
