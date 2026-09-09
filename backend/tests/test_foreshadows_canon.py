"""고도화 G-020~G-023 — 복선 CRUD·미회수 자동 주입·canon 검사 테스트."""
import json

import pytest
from sqlalchemy import select

from app.database import get_db
from app.models import Foreshadow
from tests.test_ai_generate_stream import (DEFAULT_CHUNKS, FakeAsyncOpenAI,
                                           _parse_sse)
from tests.test_bootstrap_api import _Message, _Response


@pytest.fixture()
def chapter(client):
    pid = client.post("/api/v1/projects", json={"title": "p"}).json()["id"]
    ch = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화"}).json()
    return client.get(f"/api/v1/chapters/{ch['id']}").json()


def _fs(client, pid, title, **kw):
    return client.post(f"/api/v1/projects/{pid}/foreshadows",
                       json={"title": title, **kw}).json()


def test_foreshadow_rejects_chapter_from_another_project(client):
    project_a = client.post("/api/v1/projects", json={"title": "A"}).json()["id"]
    project_b = client.post("/api/v1/projects", json={"title": "B"}).json()["id"]
    foreign_chapter = client.post(
        f"/api/v1/projects/{project_b}/chapters", json={"title": "B-1"}
    ).json()

    response = client.post(
        f"/api/v1/projects/{project_a}/foreshadows",
        json={"title": "외부 회차 참조", "planted_chapter_id": foreign_chapter["id"]},
    )

    assert response.status_code == 422


def test_foreshadow_reminder_handles_installed_foreshadow_without_chapters(client):
    pid = client.post("/api/v1/projects", json={"title": "회차 없는 프로젝트"}).json()["id"]
    foreshadow = _fs(client, pid, "아직 풀리지 않은 복선", status="설치")

    response = client.get(f"/api/v1/projects/{pid}/foreshadows/reminder")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "window": 5,
        "latest_chapter": None,
        "items": [{
            "id": foreshadow["id"],
            "title": "아직 풀리지 않은 복선",
            "content": None,
            "planted_chapter_id": None,
            "last_mentioned_chapter_id": None,
            "last_mentioned_chapter_title": None,
            "chapters_since_mentioned": None,
            "stale": True,
        }],
    }


def test_foreshadow_crud_and_status_filter(client, chapter):
    pid = chapter["project_id"]
    f1 = _fs(client, pid, "검의 진짜 주인", status="설치")
    f2 = _fs(client, pid, "예언의 조각", status="회수")
    f3 = _fs(client, pid, "그림자 조합 이중 계약", status="보류")

    rows = client.get(f"/api/v1/projects/{pid}/foreshadows").json()
    assert len(rows) == 3

    installed = client.get(
        f"/api/v1/projects/{pid}/foreshadows",
        params={"status_filter": "설치"}).json()
    assert [r["id"] for r in installed] == [f1["id"]]

    # 상태 변경: 설치 → 회수
    r = client.patch(f"/api/v1/foreshadows/{f1['id']}",
                     json={"status": "회수", "resolved_chapter_id": chapter["id"]})
    assert r.status_code == 200 and r.json()["status"] == "회수"
    # 잘못된 상태 → 422
    assert client.patch(f"/api/v1/foreshadows/{f1['id']}",
                        json={"status": "없음"}).status_code == 422
    # 존재하지 않는 회차 FK → 422
    assert client.patch(f"/api/v1/foreshadows/{f1['id']}",
                        json={"planted_chapter_id": 99999}).status_code == 422
    # 삭제
    assert client.delete(f"/api/v1/foreshadows/{f2['id']}").status_code == 204


def test_unresolved_foreshadows_auto_injected(client, monkeypatch, chapter):
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

    pid = chapter["project_id"]
    f1 = _fs(client, pid, "검의 진짜 주인", content="검은 다른 사람의 것이다",
             keywords=["검"])
    _fs(client, pid, "이미 회수된 복선", status="회수")

    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘",
        "context": {"chapter_id": chapter["id"], "auto_foreshadow": True}})
    assert resp.status_code == 200
    user_text = holder["client"].last_kwargs["messages"][-1]["content"]
    assert "[미회수 복선: 검의 진짜 주인]" in user_text
    assert "결론을 미리 풀지 마라" in user_text
    assert "이미 회수된 복선" not in user_text

    # SSE start 이벤트 투명성
    data = json.loads(dict(_parse_sse(resp.text))["start"])
    assert data["injected_foreshadows"] == [{"id": f1["id"], "title": "검의 진짜 주인"}]

    # 플래그 off
    client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘",
        "context": {"chapter_id": chapter["id"], "auto_foreshadow": False}})
    user_text = holder["client"].last_kwargs["messages"][-1]["content"]
    assert "[미회수 복선:" not in user_text


