"""레퍼런스 스타일 분석 — 결정적 지표 + 프로파일 초안 엔드포인트.

지표 측정은 순수 Python이라 격리 테스트 가능. LLM 합성 호출은
complete_chat을 fake로 교체한다 — 실제 provider 호출 없음.
"""
from __future__ import annotations

import pytest

from app.services import llm, style_analysis


def _sample_dialogue_heavy() -> str:
    paras = [
        '"문을 닫지 마세요." 그가 말했다.',
        '나는 걸음을 멈췄다. 심장이 빠르게 뛰기 시작했다.',
        '"누구세요?"',
        '그는 대답하지 않은 채 창가로 걸어갔다. 비가 유리를 두드리며 흘러내렸다.',
        '"왜 나를 부른 거죠."',
        '그는 천천히 고개를 돌렸다. 그의 눈빛이 어둠 속에서 흔들렸다.',
    ] * 8
    return "\n".join(paras)


def _sample_terse() -> str:
    paras = [
        '비가 내렸다. 장례식장은 조용했다.',
        '그는 우산을 접었다. 물이 떨어졌다.',
        '아무도 말하지 않았다.',
        '시간이 멈췄다.',
    ] * 8
    return "\n".join(paras)


def test_analyze_text_basic_metrics():
    m = style_analysis.analyze_text(_sample_dialogue_heavy())
    d = m.to_dict()
    assert d["sentences"] > 0 and d["paragraphs"] > 0
    assert d["sent_len_avg"] > 0
    # 대화문 시작 단락이 절반 가까이 된다.
    assert d["dialogue_ratio"] > 0.3
    # 1인칭 마커(나는)가 3인칭보다 많지는 않지만 둘 다 집계된다.
    assert m.first_person_hits > 0 and m.third_person_hits > 0


def test_analyze_text_terse_style():
    m = style_analysis.analyze_text(_sample_terse())
    d = m.to_dict()
    assert d["sent_len_avg"] < 25
    assert d["short_sentence_ratio"] > 0.2
    assert "connective_ending_ratio" in d
    assert d["sentences_per_paragraph"] > 0


def test_build_analysis_messages_shape():
    m = style_analysis.analyze_text(_sample_terse())
    msgs = style_analysis.build_analysis_messages(_sample_terse(), m)
    assert msgs[0]["role"] == "system" and "문체 프로파일" in msgs[0]["content"]
    assert "[측정 지표]" in msgs[1]["content"] and "[원문 샘플]" in msgs[1]["content"]


class _FakeClient:
    async def close(self):
        pass


def test_style_analysis_endpoint(client, monkeypatch):
    captured: dict = {}

    async def fake_complete(client_, model, messages, **kwargs):
        captured["messages"] = messages
        captured["model"] = model
        return "- 문장은 짧게 유지한다\n- 대화 사이에 행동 묘사를 끼운다"

    monkeypatch.setattr(llm, "make_client", lambda *a, **k: _FakeClient())
    monkeypatch.setattr(llm, "complete_chat", fake_complete)

    project = client.post("/api/v1/projects", json={"title": "p"}).json()
    res = client.post(
        f"/api/v1/projects/{project['id']}/style-analysis",
        json={"text": _sample_dialogue_heavy()})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["metrics"]["sentences"] > 0
    assert "문장은 짧게" in body["profile_draft"]
    # LLM에 지표와 원문이 함께 전달됐다.
    user_msg = captured["messages"][-1]["content"]
    assert "[측정 지표]" in user_msg and "문을 닫지 마세요" in user_msg
    # 저장되지 않는다 — style_profile은 작가가 PATCH로만 적용한다.
    assert client.get(f"/api/v1/projects/{project['id']}").json()["style_profile"] is None


def test_style_analysis_requires_200_chars(client, monkeypatch):
    monkeypatch.setattr(llm, "make_client", lambda *a, **k: _FakeClient())
    project = client.post("/api/v1/projects", json={"title": "p"}).json()
    res = client.post(
        f"/api/v1/projects/{project['id']}/style-analysis",
        json={"text": "짧은 텍스트"})
    assert res.status_code == 422
