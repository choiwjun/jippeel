"""E1 생성 이력 — generation_runs/outputs 영속 + E2 outcome 기록 테스트.

fake provider(test_ai_generate_stream의 FakeAsyncOpenAI·parallel fake)를 재사용해
3개 surface(/ai/generate, /ai/generate-parallel, /ai/review)가 이력을 남기고,
SSE 계약이 additive(generation_saved)만 확장됐음을 검증한다.
"""
import hashlib
import json
from typing import Any

import httpx
import openai  # pyright: ignore[reportMissingImports]
import pytest

from app.models import GenerationOutput, GenerationRun
from app.routers import ai_panel
from tests.conftest import _db
from tests.test_ai_generate_stream import (
    FakeAsyncOpenAI,
    _Chunk,
    _parse_sse,
    _parallel_plan_json,
)


# ---------- fixtures ----------

@pytest.fixture()
def fake_llm(monkeypatch):
    """기본 fake — draft·review 호출 모두 같은 chunks를 흘린다."""
    spec = {"chunks": ["초안 한 줄.", " 둘째 줄."], "exc": None}

    def _make_client(base_url, api_key_encrypted):
        return FakeAsyncOpenAI(base_url=base_url, api_key="decrypted", spec=spec)

    monkeypatch.setattr(ai_panel.llm, "make_client", _make_client)
    return spec


@pytest.fixture()
def endpoint(client):
    return client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://localhost:1234/v1",
        "api_key": "secret", "default_model": "m-1"}).json()


@pytest.fixture()
def proj_chapter(client):
    project = client.post("/api/v1/projects", json={"title": "p"}).json()
    chapter = client.post(
        f"/api/v1/projects/{project['id']}/chapters", json={}).json()
    return {"project_id": project["id"], "chapter_id": chapter["id"]}


@pytest.fixture()
def parallel_llm(monkeypatch):
    class FakeClient:
        pass

    async def complete_chat(client, model, messages, temperature=None,
                            max_tokens=None, reasoning_effort=None):
        user = messages[-1]["content"]
        if "[병렬 Planner" in user:
            return _parallel_plan_json()
        if '"order": 1' in user:
            return "장면 1 원고"
        if '"order": 2' in user:
            return "장면 2 원고"
        raise AssertionError(f"unexpected prompt: {user[:100]}")

    async def stream_chat(client, model, messages, temperature=None,
                          max_tokens=None, reasoning_effort=None):
        yield "[감수]\n- 연결 자연스러움."

    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *a, **k: FakeClient())
    monkeypatch.setattr(ai_panel.llm, "complete_chat", complete_chat)
    monkeypatch.setattr(ai_panel.llm, "stream_chat", stream_chat)


def _saved_event(events):
    data = [json.loads(d) for e, d in events if e == "generation_saved"]
    assert len(data) == 1, f"generation_saved 이벤트 없음: {[e for e, _ in events]}"
    return data[0]


# ---------- E1: surface별 기록 ----------

def test_generate_records_run_and_draft_output(client, fake_llm, endpoint, proj_chapter):
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": endpoint["id"],
        "prompt_override": "써줘",
        "context": {"chapter_id": proj_chapter["chapter_id"],
                    "project_id": proj_chapter["project_id"]}})
    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.text)
    names = [e for e, _ in events]
    assert names[0] == "start" and names[-1] == "done"

    saved = _saved_event(events)
    assert saved["run_id"]
    detail = client.get(f"/api/v1/generation-runs/{saved['run_id']}").json()
    assert detail["surface"] == "generate"
    assert detail["status"] == "completed"
    assert detail["project_id"] == proj_chapter["project_id"]
    assert detail["chapter_id"] == proj_chapter["chapter_id"]
    assert detail["input_sha256"]
    assert detail["ai_usage_id"] is not None

    assert list(saved["outputs"].keys()) == ["draft"]
    out = detail["outputs"][0]
    assert out["id"] == saved["outputs"]["draft"]
    assert out["channel"] == "draft"
    assert out["output_text"] == "초안 한 줄. 둘째 줄."
    assert out["output_chars"] == len("초안 한 줄. 둘째 줄.")
    assert out["output_sha256"] == hashlib.sha256(
        "초안 한 줄. 둘째 줄.".encode("utf-8")).hexdigest()
    assert out["outcome"] == "pending"