def test_canon_check_success(client, monkeypatch, chapter):
    from app.routers import quality as quality_router
    holder = {"calls": []}

    class _Completions:
        async def create(self, **kwargs):
            holder["calls"].append(kwargs)
            return _Response(json.dumps({
                "issues": [{"quote": "그는 어릴 때부터 검을 배웠다",
                            "reason": "캐릭터 설정: 검을 배운 적 없음",
                            "severity": "error"},
                           {"quote": "", "reason": "빈 발췌는 무시",
                            "severity": "warn"}]}, ensure_ascii=False))

    class _FakeClient:
        def __init__(self, base_url=None, api_key_encrypted=None):
            self.chat = type("NS", (), {"completions": _Completions()})()

    monkeypatch.setattr(quality_router.llm, "make_client",
                        lambda base_url, api_key_encrypted: _FakeClient())

    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m",
        "is_default": True}).json()
    client.put(f"/api/v1/chapters/{chapter['id']}/content",
               json={"content_md": "그는 어릴 때부터 검을 배웠다.", "expected_revision": 0})

    resp = client.post("/api/v1/canon-check", json={"chapter_id": chapter["id"]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["issues"]) == 1  # 빈 quote 필터링
    assert body["issues"][0]["severity"] == "error"
    for key, value in {"characters": 0, "lore": 0, "foreshadows": 0, "audience_known": 0}.items():
        assert body["checked_context"][key] == value
    assert "checked_input_revision" in body["checked_context"]
    assert "checked_input_hash" in body["checked_context"]
    # G-041 — 검사 이력 저장·재조회
    assert body["run_id"] > 0
    runs = client.get("/api/v1/canon-check/runs",
                      params={"chapter_id": chapter["id"]}).json()
    assert len(runs) == 1 and runs[0]["id"] == body["run_id"]


def test_canon_check_requires_default_endpoint(client, chapter):
    resp = client.post("/api/v1/canon-check", json={"chapter_id": chapter["id"]})
    assert resp.status_code == 400  # 엔드포인트 없음


def test_project_delete_cascades_foreshadows(client, chapter):
    """복선이 있어도 프로젝트 삭제가 FK 오류 없이 성공해야 한다(회귀 — Relationship 사례 동일)."""
    pid = chapter["project_id"]
    _fs(client, pid, "삭제 회귀 복선", status="설치")
    r = client.delete(f"/api/v1/projects/{pid}")
    assert r.status_code in (204, 200)
    db = next(iter(client.app.dependency_overrides[get_db]()))
    assert db.scalars(select(Foreshadow).where(Foreshadow.project_id == pid)).all() == []


def test_project_delete_cascades_canon_and_quality_runs(client, chapter, monkeypatch):
    """canon/quality 이력이 있어도 프로젝트 삭제가 FK 오류 없이 성공(회귀)."""
    from app.models import CanonRun, QualityCheck
    db = next(iter(client.app.dependency_overrides[get_db]()))
    db.add(CanonRun(chapter_id=chapter["id"], model="m", issues_json=[]))
    db.add(QualityCheck(chapter_id=chapter["id"], score=80, content_hash="h"))
    db.commit()
    r = client.delete(f"/api/v1/projects/{chapter['project_id']}")
    assert r.status_code in (204, 200)



def test_canon_checked_context_preserves_input_revision_and_hash(client, monkeypatch, chapter):
    import hashlib

    from app.database import get_db
    from app.models import Chapter
    from app.routers import quality as quality_router

    holder = {"calls": []}

    class _Completions:
        async def create(self, **kwargs):
            holder["calls"].append(kwargs)
            db = next(iter(client.app.dependency_overrides[get_db]()))
            row = db.get(Chapter, chapter["id"])
            row.content_md = "provider 중 바뀐 본문"
            row.revision += 1
            db.commit()
            return _Response(json.dumps({"issues": []}, ensure_ascii=False))

    class _FakeClient:
        def __init__(self, base_url=None, api_key_encrypted=None):
            self.chat = type("NS", (), {"completions": _Completions()})()

    monkeypatch.setattr(
        quality_router.llm,
        "make_client",
        lambda base_url, api_key_encrypted: _FakeClient(),
    )
    client.post(
        "/api/v1/ai/endpoints",
        json={"name": "e", "base_url": "http://x/v1", "default_model": "m", "is_default": True},
    )
    client.put(
        f"/api/v1/chapters/{chapter['id']}/content",
        json={"content_md": "검사 전 원본", "expected_revision": 0},
    )
    before = client.get(f"/api/v1/chapters/{chapter['id']}").json()
    expected_hash = hashlib.sha256("검사 전 원본".encode("utf-8")).hexdigest()

    resp = client.post(
        "/api/v1/canon-check",
        json={"chapter_id": chapter["id"], "expected_revision": before["revision"]},
    )
    assert resp.status_code == 200, resp.text
    checked = resp.json()["checked_context"]
    assert checked["checked_input_revision"] == before["revision"]
    assert checked["checked_input_hash"] == expected_hash

    runs = client.get(
        "/api/v1/canon-check/runs", params={"chapter_id": chapter["id"]}
    ).json()
    assert runs[0]["context_json"]["checked_input_revision"] == before["revision"]
    assert runs[0]["context_json"]["checked_input_hash"] == expected_hash
    sent_user = holder["calls"][0]["messages"][-1]["content"]
    assert "검사 전 원본" in sent_user
    assert "provider 중 바뀐 본문" not in sent_user


def test_canon_approved_foreshadow_permission_does_not_mutate_rows(client, monkeypatch, chapter):
    from app.routers import quality as quality_router

    holder = {"calls": []}

    class _Completions:
        async def create(self, **kwargs):
            holder["calls"].append(kwargs)
            return _Response(json.dumps({"issues": []}, ensure_ascii=False))

    class _FakeClient:
        def __init__(self, base_url=None, api_key_encrypted=None):
            self.chat = type("NS", (), {"completions": _Completions()})()

    monkeypatch.setattr(
        quality_router.llm,
        "make_client",
        lambda base_url, api_key_encrypted: _FakeClient(),
    )
    client.post(
        "/api/v1/ai/endpoints",
        json={"name": "e", "base_url": "http://x/v1", "default_model": "m", "is_default": True},
    )
    pid = chapter["project_id"]
    fs = _fs(
        client, pid, "검의 진짜 주인",
        content="검은 타인의 것이다", status="설치", audience_knows=False,
    )

    resp = client.post(
        "/api/v1/canon-check",
        json={
            "chapter_id": chapter["id"],
            "episode_purpose": "series_finale",
            "approved_foreshadow_ids": [fs["id"]],
        },
    )
    assert resp.status_code == 200, resp.text
    user_text = holder["calls"][0]["messages"][-1]["content"]
    system_text = holder["calls"][0]["messages"][0]["content"]
    assert "[최종화 목적]" in user_text
    assert "[이번 요청에서 회수/공개 허용된 복선: 검의 진짜 주인]" in user_text
    assert "그 공개 자체만으로 미회수 복선 오류로 판정하지 않는다" in system_text
    checked = resp.json()["checked_context"]
    assert checked["approved_foreshadow_ids"] == [fs["id"]]
    after = client.get(f"/api/v1/projects/{pid}/foreshadows").json()[0]
    assert after["status"] == "설치"
    assert after["audience_knows"] is False
    assert after["resolved_chapter_id"] is None


def _capture_canon_prompt(client, monkeypatch, payload):
    from app.routers import quality as quality_router

    holder = {"calls": []}

    class _Completions:
        async def create(self, **kwargs):
            holder["calls"].append(kwargs)
            return _Response(json.dumps({"issues": []}, ensure_ascii=False))

    class _FakeClient:
        def __init__(self, base_url=None, api_key_encrypted=None):
            self.chat = type("NS", (), {"completions": _Completions()})()

    monkeypatch.setattr(
        quality_router.llm,
        "make_client",
        lambda base_url, api_key_encrypted: _FakeClient(),
    )
    client.post(
        "/api/v1/ai/endpoints",
        json={"name": "e", "base_url": "http://x/v1", "default_model": "m", "is_default": True},
    )
    resp = client.post("/api/v1/canon-check", json=payload)
    assert resp.status_code == 200, resp.text
    return holder["calls"][0]["messages"][-1]["content"], resp.json()["checked_context"]


def test_canon_prompt_labels_future_planted_rows_by_time_not_audience(client, monkeypatch):
    pid = client.post("/api/v1/projects", json={"title": "P"}).json()["id"]
    ch1 = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화", "sort_order": 1}).json()
    ch2 = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "2화", "sort_order": 2}).json()
    client.put(
        f"/api/v1/chapters/{ch1['id']}/content",
        json={"content_md": "현재 회차 본문", "expected_revision": 0},
    )
    future_secret = _fs(
        client, pid, "미래에 처음 설치될 문",
        content="2화에서 처음 등장할 문은 아직 현재 사실이 아니다",
        status="보류", audience_knows=False, planted_chapter_id=ch2["id"],
    )
    future_public = _fs(
        client, pid, "미래 공개 계획",
        content="독자가 알게 될 계획도 현재 회차 사실은 아니다",
        status="설치", audience_knows=True, planted_chapter_id=ch2["id"],
    )
    client.patch(f"/api/v1/foreshadows/{future_public['id']}", json={"audience_knows": True})

    user_text, context = _capture_canon_prompt(
        client, monkeypatch, {"chapter_id": ch1["id"]},
    )

    assert "[미래 계획 복선: 미래에 처음 설치될 문 — 현재 사실 아님]" in user_text
    assert "[미래 계획 복선: 미래 공개 계획 — 현재 사실 아님]" in user_text
    assert "현재 인물 지식·세계 사실로 단정하지 마라" in user_text
    assert "[미회수 복선 —" not in user_text
    assert "[독자가 이미 알게 된 사실" not in user_text
    assert context["included_foreshadow_ids"] == [future_secret["id"], future_public["id"]]
    assert context["future_reference_foreshadow_ids"] == [future_secret["id"], future_public["id"]]
    assert context["foreshadows"] == 1
    assert context["audience_known"] == 1


