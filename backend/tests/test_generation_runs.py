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
from sqlalchemy import select

from app.models import Chapter, GenerationOutput, GenerationRun
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


# ---------- P1 집필 계획 surface (/ai/plan) ----------

def test_plan_endpoint_returns_plan_and_saves_run(
        client, parallel_llm, endpoint, proj_chapter):
    r = client.post("/api/v1/ai/plan", json={
        "prompt_override": "계획해줘",
        "context": {"project_id": proj_chapter["project_id"],
                    "chapter_id": proj_chapter["chapter_id"]}})
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] and body["plan_output_id"]
    assert len(body["plan"]["scenes"]) == 2
    assert body["plan"]["scenes"][0]["title"] == "장면 1"
    db = _db(client)
    run = db.get(GenerationRun, body["run_id"])
    assert run.surface == "plan" and run.status == "completed"
    out = db.get(GenerationOutput, body["plan_output_id"])
    assert out.channel == "plan" and '"scenes"' in out.output_text
    # 계획 단계는 원고를 쓰지 않는다 — draft 산출물이 없어야 한다
    assert all(o.channel == "plan" for o in run.outputs)


def test_plan_endpoint_provider_error_saves_failed_run(
        client, endpoint, proj_chapter, monkeypatch):
    class _ErrClient:
        pass

    async def _boom(*a, **k):
        raise openai.APIConnectionError(request=httpx.Request("POST", "http://x"))

    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *a, **k: _ErrClient())
    monkeypatch.setattr(ai_panel.llm, "complete_chat", _boom)
    r = client.post("/api/v1/ai/plan", json={
        "prompt_override": "계획해줘",
        "context": {"project_id": proj_chapter["project_id"],
                    "chapter_id": proj_chapter["chapter_id"]}})
    assert r.status_code == 502
    db = _db(client)
    run = db.scalars(
        select(GenerationRun)
        .where(GenerationRun.surface == "plan")).first()
    assert run is not None and run.status == "provider_error"


# ---------- P2 승인 계획 주입 (approved_plan) ----------

def _approved_plan_payload():
    return {
        "scenes": [
            {"order": 1, "title": "승인 장면 1", "purpose": "p",
             "objective": "o", "choice": "c", "cost": "k",
             "required_beats": ["b"], "characters": ["주인공"],
             "opening_state": "s", "closing_hook": "h",
             "ending_intent": None},
            {"order": 2, "title": "승인 장면 2", "purpose": "p",
             "objective": "o", "choice": "c", "cost": "k",
             "required_beats": ["b"], "characters": ["주인공"],
             "opening_state": "s", "closing_hook": "h",
             "ending_intent": None},
        ],
    }


def test_parallel_approved_plan_skips_planner(
        client, parallel_llm, endpoint, proj_chapter):
    r = client.post("/api/v1/ai/generate-parallel", json={
        "prompt_override": "집필해줘",
        "context": {"project_id": proj_chapter["project_id"],
                    "chapter_id": proj_chapter["chapter_id"]},
        "approved_plan": _approved_plan_payload()})
    assert r.status_code == 200
    events = _parse_sse(r.text)
    saved = _saved_event(events)
    db = _db(client)
    run = db.get(GenerationRun, saved["run_id"])
    assert run.input_manifest_json["plan_source"] == "approved"
    # planner를 건너뛰었으므로 plan 산출물은 승인 계획 그대로다
    plan_out = next(o for o in run.outputs if o.channel == "plan")
    assert "승인 장면 1" in plan_out.output_text


def test_parallel_approved_plan_records_output_id(
        client, parallel_llm, endpoint, proj_chapter):
    # 먼저 /ai/plan으로 계획 산출물을 만든 뒤 그 id로 승인 집필한다
    pr = client.post("/api/v1/ai/plan", json={
        "prompt_override": "계획해줘",
        "context": {"project_id": proj_chapter["project_id"],
                    "chapter_id": proj_chapter["chapter_id"]}}).json()
    r = client.post("/api/v1/ai/generate-parallel", json={
        "prompt_override": "집필해줘",
        "context": {"project_id": proj_chapter["project_id"],
                    "chapter_id": proj_chapter["chapter_id"]},
        "approved_plan": _approved_plan_payload(),
        "plan_output_id": pr["plan_output_id"]})
    assert r.status_code == 200
    saved = _saved_event(_parse_sse(r.text))
    db = _db(client)
    run = db.get(GenerationRun, saved["run_id"])
    assert run.input_manifest_json["plan_output_id"] == pr["plan_output_id"]


def test_parallel_approved_plan_purpose_mismatch_422(
        client, parallel_llm, endpoint, proj_chapter):
    bad = _approved_plan_payload()
    for scene in bad["scenes"]:
        scene["closing_hook"] = None  # serial은 closing_hook 필수
    r = client.post("/api/v1/ai/generate-parallel", json={
        "prompt_override": "집필해줘",
        "context": {"project_id": proj_chapter["project_id"],
                    "chapter_id": proj_chapter["chapter_id"],
                    "episode_purpose": "serial"},
        "approved_plan": bad})
    assert r.status_code == 422


# ---------- P4 assistant 이력 기록 ----------

def test_assistant_generate_next_records_run(
        client, endpoint, proj_chapter, monkeypatch):
    class _Client:
        pass

    async def complete_chat(client_, model, messages, **kw):
        return "원클릭으로 쓴 원고 본문."

    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *a, **k: _Client())
    monkeypatch.setattr(ai_panel.llm, "complete_chat", complete_chat)
    r = client.post(
        f"/api/v1/projects/{proj_chapter['project_id']}/assistant/generate-next",
        json={})
    assert r.status_code == 200
    body = r.json()
    assert body["content_md"] == "원클릭으로 쓴 원고 본문."
    db = _db(client)
    run = db.scalars(
        select(GenerationRun)
        .where(GenerationRun.surface == "assistant_generate")).first()
    assert run is not None and run.status == "completed"
    assert run.outputs[0].channel == "draft"
    assert run.outputs[0].output_text == "원클릭으로 쓴 원고 본문."


