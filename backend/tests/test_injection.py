"""로어북 자동 주입 + 빌트인 프리셋 시드 테스트 (백로그 P1 / 부록06)."""
import json

import pytest
from sqlalchemy import select

from app.database import get_db
from app.models import LoreEntry
from app.routers import ai_panel
from app.services.injection import score_entries, select_lore_for_text
from app.services.presets_seed import BUILTIN_PRESETS, ensure_builtin_presets
from tests.test_ai_generate_stream import FakeAsyncOpenAI, _parse_sse


# ---------- fixtures ----------
@pytest.fixture()
def db(client):
    return next(iter(client.app.dependency_overrides[get_db]()))


@pytest.fixture()
def project(client):
    return client.post("/api/v1/projects", json={"title": "p"}).json()


def _mk_lore(client, pid, title, keywords=None, content=None, category="용어"):
    return client.post(f"/api/v1/projects/{pid}/lore", json={
        "category": category, "title": title,
        "content": content if content is not None else f"{title} 설명",
        "keywords": keywords or [],
    }).json()


def _mk_chapter(client, pid, content_md):
    ch = client.post(f"/api/v1/projects/{pid}/chapters", json={}).json()
    client.put(f"/api/v1/chapters/{ch['id']}/content",
               json={"content_md": content_md})
    return ch


@pytest.fixture()
def fake_llm(monkeypatch):
    holder = {"client": None}

    def _make_client(base_url, api_key_encrypted):
        c = FakeAsyncOpenAI(base_url=base_url, api_key="decrypted")
        holder["client"] = c
        return c

    monkeypatch.setattr(ai_panel.llm, "make_client", _make_client)
    return holder


def _generate(client, ep_id, context=None, prompt="써줘"):
    return client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep_id,
        "prompt_override": prompt,
        "context": context or {},
    })


# ---------- 단위: 점수화 ----------
def test_score_ranks_multi_hit_higher(db, project):
    a = LoreEntry(project_id=project["id"], title="붉은 협곡",
                  content="", keywords=["용암"])
    b = LoreEntry(project_id=project["id"], title="은빛 숲",
                  content="", keywords=[])
    db.add_all([a, b])
    db.commit()
    text = ("붉은 협곡에서 용암이 흘렀고, 붉은 협곡의 열기가 느껴졌다. "
            "은빛 숲도 멀지 않았다.")
    scored = score_entries([a, b], text)
    # 협곡: 제목 2회×3 + 키워드 1회×2 = 8 / 숲: 제목 1회×3
    assert [(e.id, s) for e, s in scored] == [(a.id, 8), (b.id, 3)]


def test_single_char_terms_ignored(db, project):
    entry = LoreEntry(project_id=project["id"], title="탑", content="", keywords=[])
    assert score_entries([entry], "탑 위에 섰다") == []


def test_select_lore_respects_limit(db, project):
    titles = ["무한의 탑", "붉은 협곡", "칠흑 성단", "은빛 숲"]
    for t in titles:
        db.add(LoreEntry(project_id=project["id"], title=t, content="",
                         keywords=[t]))
    db.commit()
    text = " ".join(titles)
    picked = select_lore_for_text(db, project["id"], text, limit=2)
    assert len(picked) == 2


def test_select_lore_empty_text(db, project):
    db.add(LoreEntry(project_id=project["id"], title="무언가", content="", keywords=[]))
    db.commit()
    assert select_lore_for_text(db, project["id"], "   ") == []


# ---------- 통합: POST /ai/generate ----------
@pytest.fixture()
def ep_with_world(client, project):
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://localhost:1234/v1",
        "default_model": "m-1"}).json()
    tower = _mk_lore(client, project["id"], "무한의 탑",
                     content="하늘까지 닿는 탑.", keywords=["탑 등반"])
    canyon = _mk_lore(client, project["id"], "붉은 협곡",
                      content="용암이 흐르는 협곡.")
    chapter = _mk_chapter(client, project["id"],
                          "주인공은 무한의 탑 앞에 섰다. 등반을 결심했다.")
    return {"ep": ep, "tower": tower, "canyon": canyon,
            "chapter": chapter, "project_id": project["id"]}


