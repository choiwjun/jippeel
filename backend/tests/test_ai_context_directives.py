import json

import pytest

from tests.test_ai_generate_stream import _parse_sse, fake_llm, parallel_llm


def _endpoint(client):
    return client.post(
        "/api/v1/ai/endpoints",
        json={"name": "e", "base_url": "http://x/v1", "default_model": "m"},
    ).json()


def _base_brief(**extra):
    data = {
        "emotion_goal": "불안을 끝내는 안도감",
        "core_events": ["황궁 지하 문을 연다"],
        "character_choices": ["주인공은 복수보다 구출을 택한다"],
        "cost": "왕좌를 포기한다",
        "prohibitions": ["새 흑막을 만들지 않는다"],
    }
    data.update(extra)
    return data


def _project_chapter(client, title, body="본문"):
    pid = client.post("/api/v1/projects", json={"title": title}).json()["id"]
    chapter = client.post(
        f"/api/v1/projects/{pid}/chapters",
        json={"title": "1화", "sort_order": 1},
    ).json()
    client.put(
        f"/api/v1/chapters/{chapter['id']}/content",
        json={"content_md": body, "expected_revision": 0},
    )
    return pid, client.get(f"/api/v1/chapters/{chapter['id']}").json()


def test_serial_brief_requires_next_hook(client, fake_llm):
    ep = _endpoint(client)
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"],
        "prompt_override": "이어 써줘",
        "context": {"episode_purpose": "serial", "brief": _base_brief()},
    })
    assert resp.status_code == 422


def test_series_finale_brief_accepts_ending_intent_without_next_hook(client, fake_llm):
    ep = _endpoint(client)
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"],
        "prompt_override": "완결 장면을 써줘",
        "context": {
            "episode_purpose": "series_finale",
            "brief": _base_brief(ending_intent="주인공이 선택의 대가를 받아들이고 시리즈 갈등을 닫는다"),
        },
    })
    assert resp.status_code == 200
    user_text = fake_llm["client"].last_kwargs["messages"][-1]["content"]
    assert "결말 의도" in user_text
    assert "주인공이 선택의 대가" in user_text


@pytest.mark.parametrize("purpose, must_contain, must_not_contain", [
    ("serial", "연재화 목적", "무조건 갈등을 다 풀지 마라"),
    ("volume_end", "권말 목적", "훅이 없어도 장면의 긴장이 완전히 풀리기 전에 끝낸다"),
    ("series_finale", "최종화 목적", "갈등을 다 풀지 마라"),
])
def test_generation_system_prompt_is_purpose_aware(client, fake_llm, purpose, must_contain, must_not_contain):
    ep = _endpoint(client)
    context = {"episode_purpose": purpose}
    if purpose == "serial":
        context["brief"] = _base_brief(next_hook="문밖의 발소리로 넘긴다")
    elif purpose == "volume_end":
        context["brief"] = _base_brief(ending_intent="권의 감정선을 닫고 다음 권 질문만 남긴다")
    else:
        context["brief"] = _base_brief(ending_intent="시리즈 핵심 갈등을 닫는다")
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "써줘", "context": context,
    })
    assert resp.status_code == 200
    sys_text = fake_llm["client"].last_kwargs["messages"][0]["content"]
    assert must_contain in sys_text
    assert must_not_contain not in sys_text
    assert "최종화 문학성 점수" not in sys_text


def test_approved_foreshadow_block_allows_this_request_only(client, fake_llm):
    ep = _endpoint(client)
    pid, chapter = _project_chapter(client, "P")
    fs = client.post(f"/api/v1/projects/{pid}/foreshadows", json={
        "title": "검의 진짜 주인", "content": "검은 타인의 것이다", "status": "설치",
    }).json()
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"],
        "prompt_override": "이번 화에서 검의 진실을 밝혀줘",
        "context": {
            "project_id": pid,
            "chapter_id": chapter["id"],
            "approved_foreshadow_ids": [fs["id"]],
            "auto_foreshadow": False,
        },
    })
    assert resp.status_code == 200
    user_text = fake_llm["client"].last_kwargs["messages"][-1]["content"]
    assert "[이번 요청에서 회수/공개 허용된 복선: 검의 진짜 주인]" in user_text
    assert "상태값은 자동 변경하지 마라" in user_text
    assert user_text.count("검의 진짜 주인") == 1
    start = json.loads(dict(_parse_sse(resp.text))["start"])
    assert start["context_metadata"]["approved_foreshadow_ids"] == [fs["id"]]
    assert start["context_metadata"]["included_foreshadow_ids"] == [fs["id"]]
    after = client.get(f"/api/v1/projects/{pid}/foreshadows").json()[0]
    assert after["status"] == "설치"
    assert after["audience_knows"] is False


def test_approved_foreshadow_dedupes_auto_block(client, fake_llm):
    ep = _endpoint(client)
    pid, chapter = _project_chapter(client, "P")
    fs = client.post(f"/api/v1/projects/{pid}/foreshadows", json={
        "title": "검의 진짜 주인", "content": "검은 타인의 것이다", "status": "설치",
    }).json()
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"],
        "prompt_override": "검의 진실",
        "context": {
            "project_id": pid,
            "chapter_id": chapter["id"],
            "approved_foreshadow_ids": [fs["id"]],
            "auto_foreshadow": True,
        },
    })
    assert resp.status_code == 200
    user_text = fake_llm["client"].last_kwargs["messages"][-1]["content"]
    assert user_text.count("검의 진짜 주인") == 1
    assert "[미회수 복선: 검의 진짜 주인" not in user_text


