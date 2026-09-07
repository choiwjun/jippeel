"""고도화 v2 테스트 — 권 개요(G-050)·독자 인지(G-045)·문체 프로파일(G-040)
·장면 조립(G-013)·품질 이력(G-041)·AI 사용량(G-060)·복선 추출(G-046)."""
import json

import pytest
from sqlalchemy import select

from app.database import get_db
from app.models import AiUsage, Foreshadow, QualityCheck
from tests.test_ai_generate_stream import (DEFAULT_CHUNKS, FakeAsyncOpenAI,
                                           _parse_sse)
from tests.test_bootstrap_api import _Response, fake_llm  # noqa: F401 — fixture 재노출


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
               json={"content_md": "본문", "expected_revision": 0})
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
    assert client.put(f"/api/v1/chapters/{cid}/content_from_scenes", json={}).status_code == 422

    s2 = client.post(f"/api/v1/chapters/{cid}/scenes", json={
        "title": "후반", "content_md": "두 번째 장면.", "sort_order": 2}).json()
    s1 = client.post(f"/api/v1/chapters/{cid}/scenes", json={
        "title": "전반", "content_md": "첫 번째 장면.", "sort_order": 1}).json()

    r = client.put(f"/api/v1/chapters/{cid}/content_from_scenes", json={"expected_revision": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["content_md"] == "첫 번째 장면.\n\n두 번째 장면."
    assert body["word_count_cache"] > 0


# ---------- G-041 품질 이력 ----------
def test_quality_record_history_dedup(client, project, chapter):
    cid = chapter["id"]
    client.put(f"/api/v1/chapters/{cid}/content", json={"content_md": "「비켜라.」\n\n순간, 칼이 빠졌다.", "expected_revision": 0})
    r1 = client.get(f"/api/v1/chapters/{cid}/quality").json()
    assert r1["recorded"] is True
    # 같은 본문 재조회 — 중복 기록 스킵
    r2 = client.get(f"/api/v1/chapters/{cid}/quality").json()
    assert r2["recorded"] is False
    # 본문 변경 — 새 기록
    client.put(f"/api/v1/chapters/{cid}/content", json={"content_md": "「비켜라.」\n\n순간, 칼이 빠졌다. 소리가 들려왔다.", "expected_revision": 1})
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
               json={"content_md": "검이 스스로 그를 향했다.", "expected_revision": 0})

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


# ---------- 부트스트랩 권 개요 동시 생성 ----------
def test_bootstrap_fallback_creates_volume_notes(client, project):
    """use_ai=false 폴백에서도 권 개요(개요·감정 곡선·고봉)가 함께 생성된다."""
    r = client.post("/api/v1/projects/bootstrap", json={
        "genre": "판타지", "volume_count": 2, "chapters_per_volume": 3, "use_ai": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["volume_note_count"] == 2
    notes = client.get(f"/api/v1/projects/{body['project_id']}/volume-notes").json()
    assert len(notes) == 2
    assert all(n["overview"] and n["emotion_curve"] and n["climax_note"] for n in notes)


def test_bootstrap_ai_outline_volume_notes_persisted(client, fake_llm):
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "기본", "base_url": "http://x/v1", "default_model": "test-model",
        "is_default": True}).json()
    """콜 2(목차)가 권 개요 필드를 반환하면 volume_notes로 저장된다."""
    from tests.test_bootstrap_api import (enqueue_success, fake_llm as _fl,  # noqa: F811
                                          _good_outline)
    outline = _good_outline()
    outline["volumes"][0]["overview"] = "1권 개요 텍스트"
    outline["volumes"][0]["emotion_curve"] = "3화 고조 4화 완충"
    outline["volumes"][0]["climax_note"] = "결전"
    enqueue_success(fake_llm, outline=outline)
    r = client.post("/api/v1/projects/bootstrap", json={
        "genre": "무협", "volume_count": 2, "chapters_per_volume": 3})
    assert r.status_code == 200
    # 권마다 노트가 생성되고(2권), 콜 2가 준 개요 필드가 저장된다
    assert r.json()["volume_note_count"] == 2
    notes = client.get(
        f"/api/v1/projects/{r.json()['project_id']}/volume-notes").json()
    assert notes[0]["overview"] == "1권 개요 텍스트"


# ---------- G-047 복선 키워드 본문 매칭 ----------
def test_foreshadow_match_endpoint(client, project, chapter):
    pid = project["id"]
    f1 = client.post(f"/api/v1/projects/{pid}/foreshadows", json={
        "title": "검의 진짜 주인", "keywords": ["검의 주인"], "status": "설치"}).json()
    f2 = client.post(f"/api/v1/projects/{pid}/foreshadows", json={
        "title": "예언의 조각", "keywords": ["예언"], "status": "설치"}).json()
    client.put(f"/api/v1/chapters/{chapter['id']}/content", json={
        "content_md": "검이 그의 손에서 울렸다. 검의 주인은 아직 다른 곳에 있다.", "expected_revision": 0})

    matched = client.get(f"/api/v1/projects/{pid}/foreshadows/match",
                         params={"chapter_id": chapter["id"]}).json()
    ids = {m["id"] for m in matched}
    assert f1["id"] in ids and f2["id"] not in ids
    hit = next(m for m in matched if m["id"] == f1["id"])
    assert set(hit["matched_terms"]) == {"검의 주인"}  # 제목은 본문에 미등장

    # 존재하지 않는 회차 → 404
    assert client.get(f"/api/v1/projects/{pid}/foreshadows/match",
                      params={"chapter_id": 99999}).status_code == 404


# ---------- G-070 시맨틱 로어 하이브리드 ----------
def test_semantic_hybrid_catches_morphological_variant(client, monkeypatch, project, chapter):
    """키워드 미등장 + 2-gram 유사도만으로 매칭되는 케이스 — v1은 놓치고 v2는 잡는다."""
    from app.services import semantic
    # 단위: 순수 함수 검증
    assert semantic.semantic_score("그 펜던트가 빛났다", "은빛 펜던트의 비밀") > \
           semantic.semantic_score("완전히 다른 이야기다", "은빛 펜던트의 비밀")

    from app.routers import ai_panel
    holder = {"client": None}
    spec = {"chunks": list(DEFAULT_CHUNKS), "exc": None}

    def _make_client(base_url, api_key_encrypted):
        holder["client"] = FakeAsyncOpenAI(base_url=base_url, api_key="x", spec=spec)
        return holder["client"]

    monkeypatch.setattr(ai_panel.llm, "make_client", _make_client)
    _make_client("http://x/v1", None)
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()

    pid = project["id"]
    # v1 매칭 실패 케이스: 키워드 "흑염술"이 본문에 없고, 본문은 "흑염의 술식"을 언급
    client.post(f"/api/v1/projects/{pid}/lore", json={
        "category": "용어", "title": "흑염술", "keywords": ["흑염술"],
        "content": "검은 불꽃을 다루는 술식"})
    client.post(f"/api/v1/projects/{pid}/lore", json={
        "category": "장소", "title": "남쪽 바다", "keywords": ["남쪽 바다"],
        "content": "바다의 끝"})
    client.put(f"/api/v1/chapters/{chapter['id']}/content", json={
        "content_md": "그는 흑염의 술식을 손끝으로 모았다.", "expected_revision": 0})

    # v1(키워드만) — 미매칭
    client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "써줘",
        "context": {"chapter_id": chapter["id"], "auto_lore": True}})
    user_text = holder["client"].last_kwargs["messages"][-1]["content"]
    assert "흑염술" not in user_text

    # v2(하이브리드) — 2-gram 유사도로 매칭
    client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "써줘",
        "context": {"chapter_id": chapter["id"], "auto_lore": True,
                    "auto_lore_semantic": True}})
    user_text = holder["client"].last_kwargs["messages"][-1]["content"]
    assert "[세계관(자동): 흑염술]" in user_text


