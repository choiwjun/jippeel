"""assistant 계획→승인→초안 경로 테스트 (P4 정합).

- plan-next: 계획만 생성하고 원고를 쓰지 않는다.
- generate-next: 초안 산출물로만 보존 — replace_manuscript를 호출하지 않는다.
- apply: 작가의 명시 액션만이 산출물을 정본으로 승격한다(CAS).
"""
import json

import pytest
from sqlalchemy import select

from app.models import Chapter, GenerationOutput, GenerationRun
from app.routers import ai_panel
from tests.conftest import _db
from tests.test_ai_generate_stream import _parallel_plan_json


# ---------- fixtures ----------

@pytest.fixture()
def proj_chapter(client):
    project = client.post("/api/v1/projects", json={"title": "p"}).json()
    chapter = client.post(
        f"/api/v1/projects/{project['id']}/chapters", json={}).json()
    return {"project_id": project["id"], "chapter_id": chapter["id"]}


@pytest.fixture()
def assistant_llm(monkeypatch):
    """planner/집필 호출을 구분해 기록하는 fake — provider 호출은 없다."""
    calls: list[str] = []

    class FakeClient:
        pass

    async def complete_chat(client, model, messages, temperature=None,
                            max_tokens=None, reasoning_effort=None):
        user = messages[-1]["content"]
        if "[병렬 Planner" in user:
            calls.append("planner")
            return _parallel_plan_json()
        calls.append("draft")
        assert "작가 승인 집필 계획" not in user or "scenes" in user
        return "생성된 초안 원고입니다."

    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *a, **k: FakeClient())
    monkeypatch.setattr(ai_panel.llm, "complete_chat", complete_chat)
    return calls


def _outputs_for_run(client, run_id: int):
    s = _db(client)
    return s.scalars(
        select(GenerationOutput)
        .where(GenerationOutput.run_id == run_id)
    ).all()


def _chapter_content(client, chapter_id: int) -> str:
    return _db(client).get(Chapter, chapter_id).content_md or ""


def _fill_chapter(client, chapter_id: int, text: str = "기존 원고"):
    """원고 저장은 PUT /chapters/{id}/content의 CAS 경로를 통한다."""
    revision = _db(client).get(Chapter, chapter_id).revision
    r = client.put(
        f"/api/v1/chapters/{chapter_id}/content",
        json={"content_md": text, "expected_revision": revision})
    assert r.status_code == 200, r.text


# ---------- plan-next ----------