def test_canon_prompt_keeps_future_resolution_as_current_record_plan(client, monkeypatch):
    pid = client.post("/api/v1/projects", json={"title": "P"}).json()["id"]
    ch1 = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화", "sort_order": 1}).json()
    ch2 = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "2화", "sort_order": 2}).json()
    client.put(
        f"/api/v1/chapters/{ch1['id']}/content",
        json={"content_md": "현재 회차 본문", "expected_revision": 0},
    )
    planned_resolution = _fs(
        client, pid, "이미 설치된 검의 주인",
        content="검의 주인은 아직 본문에서 밝혀지지 않았다",
        status="설치", audience_knows=False,
        planted_chapter_id=ch1["id"], resolved_chapter_id=ch2["id"],
    )
    public_current = _fs(
        client, pid, "이미 공개된 혈통",
        content="독자는 혈통을 이미 안다",
        status="설치", audience_knows=True, planted_chapter_id=ch1["id"],
    )
    client.patch(f"/api/v1/foreshadows/{public_current['id']}", json={"audience_knows": True})

    user_text, context = _capture_canon_prompt(
        client, monkeypatch, {"chapter_id": ch1["id"]},
    )

    assert "[미래 계획 복선: 이미 설치된 검의 주인 — 현재 사실 아님]" not in user_text
    assert "[미회수 복선 —" in user_text
    assert "이미 설치된 검의 주인" in user_text
    assert "미래 회수 계획은 현재 사실이나 현재 인물 지식으로 단정하지 마라" in user_text
    assert "[독자가 이미 알게 된 사실" in user_text
    assert "이미 공개된 혈통" in user_text
    assert context["included_foreshadow_ids"] == [planned_resolution["id"], public_current["id"]]
    assert context["future_reference_foreshadow_ids"] == [planned_resolution["id"]]
    assert context["foreshadows"] == 1
    assert context["audience_known"] == 1