def test_generate_with_review_records_all_channels(
        client, fake_llm, endpoint, proj_chapter, monkeypatch):
    fake_llm["chunks"] = ["[감수] 괜찮음.", "\n[수정본]\n", "다시 쓴 원고."]
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": endpoint["id"],
        "prompt_override": "써줘",
        "context": {"chapter_id": proj_chapter["chapter_id"]},
        "review": {}})
    events = _parse_sse(resp.text)
    saved = _saved_event(events)
    assert {"draft", "review", "refined"} <= set(saved["outputs"])
    detail = client.get(f"/api/v1/generation-runs/{saved['run_id']}").json()
    channels = {o["channel"]: o for o in detail["outputs"]}
    assert channels["refined"]["output_text"].endswith("다시 쓴 원고.")
    assert "[감수] 괜찮음." in channels["review"]["output_text"]


def test_generate_provider_error_preserves_partial_draft(
        client, endpoint, proj_chapter, monkeypatch):
    """스트림 중간 provider 에러 — 부분 초안 보존 + status=provider_error."""

    class _ErrCompletions:
        async def create(self, **kwargs):
            async def _gen():
                yield _Chunk("절반만 온 초안")
                raise openai.APIConnectionError(
                    message="끊김",
                    request=httpx.Request("POST", "http://x/v1/chat/completions"))
            return _gen()

    class _ErrClient:
        chat = type("Chat", (), {"completions": _ErrCompletions()})()

    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *a, **k: _ErrClient())
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": endpoint["id"],
        "prompt_override": "써줘",
        "context": {"chapter_id": proj_chapter["chapter_id"]}})
    events = _parse_sse(resp.text)
    names = [e for e, _ in events]
    assert "error" in names
    # 기존 계약: draft 에러 시 done 없이 종료
    assert "done" not in names
    saved = _saved_event(events)
    detail = client.get(f"/api/v1/generation-runs/{saved['run_id']}").json()
    assert detail["status"] == "provider_error"
    assert detail["outputs"][0]["output_text"] == "절반만 온 초안"


def test_parallel_records_plan_workers_draft_review(
        client, parallel_llm, endpoint, proj_chapter):
    resp = client.post("/api/v1/ai/generate-parallel", json={
        "endpoint_id": endpoint["id"],
        "prompt_override": "병렬 집필",
        "worker_limit": 2,
        "context": {"chapter_id": proj_chapter["chapter_id"]},
        "review": {"reasoning_effort": "xhigh"}})
    assert resp.status_code == 200, resp.text
    saved = _saved_event(_parse_sse(resp.text))
    detail = client.get(f"/api/v1/generation-runs/{saved['run_id']}").json()
    assert detail["surface"] == "generate_parallel"
    channels = [o["channel"] for o in detail["outputs"]]
    assert channels == ["plan", "worker", "worker", "draft", "review"]
    workers = [o for o in detail["outputs"] if o["channel"] == "worker"]
    assert [w["scene_order"] for w in workers] == [1, 2]
    assert workers[0]["output_text"] == "장면 1 원고"
    draft = [o for o in detail["outputs"] if o["channel"] == "draft"][0]
    assert draft["output_text"] == "장면 1 원고\n\n장면 2 원고"


def test_standalone_review_saves_run_without_context(client, fake_llm, endpoint):
    fake_llm["chunks"] = ["[감수] 지적.", "\n[수정본]\n", "수정본 텍스트"]
    resp = client.post("/api/v1/ai/review", json={"draft": "원고 초안"})
    assert resp.status_code == 200, resp.text
    saved = _saved_event(_parse_sse(resp.text))
    detail = client.get(f"/api/v1/generation-runs/{saved['run_id']}").json()
    assert detail["surface"] == "review"
    assert detail["project_id"] is None
    assert detail["chapter_id"] is None
    assert {o["channel"] for o in detail["outputs"]} == {"review", "refined"}


