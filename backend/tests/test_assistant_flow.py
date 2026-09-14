"""AI 어시스턴트 plan-first·draft-only와 병렬 감수 transport 재시도 계약.

과거 자동 저장 계약의 테스트를 draft-only 계약으로 이식했다 — generate-next는
원고를 쓰지 않고 channel=draft 산출물만 보존하며, 원고 반영은
POST /generation-outputs/{id}/apply의 명시 액션만이 수행한다.
"""

import json

import httpx
from sqlalchemy import select

from app.models import Chapter, ChapterSnapshot, GenerationOutput, GenerationRun
from app.routers import ai_panel
from tests.conftest import _db


def test_assistant_generates_draft_and_apply_is_explicit(client, monkeypatch):
    calls = []

    class FakeClient:
        pass

    async def complete_chat(client_obj, model, messages, temperature=None,
                            max_tokens=None, reasoning_effort=None):
        calls.append({"client": client_obj, "model": model, "messages": messages,
                      "max_tokens": max_tokens, "reasoning_effort": reasoning_effort})
        return "첫 회차의 정본 본문입니다."

    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *args, **kwargs: FakeClient())
    monkeypatch.setattr(ai_panel.llm, "complete_chat", complete_chat)

    project = client.post("/api/v1/projects", json={
        "title": "원클릭 작품", "genre": "판타지",
    }).json()
    client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"style_profile": "STYLE_TOKEN_ASSISTANT"},
    )
    first = client.post(
        f"/api/v1/projects/{project['id']}/chapters",
        json={"title": "1화", "sort_order": 0},
    ).json()
    second = client.post(
        f"/api/v1/projects/{project['id']}/chapters",
        json={"title": "2화", "sort_order": 1},
    ).json()
    client.put(
        f"/api/v1/chapters/{second['id']}/content",
        json={"content_md": "이미 작성된 2화", "expected_revision": 0},
    )

    response = client.post(
        f"/api/v1/projects/{project['id']}/assistant/generate-next",
        json={},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["chapter_id"] == first["id"]
    assert body["content_md"] == "첫 회차의 정본 본문입니다."
    assert body["applied"] is False
    assert body["draft_output_id"] is not None
    assert len(calls) == 1
    combined = "\n".join(m["content"] for m in calls[0]["messages"])
    assert "STYLE_TOKEN_ASSISTANT" in combined
    assert "목차" in combined

    # draft-only — 원고는 건드리지 않는다.
    db = _db(client)
    stored = db.get(Chapter, first["id"])
    assert (stored.content_md or "").strip() == ""
    assert stored.revision == 0

    # 명시적 apply만 원고로 승격한다 — expected_revision CAS 필수.
    apply_resp = client.post(
        f"/api/v1/generation-outputs/{body['draft_output_id']}/apply",
        json={"expected_revision": body["revision"]},
    )
    assert apply_resp.status_code == 200, apply_resp.text
    db.expire_all()
    stored = db.get(Chapter, first["id"])
    assert stored.content_md == "첫 회차의 정본 본문입니다."
    assert stored.revision == 1
    snapshot = db.scalar(select(ChapterSnapshot).where(
        ChapterSnapshot.chapter_id == first["id"]
    ))
    assert snapshot is not None
    assert snapshot.reason == "generation_output_apply"


def test_assistant_rejects_project_without_blank_chapter(client, monkeypatch):
    class FakeClient:
        pass

    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *args, **kwargs: FakeClient())
    project = client.post("/api/v1/projects", json={"title": "완성 작품"}).json()
    chapter = client.post(
        f"/api/v1/projects/{project['id']}/chapters", json={"title": "1화"}
    ).json()
    client.put(
        f"/api/v1/chapters/{chapter['id']}/content",
        json={"content_md": "완성된 본문", "expected_revision": 0},
    )

    response = client.post(
        f"/api/v1/projects/{project['id']}/assistant/generate-next", json={}
    )

    assert response.status_code == 409
    assert "빈 회차" in response.json()["detail"]


def test_apply_requires_expected_revision(client, monkeypatch):
    """expected_revision 생략은 허용하지 않는다 — 422."""
    class FakeClient:
        pass

    async def complete_chat(client_obj, model, messages, temperature=None,
                            max_tokens=None, reasoning_effort=None):
        return "초안 본문"

    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *args, **kwargs: FakeClient())
    monkeypatch.setattr(ai_panel.llm, "complete_chat", complete_chat)

    project = client.post("/api/v1/projects", json={"title": "CAS 작품"}).json()
    client.post(
        f"/api/v1/projects/{project['id']}/chapters", json={"title": "1화"}
    )
    gen = client.post(
        f"/api/v1/projects/{project['id']}/assistant/generate-next", json={}
    ).json()

    missing = client.post(
        f"/api/v1/generation-outputs/{gen['draft_output_id']}/apply", json={}
    )
    assert missing.status_code == 422

    stale = client.post(
        f"/api/v1/generation-outputs/{gen['draft_output_id']}/apply",
        json={"expected_revision": 99},
    )
    assert stale.status_code == 409


