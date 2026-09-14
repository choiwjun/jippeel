"""agy(Antigravity CLI) 감수 라우팅 — GPT 초안 + Gemini 감수 교차 검수 계약.

JIPPEEL_REVIEW_PROVIDER=agy일 때 감수만 agy subprocess로 라우팅되고
생성은 고정 GPT OAuth 브릿지를 유지한다. 테스트의 agy 호출은
monkeypatch·파서 단위 테스트로 대체해 실제 agy·Google 호출이 없다.
subprocess 실행 경로 자체는 격리 가드가 차단하므로 운영 전 수동 스모크로 검증한다.
"""

import json

from app.routers import ai_panel
from app.services import agy_review


def test_flatten_messages_marks_roles():
    messages = [
        {"role": "system", "content": "지시"},
        {"role": "user", "content": "본문"},
    ]
    out = agy_review.flatten_messages(messages)
    assert out == "[시스템 지시]\n지시\n\n[작업]\n본문"


def test_agy_config_gated_by_env(monkeypatch):
    monkeypatch.delenv("JIPPEEL_REVIEW_PROVIDER", raising=False)
    assert agy_review.get_agy_review_config() is None
    monkeypatch.setenv("JIPPEEL_REVIEW_PROVIDER", "agy")
    monkeypatch.setenv("JIPPEEL_AGY_MODEL", "gemini-test")
    cfg = agy_review.get_agy_review_config()
    assert cfg is not None and cfg.model == "gemini-test"
    assert cfg.timeout_s > 0


def test_agy_parse_event_tolerates_bad_lines():
    assert agy_review._agy_parse_event(b"not json") == {}
    assert agy_review._agy_parse_event(b'"str"') == {}
    ev = agy_review._agy_parse_event(
        json.dumps({"event": "step_update", "step_update": {}}).encode())
    assert ev["event"] == "step_update"


def test_agy_event_text_delta_filters_agent_response():
    assert agy_review._agy_event_text_delta({
        "event": "step_update",
        "step_update": {"step_type": "agent_response", "text_delta": "본문"},
    }) == "본문"
    # 다른 step_type의 text_delta는 본문 델타가 아니다.
    assert agy_review._agy_event_text_delta({
        "event": "step_update",
        "step_update": {"step_type": "user_input", "text_delta": "무시"},
    }) is None
    assert agy_review._agy_event_text_delta({"event": "init"}) is None


def test_agy_result_error_contract():
    assert agy_review._agy_result_error(
        {"event": "result", "result": {"status": "SUCCESS"}}) is None
    assert agy_review._agy_result_error(
        {"event": "result",
         "result": {"status": "ERROR", "error": "quota exceeded"}}
    ) == "quota exceeded"
    assert agy_review._agy_result_error({"event": "step_update"}) is None


def _parse_sse(text):
    events = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        ev, data = None, None
        for line in block.splitlines():
            if line.startswith("event:"):
                ev = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = line.split(":", 1)[1].strip()
        if ev:
            events.append((ev, data))
    return events


def _enable_agy(monkeypatch, deltas, calls):
    """agy 라우팅 활성화 + stream_agy_chat를 fake로 대체."""
    cfg = agy_review.AgyReviewConfig(bin_path="agy", model="gemini-test", timeout_s=60)
    monkeypatch.setattr(agy_review, "get_agy_review_config", lambda: cfg)

    async def fake_stream(cfg_arg, model, messages):
        calls.append({"model": model, "messages": messages})
        for d in deltas:
            yield d

    monkeypatch.setattr(agy_review, "stream_agy_chat", fake_stream)


def test_generate_review_routes_to_agy(client, monkeypatch):
    """/ai/generate: 초안은 브릿지(llm.stream_chat), 감수는 agy로 라우팅."""
    async def draft_stream(client_obj, model, messages, **kwargs):
        for d in ("초안", " 원고"):
            yield d

    agy_calls: list = []
    _enable_agy(monkeypatch, ["[감수] 지적입니다\n", "[수정본]\n수정 원고"], agy_calls)
    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *a, **k: object())
    monkeypatch.setattr(ai_panel.llm, "stream_chat", draft_stream)

    resp = client.post("/api/v1/ai/generate", json={
        "prompt_override": "써줘",
        "review": {"reasoning_effort": "high"},
    })
    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.text)
    kinds = [e for e, _ in events]
    assert "review_start" in kinds and "review" in kinds and "refined" in kinds

    start = json.loads(next(d for e, d in events if e == "review_start"))
    assert start["provider"] == "antigravity-agy"
    assert start["model"] == "gemini-test"

    review_text = "".join(json.loads(d)["delta"] for e, d in events if e == "review")
    refined_text = "".join(json.loads(d)["delta"] for e, d in events if e == "refined")
    assert "지적입니다" in review_text
    assert "수정 원고" in refined_text
    # 감수 프롬프트에 초안이 포함된다.
    assert any("초안 원고" in m["content"] for c in agy_calls
               for m in c["messages"] if m["role"] == "user")


def test_review_endpoint_routes_to_agy(client, monkeypatch):
    """독립 /ai/review도 같은 라우팅 — 생성 provider를 거치지 않는다."""
    agy_calls: list = []
    _enable_agy(monkeypatch, ["[감수] 검토\n", "[수정본]\n정본"], agy_calls)
    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *a, **k: object())

    resp = client.post("/api/v1/ai/review", json={"draft": "초안 본문"})
    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.text)
    start = json.loads(next(d for e, d in events if e == "review_start"))
    assert start["provider"] == "antigravity-agy"
    refined = "".join(json.loads(d)["delta"] for e, d in events if e == "refined")
    assert "정본" in refined
    assert len(agy_calls) == 1


def test_generate_review_agy_failure_keeps_draft(client, monkeypatch):
    """agy 감수 실패는 review_error로만 보고하고 초안 스트림은 유지된다."""
    async def draft_stream(client_obj, model, messages, **kwargs):
        yield "초안 원고"

    cfg = agy_review.AgyReviewConfig(bin_path="agy", model="gemini-test", timeout_s=60)
    monkeypatch.setattr(agy_review, "get_agy_review_config", lambda: cfg)

    async def failing_stream(cfg_arg, model, messages):
        raise agy_review.AgyReviewError("agy 실행 실패")
        yield  # pragma: no cover — async generator 형태 유지

    monkeypatch.setattr(agy_review, "stream_agy_chat", failing_stream)
    monkeypatch.setattr(ai_panel.llm, "make_client", lambda *a, **k: object())
    monkeypatch.setattr(ai_panel.llm, "stream_chat", draft_stream)

    resp = client.post("/api/v1/ai/generate", json={
        "prompt_override": "써줘",
        "review": {},
    })
    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.text)
    kinds = [e for e, _ in events]
    assert "review_error" in kinds and "done" in kinds
    draft = "".join(json.loads(d)["delta"] for e, d in events if e == "message")
    assert draft == "초안 원고"