def test_future_resolved_chapter_keeps_planted_clue_current_record(client, fake_llm):
    ep = _endpoint(client)
    pid = client.post("/api/v1/projects", json={"title": "P"}).json()["id"]
    ch1 = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화", "sort_order": 1}).json()
    ch2 = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "2화", "sort_order": 2}).json()
    fs = client.post(f"/api/v1/projects/{pid}/foreshadows", json={
        "title": "검의 진짜 주인",
        "content": "검은 타인의 것이다",
        "status": "설치",
        "planted_chapter_id": ch1["id"],
        "resolved_chapter_id": ch2["id"],
    }).json()
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "검",
        "context": {"project_id": pid, "chapter_id": ch1["id"], "auto_foreshadow": True},
    })
    assert resp.status_code == 200
    user_text = fake_llm["client"].last_kwargs["messages"][-1]["content"]
    assert "[미회수 복선: 검의 진짜 주인]" in user_text
    assert "기록: 현재 기록" in user_text
    assert "미래 회수 계획" in user_text
    assert "[미래 계획 복선: 검의 진짜 주인 — 현재 사실 아님]" not in user_text
    start = json.loads(dict(_parse_sse(resp.text))["start"])
    assert start["context_metadata"]["future_reference_foreshadow_ids"] == [fs["id"]]


def test_wrong_project_approved_foreshadow_rejected_before_llm(client, fake_llm):
    ep = _endpoint(client)
    pid_a, chapter_a = _project_chapter(client, "A")
    pid_b, _chapter_b = _project_chapter(client, "B")
    fs_b = client.post(f"/api/v1/projects/{pid_b}/foreshadows", json={"title": "타작품 복선"}).json()
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "써줘",
        "context": {"project_id": pid_a, "chapter_id": chapter_a["id"], "approved_foreshadow_ids": [fs_b["id"]]},
    })
    assert resp.status_code == 422
    assert fake_llm["client"].last_kwargs is None or "타작품 복선" not in str(fake_llm["client"].last_kwargs)


def test_single_review_receives_same_purpose_directive(client, fake_llm):
    ep = _endpoint(client)
    fake_llm["client"].set_chunks(["[감수]\n- 목적에 맞다", "[수정본]\n수정본"])
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"],
        "prompt_override": "완결 장면",
        "context": {"episode_purpose": "series_finale"},
        "review": {},
    })
    assert resp.status_code == 200
    messages = fake_llm["client"].last_kwargs["messages"]
    assert "[최종화 목적]" in messages[0]["content"]
    assert "[초안 원고]" in messages[-1]["content"]


def test_parallel_planner_workers_and_reviewer_receive_purpose_directive(client, parallel_llm):
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "medium", "base_url": "http://x/v1", "default_model": "medium-model",
        "reasoning_effort": "medium",
    }).json()
    resp = client.post("/api/v1/ai/generate-parallel", json={
        "endpoint_id": ep["id"],
        "prompt_override": "권말 장면을 나눠 써줘",
        "worker_limit": 2,
        "context": {"episode_purpose": "volume_end"},
        "review": {"reasoning_effort": "xhigh"},
    })
    assert resp.status_code == 200, resp.text
    planner_messages = parallel_llm["complete_calls"][0]["messages"]
    worker_messages = parallel_llm["complete_calls"][1]["messages"]
    review_messages = parallel_llm["stream_calls"][-1]["messages"]
    assert any("[권말 목적]" in m["content"] for m in planner_messages)
    assert any("[권말 목적]" in m["content"] for m in worker_messages)
    assert any("[권말 목적]" in m["content"] for m in review_messages)


def test_generation_unapproved_public_foreshadow_is_reference_not_secret(client, fake_llm):
    ep = _endpoint(client)
    pid, chapter = _project_chapter(client, "P")
    public_row = client.post(f"/api/v1/projects/{pid}/foreshadows", json={
        "title": "이미 공개된 혈통",
        "content": "독자는 주인공의 혈통을 이미 안다",
        "status": "설치",
        "audience_knows": True,
    }).json()
    client.patch(f"/api/v1/foreshadows/{public_row['id']}", json={"audience_knows": True})
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"],
        "prompt_override": "혈통을 언급해줘",
        "context": {"project_id": pid, "chapter_id": chapter["id"], "auto_foreshadow": True},
    })
    assert resp.status_code == 200
    user_text = fake_llm["client"].last_kwargs["messages"][-1]["content"]
    assert "[독자가 이미 알게 된 복선 정보: 이미 공개된 혈통]" in user_text
    assert "이미 공개된 정보는 현재 사실로 참고할 수 있다" in user_text
    assert "작가 승인 없이 결론·정체·회수를 공개하지 마라" not in user_text
    assert "새로운 회수·반전은 작가 승인 없이 만들지 마라" in user_text
