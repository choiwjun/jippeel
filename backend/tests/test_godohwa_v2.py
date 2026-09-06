"""고도화 v2 테스트 — 권 개요(G-050)·독자 인지(G-045)·문체 프로파일(G-040)
·장면 조립(G-013)·품질 이력(G-041)·AI 사용량(G-060)·복선 추출(G-046)."""
import json

import pytest
from sqlalchemy import select

from app.database import get_db
from app.models import AiUsage, Foreshadow, QualityCheck
from tests.test_ai_generate_stream import (DEFAULT_CHUNKS, FakeAsyncOpenAI,
                                           _parse_sse)
from tests.test_bootstrap_api import _Response


@pytest.fixture()
def project(client):
    return client.post("/api/v1/projects", json={"title": "p"}).json()


@pytest.fixture()
def chapter(client, project):
    ch = client.post(f"/api/v1/projects/{project['id']}/chapters",
                     json={"title": "1화", "sort_order": 0}).json()
    return client.get(f"/api/v1/chapters/{ch['id']}").json()


def _endpoint(client, **kw):
    return client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m",
        "is_default": True, **kw}).json()


# ---------- G-050 권 개요 ----------
def test_volume_note_crud_and_conflict(client, project):
    r = client.post(f"/api/v1/projects/{project['id']}/volume-notes", json={
        "volume": 1, "title": "균열의 시작",
        "overview": "주인공이 각성하고 첫 적을 만난다",
        "emotion_curve": "고조-완충-고조", "climax_note": "낙하협곡 결전"})
    assert r.status_code == 201
    note = r.json()

    # 중복 volume → 422
    assert client.post(f"/api/v1/projects/{project['id']}/volume-notes",
                       json={"volume": 1}).status_code == 422

    r = client.patch(f"/api/v1/volume-notes/{note['id']}",
                     json={"overview": "개요 수정"})
    assert r.status_code == 200 and r.json()["overview"] == "개요 수정"
    assert client.get(f"/api/v1/projects/{project['id']}/volume-notes").json()[0][
        "climax_note"] == "낙하협곡 결전"
    assert client.delete(f"/api/v1/volume-notes/{note['id']}").status_code == 204


def test_auto_outline_includes_volume_note(client, monkeypatch, project):
    from app.routers import ai_panel
    holder = {"client": None}
    spec = {"chunks": list(DEFAULT_CHUNKS), "exc": None}

    def _make_client(base_url, api_key_encrypted):
        holder["client"] = FakeAsyncOpenAI(base_url=base_url, api_key="x", spec=spec)
        return holder["client"]

    monkeypatch.setattr(ai_panel.llm, "make_client", _make_client)
    _make_client("http://x/v1", None)
    ep = _endpoint(client, is_default=False)

    pid = project["id"]
    client.post(f"/api/v1/projects/{pid}/volume-notes", json={
        "volume": 1, "overview": "1권 전체 개요 텍스트"})
    ch = client.post(f"/api/v1/projects/{pid}/chapters", json={
        "title": "1화", "volume": 1, "sort_order": 0}).json()

    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘",
        "context": {"chapter_id": ch["id"], "auto_outline": True}})
    user_text = holder["client"].last_kwargs["messages"][-1]["content"]
    assert "[1권 개요" in user_text and "1권 전체 개요 텍스트" in user_text

    # 권 개요 없는 회차 — 블록 없음
    ch2 = client.post(f"/api/v1/projects/{pid}/chapters", json={
        "title": "2화", "volume": 2, "sort_order": 1}).json()
    client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘",
        "context": {"chapter_id": ch2["id"], "auto_outline": True}})
    user_text = holder["client"].last_kwargs["messages"][-1]["content"]
    assert "권 개요" not in user_text


# ---------- G-045 독자 인지 ----------
def test_foreshadow_audience_knows(client, monkeypatch, chapter):
    pid = chapter["project_id"]
    f = client.post(f"/api/v1/projects/{pid}/foreshadows", json={
        "title": "검의 주인", "audience_knows": False}).json()
    assert f["audience_knows"] is False
    f = client.patch(f"/api/v1/foreshadows/{f['id']}",
                     json={"audience_knows": True}).json()
    assert f["audience_knows"] is True

    # canon-check 컨텍스트 분류 반영
    class _Completions:
        async def create(self, **kwargs):
            return _Response('{"issues": []}')

    from app.routers import quality as quality_router
    class _FakeClient:
        def __init__(self, base_url=None, api_key_encrypted=None):
            self.chat = type("NS", (), {"completions": _Completions()})()

    import app.routers.quality as qr
    monkeypatch.setattr(qr.llm, "make_client",
                        lambda base_url, api_key_encrypted: _FakeClient())
    _endpoint(client)
    client.put(f"/api/v1/chapters/{chapter['id']}/content",
               json={"content_md": "본문"})
    body = client.post("/api/v1/canon-check",
                       json={"chapter_id": chapter["id"]}).json()
    assert body["checked_context"]["audience_known"] == 1


