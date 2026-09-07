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
    assert body["checked_context"] == {"characters": 0, "lore": 0,
                                       "foreshadows": 0, "audience_known": 0}
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