def test_assistant_generate_next_no_empty_chapter_409(
        client, endpoint, proj_chapter, monkeypatch):
    class _Client:
        pass

    async def complete_chat(client_, model, messages, **kw):
        return "텍스트"

    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *a, **k: _Client())
    monkeypatch.setattr(ai_panel.llm, "complete_chat", complete_chat)
    # 회차를 원고로 채운 뒤 호출 — 빈 회차 부재 409 (기존 원고 덮어쓰기 없음).
    # P4 이후 generate-next는 원고를 쓰지 않으므로 CAS 저장 경로로 채운다.
    cid = proj_chapter["chapter_id"]
    revision = _db(client).get(Chapter, cid).revision
    client.put(f"/api/v1/chapters/{cid}/content",
               json={"content_md": "기존 원고", "expected_revision": revision})
    r = client.post(
        f"/api/v1/projects/{proj_chapter['project_id']}/assistant/generate-next",
        json={})
    assert r.status_code == 409


# ---------- E3 결정론 분석 (/projects/{pid}/generation-analysis) ----------

def _generate_draft_output_id(client, proj_chapter) -> tuple[int, int]:
    """단일 생성 스트림을 완주하고 (run_id, draft output_id)를 돌려준다."""
    resp = client.post("/api/v1/ai/generate", json={
        "prompt_override": "써줘",
        "context": {"chapter_id": proj_chapter["chapter_id"],
                    "project_id": proj_chapter["project_id"]}})
    assert resp.status_code == 200, resp.text
    saved = _saved_event(_parse_sse(resp.text))
    return saved["run_id"], saved["outputs"]["draft"]


def test_analysis_reports_edit_distance_and_deleted_expressions(
        client, fake_llm, endpoint, proj_chapter):
    """output→landed diff에서 편집거리·삭제 표현·수용률을 산출한다."""
    _run_id, output_id = _generate_draft_output_id(client, proj_chapter)
    # 작가가 둘째 줄을 지우고 반영 — landed_text는 output의 부분집합
    r = client.post(f"/api/v1/generation-outputs/{output_id}/outcome", json={
        "outcome": "inserted", "landed_text": "초안 한 줄."})
    assert r.status_code == 200

    res = client.get(
        f"/api/v1/projects/{proj_chapter['project_id']}/generation-analysis")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_runs"] == 1
    assert body["total_outputs"] == 1

    entry = body["edit_distances"][0]
    assert entry["output_id"] == output_id
    assert entry["channel"] == "draft"
    assert 0 < entry["ratio"] < 1  # 일부 삭제 — 무변경 수용이 아니다
    assert entry["landed_chars"] == len("초안 한 줄.")

    deleted_texts = [d["text"] for d in body["deleted_expressions"]]
    assert any("둘째 줄" in t for t in deleted_texts)
    ev = next(d for d in body["deleted_expressions"] if "둘째 줄" in d["text"])
    assert output_id in ev["output_ids"]

    surf = next(s for s in body["surfaces"] if s["surface"] == "generate")
    assert surf["outcome_counts"]["inserted"] == 1
    assert surf["accept_rate"] == 1.0

    length = next(l for l in body["length_distribution"]
                  if l["channel"] == "draft")
    assert length["count"] == 1
    assert length["max_chars"] == len("초안 한 줄. 둘째 줄.")


def test_analysis_landed_still_present_flag(
        client, fake_llm, endpoint, proj_chapter):
    """landed_text가 현재 원고에 남아 있는지 잔존 플래그를 낸다."""
    _run_id, output_id = _generate_draft_output_id(client, proj_chapter)
    client.post(f"/api/v1/generation-outputs/{output_id}/outcome", json={
        "outcome": "inserted", "landed_text": "초안 한 줄."})
    cid = proj_chapter["chapter_id"]
    revision = _db(client).get(Chapter, cid).revision
    client.put(f"/api/v1/chapters/{cid}/content",
               json={"content_md": "초안 한 줄.\n이후 작가가 이어 씀.",
                     "expected_revision": revision})
    body = client.get(
        f"/api/v1/projects/{proj_chapter['project_id']}/generation-analysis"
    ).json()
    assert body["edit_distances"][0]["landed_still_present"] is True


def test_analysis_accept_rate_excludes_pending(
        client, fake_llm, endpoint, proj_chapter):
    """pending은 처분 미결 — accept_rate 분모에서 제외한다."""
    _run_id, output_id = _generate_draft_output_id(client, proj_chapter)
    _run_id2, output_id2 = _generate_draft_output_id(client, proj_chapter)
    client.post(f"/api/v1/generation-outputs/{output_id}/outcome",
                json={"outcome": "discarded"})
    body = client.get(
        f"/api/v1/projects/{proj_chapter['project_id']}/generation-analysis"
    ).json()
    surf = next(s for s in body["surfaces"] if s["surface"] == "generate")
    assert surf["outcome_counts"]["pending"] == 1
    assert surf["outcome_counts"]["discarded"] == 1
    assert surf["accept_rate"] == 0.0  # 결정 1건 중 수용 0


def test_analysis_empty_project(client, proj_chapter):
    res = client.get(
        f"/api/v1/projects/{proj_chapter['project_id']}/generation-analysis")
    assert res.status_code == 200
    body = res.json()
    assert body["total_runs"] == 0
    assert body["avg_edit_ratio"] is None
    assert body["surfaces"] == []