def test_assistant_context_auto_includes_characters(client, monkeypatch):
    """어시스턴트 계획 경로는 인물 카드를 자동 주입한다 — 수동 선택 불필요."""
    captured = []

    class FakeClient:
        pass

    async def complete_chat(client_obj, model, messages, temperature=None,
                            max_tokens=None, reasoning_effort=None):
        captured.append(messages)
        return json.dumps({
            "scenes": [
                {"order": 1, "title": "시작", "purpose": "도입",
                 "objective": "등장", "choice": "나선다", "cost": "위험",
                 "required_beats": ["도입"], "characters": ["주인공"],
                 "opening_state": "시작", "closing_hook": "다음"},
                {"order": 2, "title": "전개", "purpose": "확대",
                 "objective": "추격", "choice": "도망", "cost": "길 잃음",
                 "required_beats": ["추격"], "characters": ["주인공"],
                 "opening_state": "직후", "closing_hook": "끝"},
            ]
        }, ensure_ascii=False)

    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *args, **kwargs: FakeClient())
    monkeypatch.setattr(ai_panel.llm, "complete_chat", complete_chat)

    project = client.post("/api/v1/projects", json={"title": "인물 작품"}).json()
    client.post(
        f"/api/v1/projects/{project['id']}/chapters", json={"title": "1화"}
    )
    char_resp = client.post(
        f"/api/v1/projects/{project['id']}/characters",
        json={"name": "CHAR_TOKEN_HERO", "role": "주연"},
    )
    assert char_resp.status_code == 201, char_resp.text

    resp = client.post(
        f"/api/v1/projects/{project['id']}/assistant/plan-next", json={}
    )
    assert resp.status_code == 200, resp.text
    combined = "\n".join(
        str(m.get("content") or "") for m in captured[-1]
    )
    assert "CHAR_TOKEN_HERO" in combined


def test_single_generate_accepts_approved_plan(client, monkeypatch):
    """단일 /ai/generate도 승인 계획을 계약으로 주입하고 이력에 plan을 남긴다."""
    captured = []

    class FakeClient:
        pass

    async def stream_chat(client_obj, model, messages, temperature=None,
                          max_tokens=None, reasoning_effort=None):
        captured.append(messages)
        yield "승인된 계획대로 쓴 본문"

    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *args, **kwargs: FakeClient())
    monkeypatch.setattr(ai_panel.llm, "stream_chat", stream_chat)

    project = client.post("/api/v1/projects", json={"title": "계획 작품"}).json()
    chapter = client.post(
        f"/api/v1/projects/{project['id']}/chapters", json={"title": "1화"}
    ).json()

    plan = {
        "scenes": [
            {"order": 1, "title": "시작", "purpose": "도입",
             "objective": "등장", "choice": "나선다", "cost": "위험",
             "required_beats": ["도입"], "characters": ["주인공"],
             "opening_state": "시작", "closing_hook": "다음"},
            {"order": 2, "title": "전개", "purpose": "확대",
             "objective": "추격", "choice": "도망", "cost": "길 잃음",
             "required_beats": ["추격"], "characters": ["주인공"],
             "opening_state": "직후", "closing_hook": "끝"},
        ]
    }
    resp = client.post("/api/v1/ai/generate", json={
        "prompt_override": "집필하라.",
        "context": {"chapter_id": chapter["id"], "project_id": project["id"]},
        "approved_plan": plan,
    })
    assert resp.status_code == 200, resp.text
    assert "[작가 승인 집필 계획" in captured[-1][-1]["content"]

    db = _db(client)
    run = db.scalar(select(GenerationRun).where(
        GenerationRun.surface == "generate"
    ))
    assert run is not None
    manifest = run.input_manifest_json or {}
    assert manifest.get("plan_source") == "approved"
    plan_out = db.scalar(select(GenerationOutput).where(
        GenerationOutput.run_id == run.id,
        GenerationOutput.channel == "plan",
    ))
    assert plan_out is not None