def test_recording_failure_never_breaks_stream(
        client, fake_llm, endpoint, proj_chapter, monkeypatch):
    """이력 기록이 실패해도 스트림은 정상 완료된다(best-effort)."""
    def _boom(**kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(ai_panel.generation_runs_svc, "save_run", _boom)
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": endpoint["id"],
        "prompt_override": "써줘",
        "context": {"chapter_id": proj_chapter["chapter_id"]}})
    events = _parse_sse(resp.text)
    names = [e for e, _ in events]
    assert names[-1] == "done"
    saved = _saved_event(events)
    assert saved["run_id"] is None


# ---------- E2: outcome 처분 ----------

def _make_output(client, endpoint, proj_chapter) -> int:
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": endpoint["id"],
        "prompt_override": "써줘",
        "context": {"chapter_id": proj_chapter["chapter_id"]}})
    return _saved_event(_parse_sse(resp.text))["outputs"]["draft"]


def test_outcome_transitions_and_409(client, fake_llm, endpoint, proj_chapter):
    oid = _make_output(client, endpoint, proj_chapter)
    # pending → copied → inserted 허용
    r = client.post(f"/api/v1/generation-outputs/{oid}/outcome",
                    json={"outcome": "copied"})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/generation-outputs/{oid}/outcome",
                    json={"outcome": "inserted",
                          "landed_text": "초안 한 줄. 둘째 줄.",
                          "chapter_revision": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["outcome"] == "inserted"
    assert [e["outcome"] for e in body["outcome_events_json"]] == ["copied", "inserted"]
    # 종결 상태 재전이는 409
    r = client.post(f"/api/v1/generation-outputs/{oid}/outcome",
                    json={"outcome": "discarded"})
    assert r.status_code == 409


def test_outcome_stores_landed_text_and_revision(
        client, fake_llm, endpoint, proj_chapter):
    oid = _make_output(client, endpoint, proj_chapter)
    r = client.post(f"/api/v1/generation-outputs/{oid}/outcome", json={
        "outcome": "replaced",
        "landed_text": "작가가 고쳐 넣은 문장.",
        "chapter_revision": 7})
    assert r.status_code == 200
    db = _db(client)
    out = db.get(GenerationOutput, oid)
    assert out.landed_text == "작가가 고쳐 넣은 문장."
    assert out.chapter_revision_at_action == 7
    assert out.outcome_at is not None


def test_outcome_404_and_invalid(client, fake_llm, endpoint, proj_chapter):
    r = client.post("/api/v1/generation-outputs/99999/outcome",
                    json={"outcome": "inserted"})
    assert r.status_code == 404
    oid = _make_output(client, endpoint, proj_chapter)
    r = client.post(f"/api/v1/generation-outputs/{oid}/outcome",
                    json={"outcome": "bogus"})
    assert r.status_code == 422


# ---------- 감사 보존 / 격리 ----------

def test_chapter_delete_preserves_run_with_null_chapter(
        client, fake_llm, endpoint, proj_chapter):
    oid = _make_output(client, endpoint, proj_chapter)
    db = _db(client)
    run_id = db.get(GenerationOutput, oid).run_id
    r = client.delete(f"/api/v1/chapters/{proj_chapter['chapter_id']}")
    assert r.status_code == 204
    db.expire_all()
    run = db.get(GenerationRun, run_id)
    assert run is not None and run.chapter_id is None


def test_project_delete_cascades_runs(client, fake_llm, endpoint, proj_chapter):
    oid = _make_output(client, endpoint, proj_chapter)
    db = _db(client)
    run_id = db.get(GenerationOutput, oid).run_id
    r = client.delete(f"/api/v1/projects/{proj_chapter['project_id']}")
    assert r.status_code == 204
    db.expire_all()
    assert db.get(GenerationRun, run_id) is None
    assert db.get(GenerationOutput, oid) is None


def test_chapter_runs_list_endpoint(client, fake_llm, endpoint, proj_chapter):
    _make_output(client, endpoint, proj_chapter)
    _make_output(client, endpoint, proj_chapter)
    runs = client.get(
        f"/api/v1/chapters/{proj_chapter['chapter_id']}/generation-runs").json()
    assert len(runs) == 2
    assert runs[0]["id"] > runs[1]["id"]  # 최신순
    assert runs[0]["outputs"][0]["channel"] == "draft"
    assert "output_text" not in runs[0]["outputs"][0]  # 목록은 요약만
    r = client.get("/api/v1/chapters/99999/generation-runs")
    assert r.status_code == 404