def test_plan_next_returns_plan_without_writing_manuscript(
        client, proj_chapter, assistant_llm):
    r = client.post(
        f"/api/v1/projects/{proj_chapter['project_id']}/assistant/plan-next",
        json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["chapter_id"] == proj_chapter["chapter_id"]
    assert len(body["plan"]["scenes"]) == 2
    assert body["plan_output_id"] is not None
    # 원고는 절대 쓰지 않는다
    assert _chapter_content(client, proj_chapter["chapter_id"]) == ""
    # 계획 산출물이 이력에 보존됐다
    run = _db(client).get(GenerationRun, body["run_id"])
    assert run is not None and run.surface == "plan"
    assert run.status == "completed"
    outs = _outputs_for_run(client, body["run_id"])
    assert [o.channel for o in outs] == ["plan"]


def test_plan_next_all_filled_returns_409(client, proj_chapter, assistant_llm):
    cid = proj_chapter["chapter_id"]
    _fill_chapter(client, cid)
    r = client.post(
        f"/api/v1/projects/{proj_chapter['project_id']}/assistant/plan-next",
        json={})
    assert r.status_code == 409


def test_plan_next_explicit_chapter_id_targets_filled_chapter(
        client, proj_chapter, assistant_llm):
    """내용이 있는 회차도 계획 대상이 될 수 있다 — 계획은 원고를 건드리지 않는다."""
    cid = proj_chapter["chapter_id"]
    _fill_chapter(client, cid)
    r = client.post(
        f"/api/v1/projects/{proj_chapter['project_id']}/assistant/plan-next",
        json={"chapter_id": cid})
    assert r.status_code == 200, r.text
    assert r.json()["chapter_id"] == cid
    assert _chapter_content(client, cid) == "기존 원고"


# ---------- generate-next (draft-only) ----------

def test_generate_next_returns_draft_without_writing_manuscript(
        client, proj_chapter, assistant_llm):
    r = client.post(
        f"/api/v1/projects/{proj_chapter['project_id']}/assistant/generate-next",
        json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] is False
    assert body["content_md"] == "생성된 초안 원고입니다."
    assert body["draft_output_id"] is not None
    # 핵심 계약 — 원고에 자동 반영되지 않는다
    assert _chapter_content(client, proj_chapter["chapter_id"]) == ""
    outs = _outputs_for_run(client, body["run_id"])
    assert [o.channel for o in outs] == ["draft"]
    run = _db(client).get(GenerationRun, body["run_id"])
    assert run.surface == "assistant_generate"
    assert run.input_manifest_json["draft_only"] is True


def test_generate_next_with_approved_plan_skips_planner(
        client, proj_chapter, assistant_llm):
    plan = json.loads(_parallel_plan_json())
    r = client.post(
        f"/api/v1/projects/{proj_chapter['project_id']}/assistant/generate-next",
        json={"approved_plan": plan, "plan_output_id": 7})
    assert r.status_code == 200, r.text
    # planner가 호출되지 않고 집필만 실행됐다
    assert assistant_llm == ["draft"]
    outs = _outputs_for_run(client, r.json()["run_id"])
    assert sorted(o.channel for o in outs) == ["draft", "plan"]
    run = _db(client).get(GenerationRun, r.json()["run_id"])
    assert run.input_manifest_json["plan_source"] == "approved"
    assert run.input_manifest_json["plan_output_id"] == 7


def test_generate_next_filled_chapter_not_overwritten(
        client, proj_chapter, assistant_llm):
    """기존 원고가 있는 회차를 대상으로 해도 덮어쓰지 않는다."""
    cid = proj_chapter["chapter_id"]
    _fill_chapter(client, cid)
    r = client.post(
        f"/api/v1/projects/{proj_chapter['project_id']}/assistant/generate-next",
        json={"chapter_id": cid})
    assert r.status_code == 200, r.text
    assert _chapter_content(client, cid) == "기존 원고"


def test_generate_next_no_target_returns_409(client, proj_chapter, assistant_llm):
    cid = proj_chapter["chapter_id"]
    _fill_chapter(client, cid)
    r = client.post(
        f"/api/v1/projects/{proj_chapter['project_id']}/assistant/generate-next",
        json={})
    assert r.status_code == 409


def test_generate_next_other_project_chapter_rejected(
        client, proj_chapter, assistant_llm):
    other = client.post("/api/v1/projects", json={"title": "other"}).json()
    r = client.post(
        f"/api/v1/projects/{proj_chapter['project_id']}/assistant/generate-next",
        json={"chapter_id": 99999})
    assert r.status_code == 404
    _ = other


# ---------- apply — 명시적 정본 승격 ----------

def _make_draft(client, proj_chapter) -> dict:
    r = client.post(
        f"/api/v1/projects/{proj_chapter['project_id']}/assistant/generate-next",
        json={})
    assert r.status_code == 200, r.text
    return r.json()


def test_apply_writes_manuscript_and_records_outcome(
        client, proj_chapter, assistant_llm):
    draft = _make_draft(client, proj_chapter)
    r = client.post(
        f"/api/v1/generation-outputs/{draft['draft_output_id']}/apply",
        json={"expected_revision": draft["revision"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == "inserted"
    assert body["revision"] == draft["revision"] + 1
    assert _chapter_content(client, draft["chapter_id"]) == "생성된 초안 원고입니다."
    out = _db(client).get(GenerationOutput, draft["draft_output_id"])
    assert out.outcome == "inserted"
    assert out.landed_text == "생성된 초안 원고입니다."


def test_apply_stale_revision_returns_409(
        client, proj_chapter, assistant_llm):
    draft = _make_draft(client, proj_chapter)
    r = client.post(
        f"/api/v1/generation-outputs/{draft['draft_output_id']}/apply",
        json={"expected_revision": draft["revision"] + 5})
    assert r.status_code == 409
    assert _chapter_content(client, draft["chapter_id"]) == ""


def test_apply_terminal_outcome_returns_409(
        client, proj_chapter, assistant_llm):
    draft = _make_draft(client, proj_chapter)
    client.post(
        f"/api/v1/generation-outputs/{draft['draft_output_id']}/outcome",
        json={"outcome": "discarded"})
    r = client.post(
        f"/api/v1/generation-outputs/{draft['draft_output_id']}/apply",
        json={})
    assert r.status_code == 409
    assert _chapter_content(client, draft["chapter_id"]) == ""


def test_apply_plan_channel_rejected(
        client, proj_chapter, assistant_llm):
    pr = client.post(
        f"/api/v1/projects/{proj_chapter['project_id']}/assistant/plan-next",
        json={})
    plan_output_id = pr.json()["plan_output_id"]
    r = client.post(
        f"/api/v1/generation-outputs/{plan_output_id}/apply", json={})
    assert r.status_code == 409