def test_parallel_review_retries_bridge_disconnect_before_first_token(client, monkeypatch):
    attempts = {"review": 0}

    class FakeClient:
        pass

    plan = json.dumps({
        "scenes": [
            {"order": 1, "title": "첫 장면", "purpose": "시작", "objective": "문을 연다",
             "choice": "문을 연다", "cost": "흔적을 남긴다", "required_beats": ["문 앞"],
             "characters": ["주인공"], "opening_state": "시작", "closing_hook": "다음 장면"},
            {"order": 2, "title": "둘째 장면", "purpose": "확대", "objective": "도망친다",
             "choice": "골목으로 간다", "cost": "길을 잃는다", "required_beats": ["추격"],
             "characters": ["주인공"], "opening_state": "첫 장면 직후", "closing_hook": "끝"},
        ]
    }, ensure_ascii=False)

    async def complete_chat(client_obj, model, messages, temperature=None,
                            max_tokens=None, reasoning_effort=None):
        prompt = messages[-1]["content"]
        if "[병렬 Planner" in prompt:
            return plan
        return "장면 본문"

    async def stream_chat(client_obj, model, messages, temperature=None,
                          max_tokens=None, reasoning_effort=None):
        attempts["review"] += 1
        if attempts["review"] == 1:
            raise httpx.RemoteProtocolError("bridge closed before response")
        yield "[감수]\n- 연결 확인"

    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *args, **kwargs: FakeClient())
    monkeypatch.setattr(ai_panel.llm, "complete_chat", complete_chat)
    monkeypatch.setattr(ai_panel.llm, "stream_chat", stream_chat)

    response = client.post("/api/v1/ai/generate-parallel", json={
        "prompt_override": "병렬로 집필하라.", "worker_limit": 2,
    })

    assert response.status_code == 200, response.text
    assert attempts["review"] == 2
    text = response.text
    assert 'event: message' in text
    assert 'event: review' in text
    assert '"stage": "review"' not in text


def _valid_plan_json():
    return json.dumps({
        "scenes": [
            {"order": 1, "title": "첫 장면", "purpose": "시작", "objective": "문을 연다",
             "choice": "문을 연다", "cost": "흔적을 남긴다", "required_beats": ["문 앞"],
             "characters": ["주인공"], "opening_state": "시작", "closing_hook": "다음 장면"},
            {"order": 2, "title": "둘째 장면", "purpose": "확대", "objective": "도망친다",
             "choice": "골목으로 간다", "cost": "길을 잃는다", "required_beats": ["추격"],
             "characters": ["주인공"], "opening_state": "첫 장면 직후", "closing_hook": "끝"},
        ]
    }, ensure_ascii=False)


def test_parallel_planner_retries_once_on_invalid_plan(client, monkeypatch):
    """planner가 계약 밖 JSON을 한 번 반환해도 재시도로 복구된다."""
    planner_calls = {"n": 0}

    class FakeClient:
        pass

    async def complete_chat(client_obj, model, messages, temperature=None,
                            max_tokens=None, reasoning_effort=None):
        if "[병렬 Planner" not in messages[-1]["content"]:
            return "장면 본문"
        planner_calls["n"] += 1
        if planner_calls["n"] == 1:
            return json.dumps({"scenes": [{"order": 1, "title": "불완전"}]})
        return _valid_plan_json()

    async def stream_chat(client_obj, model, messages, temperature=None,
                          max_tokens=None, reasoning_effort=None):
        yield "장면 본문"

    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *a, **k: FakeClient())
    monkeypatch.setattr(ai_panel.llm, "complete_chat", complete_chat)
    monkeypatch.setattr(ai_panel.llm, "stream_chat", stream_chat)

    response = client.post("/api/v1/ai/generate-parallel", json={
        "prompt_override": "병렬로 집필하라.", "worker_limit": 2,
    })

    assert response.status_code == 200, response.text
    assert planner_calls["n"] == 2
    text = response.text
    assert 'event: planner_done' in text
    assert '"stage": "generation"' not in text


def test_parallel_planner_invalid_plan_reports_detail_and_debug(client, monkeypatch):
    """planner 검증이 재시도까지 실패하면 원인·원시 응답이 남는다."""
    planner_calls = {"n": 0}

    class FakeClient:
        pass

    async def complete_chat(client_obj, model, messages, temperature=None,
                            max_tokens=None, reasoning_effort=None):
        if "[병렬 Planner" not in messages[-1]["content"]:
            return "장면 본문"
        planner_calls["n"] += 1
        return json.dumps({"scenes": [{"order": 1, "title": "불완전"}]})

    async def stream_chat(client_obj, model, messages, temperature=None,
                          max_tokens=None, reasoning_effort=None):
        yield "장면 본문"

    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *a, **k: FakeClient())
    monkeypatch.setattr(ai_panel.llm, "complete_chat", complete_chat)
    monkeypatch.setattr(ai_panel.llm, "stream_chat", stream_chat)

    response = client.post("/api/v1/ai/generate-parallel", json={
        "prompt_override": "병렬로 집필하라.", "worker_limit": 2,
    })

    assert response.status_code == 200, response.text
    assert planner_calls["n"] == 2  # 최대 1회 재시도
    text = response.text
    assert 'event: parallel_error' in text
    assert '"stage": "generation"' in text
    assert "ValidationError" in text  # 타입명 + 상세가 사용자에게 보인다

    db = _db(client)
    run = db.scalar(select(GenerationRun).where(
        GenerationRun.surface == "generate_parallel"
    ).order_by(GenerationRun.id.desc()))
    assert run is not None
    debug = (run.input_manifest_json or {}).get("planner_debug")
    assert debug and "scenes" in debug["parse_error"]["raw"]
    assert "validation errors" in debug["parse_error"]["detail"]
    assert run.status == "provider_error"
