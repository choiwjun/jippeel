"""고도화 G-001 — 목차 자동 주입(auto_outline) 테스트.

현재 회차 memo(시놉시스·핵심 사건)와 다음 회차 전개 방향이
AI 컨텍스트 블록으로 주입되는지 검증한다.
"""
import json

from tests.test_ai_generate_stream import (DEFAULT_CHUNKS, FakeAsyncOpenAI,
                                           _parse_sse)


def _setup(monkeypatch, client):
    from app.routers import ai_panel
    spec = {"chunks": list(DEFAULT_CHUNKS), "exc": None}
    holder = {"client": None}

    def _make_client(base_url, api_key_encrypted):
        c = FakeAsyncOpenAI(base_url=base_url, api_key="x", spec=spec)
        holder["client"] = c
        return c

    monkeypatch.setattr(ai_panel.llm, "make_client", _make_client)
    holder["client"] = _make_client("http://x/v1", None)

    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    pid = client.post("/api/v1/projects", json={"title": "p"}).json()["id"]
    ch1 = client.post(f"/api/v1/projects/{pid}/chapters", json={
        "title": "1화", "sort_order": 0}).json()
    client.patch(f"/api/v1/chapters/{ch1['id']}", json={
        "memo": "시놉시스: 흑마법사를 만난다\n[핵심 사건] 각성"})
    ch2 = client.post(f"/api/v1/projects/{pid}/chapters", json={
        "title": "2화", "sort_order": 1}).json()
    client.patch(f"/api/v1/chapters/{ch2['id']}", json={"memo": "시놉시스: 탑에 오른다"})
    client.put(f"/api/v1/chapters/{ch1['id']}/content", json={
        "content_md": "1화 본문", "expected_revision": 0})
    return holder, ep["id"], ch1["id"], ch2["id"], ch2["title"]


def test_auto_outline_injects_memo_and_next_direction(client, monkeypatch):
    holder, endpoint_id, ch1, _ch2_id, ch2_title = _setup(monkeypatch, client)
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": endpoint_id, "prompt_override": "이어서 써줘",
        "context": {"chapter_id": ch1, "auto_outline": True}})
    assert resp.status_code == 200

    user_text = holder["client"].last_kwargs["messages"][-1]["content"]
    assert "[이번 회차 목표(목차)" in user_text
    assert "흑마법사를 만난다" in user_text and "[핵심 사건] 각성" in user_text
    assert f"[다음 회차 예고: {ch2_title}]" in user_text
    assert "탑에 오른다" in user_text


def test_auto_outline_off_by_default(client, monkeypatch):
    holder, endpoint_id, ch1, _ch2_id, _t = _setup(monkeypatch, client)
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": endpoint_id, "prompt_override": "이어서 써줘",
        "context": {"chapter_id": ch1}})
    assert resp.status_code == 200
    user_text = holder["client"].last_kwargs["messages"][-1]["content"]
    assert "[이번 회차 목표(목차)" not in user_text
    assert "[다음 회차 예고:" not in user_text


def test_auto_outline_sse_start_event_reports_injection(client, monkeypatch):
    _holder, endpoint_id, ch1, _ch2_id, ch2_title = _setup(monkeypatch, client)
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": endpoint_id, "prompt_override": "이어서 써줘",
        "context": {"chapter_id": ch1, "auto_outline": True}})
    events = _parse_sse(resp.text)
    data = json.loads(dict(events)["start"])
    assert data["injected_outline"]["current"] is True
    assert data["injected_outline"]["next_title"] == ch2_title


def test_auto_outline_silent_without_memo_and_last_chapter(client, monkeypatch):
    holder, endpoint_id, _ch1, ch2_id, _t = _setup(monkeypatch, client)
    client.patch(f"/api/v1/chapters/{ch2_id}", json={"memo": None})
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": endpoint_id, "prompt_override": "이어서 써줘",
        "context": {"chapter_id": ch2_id, "auto_outline": True}})
    assert resp.status_code == 200
    user_text = holder["client"].last_kwargs["messages"][-1]["content"]
    assert "[이번 회차 목표(목차)" not in user_text
    assert "[다음 회차 예고:" not in user_text