def test_auto_inject_adds_matching_lore_only(client, fake_llm, ep_with_world):
    resp = _generate(client, ep_with_world["ep"]["id"],
                     {"chapter_id": ep_with_world["chapter"]["id"], "auto_lore": True})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    start_data = json.loads(next(d for e, d in events if e == "start"))
    assert start_data["injected_lore"] == [
        {"id": ep_with_world["tower"]["id"], "title": "무한의 탑"}]

    sent = fake_llm["client"].last_kwargs
    user_msg = sent["messages"][0]["content"]
    assert "[세계관(자동): 무한의 탑]" in user_msg
    assert "하늘까지 닿는 탑." in user_msg
    assert "붉은 협곡" not in user_msg


def test_auto_inject_excludes_explicit_selection(client, fake_llm, ep_with_world):
    tower_id = ep_with_world["tower"]["id"]
    chapter = ep_with_world["chapter"]
    resp = _generate(client, ep_with_world["ep"]["id"],
                     {"chapter_id": chapter["id"], "auto_lore": True,
                      "lore_ids": [tower_id]})
    events = _parse_sse(resp.text)
    injected = json.loads(next(d for e, d in events if e == "start"))["injected_lore"]
    assert injected == []  # 명시 선택분은 자동 주입 목록에 없다(중복 방지)

    user_msg = fake_llm["client"].last_kwargs["messages"][0]["content"]
    assert "[세계관: 무한의 탑]" in user_msg      # 명시 블록
    assert "[세계관(자동):" not in user_msg        # 중복 주입 없음


def test_auto_inject_no_match_keeps_clean_prompt(client, fake_llm, ep_with_world):
    chapter = _mk_chapter(client, ep_with_world["project_id"],
                          "아무 설정 언급도 없는 본문.")
    resp = _generate(client, ep_with_world["ep"]["id"],
                     {"chapter_id": chapter["id"], "auto_lore": True})
    injected = json.loads(
        next(d for e, d in _parse_sse(resp.text) if e == "start"))["injected_lore"]
    assert injected == []
    assert "(자동)" not in fake_llm["client"].last_kwargs["messages"][0]["content"]


def test_auto_inject_without_project_context_silent_skip(client, fake_llm, ep_with_world):
    """chapter·project 지정이 없으면 조용히 건너뛴다(오류 아님)."""
    resp = _generate(client, ep_with_world["ep"]["id"], {"auto_lore": True},
                     prompt="무한의 탑을 써줘")
    assert resp.status_code == 200
    injected = json.loads(
        next(d for e, d in _parse_sse(resp.text) if e == "start"))["injected_lore"]
    assert injected == []


def test_auto_inject_via_project_id_without_chapter(client, fake_llm, project):
    _mk_lore(client, project["id"], "무한의 탑", content="하늘까지 닿는 탑.")
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e2", "base_url": "http://x/v1", "default_model": "m"}).json()
    resp = _generate(client, ep["id"],
                     {"auto_lore": True, "project_id": project["id"]},
                     prompt="무한의 탑 장면을 써줘")
    injected = json.loads(
        next(d for e, d in _parse_sse(resp.text) if e == "start"))["injected_lore"]
    assert len(injected) == 1
    assert injected[0]["title"] == "무한의 탑"


def test_auto_inject_limit_param_validated(client, ep_with_world):
    resp = _generate(client, ep_with_world["ep"]["id"],
                     {"chapter_id": ep_with_world["chapter"]["id"],
                      "auto_lore": True, "auto_lore_limit": 0})
    assert resp.status_code == 422


# ---------- 빌트인 프리셋 시드 ----------
def test_builtin_presets_seeded_on_startup(client):
    listed = client.get("/api/v1/ai/presets").json()
    names = {p["name"] for p in listed}
    assert {spec["name"] for spec in BUILTIN_PRESETS} <= names
    assert len(listed) >= len(BUILTIN_PRESETS)


def test_builtin_seed_is_idempotent(client, db):
    first = ensure_builtin_presets(db)
    db.commit()
    second = ensure_builtin_presets(db)
    db.commit()
    assert first == 0
    assert second == 0