def test_canon_approved_future_plan_is_permission_without_state_mutation(client, monkeypatch):
    pid = client.post("/api/v1/projects", json={"title": "P"}).json()["id"]
    ch1 = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화", "sort_order": 1}).json()
    ch2 = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "2화", "sort_order": 2}).json()
    client.put(
        f"/api/v1/chapters/{ch1['id']}/content",
        json={"content_md": "현재 회차 본문", "expected_revision": 0},
    )
    approved_future = _fs(
        client, pid, "승인된 미래 문",
        content="작가가 이번 요청에서만 당겨 쓸 수 있다",
        status="보류", audience_knows=False, planted_chapter_id=ch2["id"],
    )

    user_text, context = _capture_canon_prompt(
        client, monkeypatch, {
            "chapter_id": ch1["id"],
            "approved_foreshadow_ids": [approved_future["id"]],
        },
    )

    assert "[이번 요청에서 회수/공개 허용된 복선: 승인된 미래 문]" in user_text
    assert "이번 원고에서 자연스럽게 공개하거나 회수할 수 있다" in user_text
    assert "기존 현재 사실로 단정하지 마라" in user_text
    assert "반드시" not in user_text[user_text.find("승인된 미래 문"):user_text.find("승인된 미래 문") + 300]
    assert context["approved_foreshadow_ids"] == [approved_future["id"]]
    assert context["future_reference_foreshadow_ids"] == [approved_future["id"]]
    after = client.get(f"/api/v1/projects/{pid}/foreshadows").json()[0]
    assert after["status"] == "보류"
    assert after["audience_knows"] is False
    assert after["resolved_chapter_id"] is None