# ---------- G-040 문체 프로파일 ----------
def test_style_profile_in_system_prompt(client, monkeypatch, project):
    from app.routers import ai_panel
    holder = {"client": None}
    spec = {"chunks": list(DEFAULT_CHUNKS), "exc": None}

    def _make_client(base_url, api_key_encrypted):
        holder["client"] = FakeAsyncOpenAI(base_url=base_url, api_key="x", spec=spec)
        return holder["client"]

    monkeypatch.setattr(ai_panel.llm, "make_client", _make_client)
    _make_client("http://x/v1", None)
    ep = _endpoint(client, is_default=False)

    pid = project["id"]
    client.patch(f"/api/v1/projects/{pid}",
                 json={"style_profile": "짧은 단문, 과거 회상 장면은 이탤릭 대신 '[기억]' 프리픽스"})
    ch = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화"}).json()

    client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "써줘",
        "context": {"chapter_id": ch["id"], "style_profile": True}})
    system = holder["client"].last_kwargs["messages"][0]["content"]
    assert "[작품 문체 프로파일" in system and "짧은 단문" in system

    # 플래그 off — 프로파일 미적용
    client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "써줘",
        "context": {"chapter_id": ch["id"], "style_profile": False}})
    system = holder["client"].last_kwargs["messages"][0]["content"]
    assert "작품 문체 프로파일" not in system


# ---------- G-013 장면 → 본문 조립 ----------
def test_merge_scenes_to_content(client, project, chapter):
    cid = chapter["id"]
    assert client.put(f"/api/v1/chapters/{cid}/content_from_scenes").status_code == 422

    s2 = client.post(f"/api/v1/chapters/{cid}/scenes", json={
        "title": "후반", "content_md": "두 번째 장면.", "sort_order": 2}).json()
    s1 = client.post(f"/api/v1/chapters/{cid}/scenes", json={
        "title": "전반", "content_md": "첫 번째 장면.", "sort_order": 1}).json()

    r = client.put(f"/api/v1/chapters/{cid}/content_from_scenes")
    assert r.status_code == 200
    body = r.json()
    assert body["content_md"] == "첫 번째 장면.\n\n두 번째 장면."
    assert body["word_count_cache"] > 0


# ---------- G-041 품질 이력 ----------
def test_quality_record_history_dedup(client, project, chapter):
    cid = chapter["id"]
    client.put(f"/api/v1/chapters/{cid}/content", json={"content_md": "「비켜라.」\n\n순간, 칼이 빠졌다."})
    r1 = client.get(f"/api/v1/chapters/{cid}/quality").json()
    assert r1["recorded"] is True
    # 같은 본문 재조회 — 중복 기록 스킵
    r2 = client.get(f"/api/v1/chapters/{cid}/quality").json()
    assert r2["recorded"] is False
    # 본문 변경 — 새 기록
    client.put(f"/api/v1/chapters/{cid}/content", json={"content_md": "「비켜라.」\n\n순간, 칼이 빠졌다. 소리가 들려왔다."})
    r3 = client.get(f"/api/v1/chapters/{cid}/quality").json()
    assert r3["recorded"] is True

    hist = client.get(f"/api/v1/chapters/{cid}/quality/history").json()
    assert len(hist) == 2 and [h["score"] for h in hist][0] >= 0


# ---------- G-060 AI 사용량 ----------
def test_ai_usage_recorded_on_generate(client, monkeypatch, project, chapter):
    from app.routers import ai_panel
    holder = {"client": None}
    spec = {"chunks": ["안녕", "하세요"], "exc": None}

    def _make_client(base_url, api_key_encrypted):
        holder["client"] = FakeAsyncOpenAI(base_url=base_url, api_key="x", spec=spec)
        return holder["client"]

    monkeypatch.setattr(ai_panel.llm, "make_client", _make_client)
    _make_client("http://x/v1", None)
    ep = _endpoint(client, is_default=False)

    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘",
        "context": {"chapter_id": chapter["id"]}})
    assert resp.status_code == 200

    summary = client.get("/api/v1/ai/usage").json()
    gen = [s for s in summary if s["kind"] == "generate"]
    assert len(gen) >= 1
    assert gen[0]["prompt_chars"] > 0
    # 집계는 전 테스트 공유 DB — 이 호출분이 포함되었는지만 확인(안녕하세요=4자)
    assert any(s["completion_chars"] >= len("안녕하세요") for s in gen)


# ---------- G-046 복선 자동 추출 ----------
def test_foreshadow_suggest(client, monkeypatch, project, chapter):
    from app.routers import foreshadows as fs_router

    class _Completions:
        async def create(self, **kwargs):
            return _Response(json.dumps({"candidates": [
                {"title": "검의 진짜 주인", "content": "검이 다른 사람의 것으로 암시됨",
                 "keywords": ["검"]},
                {"title": "", "content": "제목 없는 후보는 무시"},
            ]}, ensure_ascii=False))

    class _FakeClient:
        def __init__(self, base_url=None, api_key_encrypted=None):
            self.chat = type("NS", (), {"completions": _Completions()})()

    monkeypatch.setattr(fs_router.llm, "make_client",
                        lambda base_url, api_key_encrypted: _FakeClient())
    _endpoint(client)
    client.put(f"/api/v1/chapters/{chapter['id']}/content",
               json={"content_md": "검이 스스로 그를 향했다."})

    body = client.post(f"/api/v1/projects/{project['id']}/foreshadows/suggest",
                       json={"chapter_id": chapter["id"]}).json()
    assert len(body["candidates"]) == 1
    assert body["candidates"][0]["title"] == "검의 진짜 주인"

    # 빈 본문 → 422
    ch2 = client.post(f"/api/v1/projects/{project['id']}/chapters",
                      json={"title": "2화"}).json()
    r = client.post(f"/api/v1/projects/{project['id']}/foreshadows/suggest",
                    json={"chapter_id": ch2["id"]})
    assert r.status_code == 422


def test_ai_usage_summary_shape(client):
    summary = client.get("/api/v1/ai/usage").json()
    assert isinstance(summary, list)