# ---------- G-048 복선 회수 리마인드 ----------
def test_foreshadow_reminder(client, project):
    pid = project["id"]
    f1 = client.post(f"/api/v1/projects/{pid}/foreshadows", json={
        "title": "오래 잊힌 복선", "keywords": ["잊힌 복선"]}).json()
    f2 = client.post(f"/api/v1/projects/{pid}/foreshadows", json={
        "title": "방금 복선", "keywords": ["방금 복선"]}).json()
    chapters = []
    for i in range(7):
        ch = client.post(f"/api/v1/projects/{pid}/chapters",
                         json={"title": f"{i + 1}화", "sort_order": float(i)}).json()
        content = "방금 복선이 등장한다." if i == 6 else f"{i + 1}화 본문"
        client.put(f"/api/v1/chapters/{ch['id']}/content",
                   json={"content_md": content, "expected_revision": 0})
        chapters.append(ch)

    body = client.get(f"/api/v1/projects/{pid}/foreshadows/reminder?window=5").json()
    assert body["latest_chapter"]["title"] == "7화"
    by_id = {r["id"]: r for r in body["items"]}
    assert by_id[f1["id"]]["stale"] is True
    assert by_id[f1["id"]]["chapters_since_mentioned"] is None  # 한 번도 미언급
    assert by_id[f2["id"]]["stale"] is False                    # 직전 화에 언급
    assert by_id[f2["id"]]["chapters_since_mentioned"] == 0

    # 회수 상태는 리마인드 대상 제외
    client.patch(f"/api/v1/foreshadows/{f1['id']}", json={"status": "회수"})
    body = client.get(f"/api/v1/projects/{pid}/foreshadows/reminder").json()
    assert all(r["id"] != f1["id"] for r in body["items"])


# ---------- G-071 metrics_v2 연동 ----------
def test_quality_merges_metrics_v2_when_available(client, project, chapter):
    """im-not-ai 스킬이 있는 환경에서 metrics.v2가 병합된다(없으면 생략 — 둘 다 허용)."""
    from app.services import quality as quality_service
    quality_service._metrics_v2_loaded = False  # 모듈 캐시 리셋
    client.put(f"/api/v1/chapters/{chapter['id']}/content", json={
        "content_md": "「비켜라.」\n\n칼이 번개처럼 빠졌다. 그러나 그는 조용했다.", "expected_revision": 0})
    r = client.get(f"/api/v1/chapters/{chapter['id']}/quality?record=false").json()
    if quality_service._metrics_v2_module is not None:
        assert "v2" in r["metrics"]
        assert "risk_band" in r["metrics"]["v2"]
    else:
        assert "v2" not in r["metrics"]  # 스킬 미설치 환경 — 폴백 동작
