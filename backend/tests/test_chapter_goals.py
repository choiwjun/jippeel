"""D01 회차 목표(브리프) 영속화 — 저장·이력·CAS·복원 계약 테스트.

- 목표 저장은 Chapter.revision·snapshot·memo·기억·복선과 무관하다.
- 생성 요청 계약(context.brief 검증·브리프 블록 주입)은 변경하지 않는다.
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, create_db_engine
from app.models import Chapter, ChapterGoal, ChapterGoalRevision, MemoryEntry, Project
from app.routers import projects
from app.schemas import (
    ChapterGoalPayload,
    ChapterGoalRestoreRequest,
    ChapterGoalWrite,
)
from tests.test_ai_generate_stream import fake_llm


def _mk_project(client) -> int:
    return client.post("/api/v1/projects", json={"title": "테스트 작품"}).json()["id"]


def _mk_chapter(client, pid: int, **kwargs) -> dict:
    return client.post(f"/api/v1/projects/{pid}/chapters", json=kwargs).json()


def _goal_payload(**overrides):
    payload = {
        "emotion_goal": "굴욕을 뒤집는 통쾌함",
        "core_events": ["파문 통보", "흑요검의 첫 반응"],
        "character_choices": ["주인공은 복귀 대신 독자 노선을 택한다"],
        "cost": "세가 복귀 가능성을 포기한다",
        "prohibitions": ["흑요검의 정체를 완전히 밝히지 않는다"],
        "next_hook": "뒤에서 손목을 붙잡힌다",
        "ending_intent": None,
        "scene_type": "대립",
        "target_chars_novelpia": 5500,
    }
    payload.update(overrides)
    return payload


def _write(cid, expected, goal=None, **overrides):
    body = {
        "goal": _goal_payload(**(goal or {})),
        "expected_goal_version": expected,
    }
    body.update(overrides)
    return body


# ---------- 기본 저장·조회 ----------

def test_goal_absent_returns_null_not_error(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    r = client.get(f"/api/v1/chapters/{cid}/goal")
    assert r.status_code == 200
    body = r.json()
    assert body["chapter_id"] == cid
    assert body["project_id"] == pid
    assert body["goal"] is None
    assert body["history_count"] == 0
    assert body["current_chapter_revision"] == 0


def test_goal_missing_chapter_404(client):
    assert client.get("/api/v1/chapters/9999/goal").status_code == 404
    assert client.put("/api/v1/chapters/9999/goal", json=_write(9999, None)).status_code == 404
    assert client.delete("/api/v1/chapters/9999/goal").status_code == 404


def test_goal_save_and_reload_preserves_payload(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    r = client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None))
    assert r.status_code == 200
    body = r.json()
    assert body["goal"]["goal_version"] == 1
    assert body["goal"]["episode_purpose"] == "serial"
    assert body["goal"]["base_manuscript_revision"] == 0
    assert body["goal"]["goal"]["emotion_goal"] == "굴욕을 뒤집는 통쾌함"
    assert body["goal"]["goal"]["core_events"] == ["파문 통보", "흑요검의 첫 반응"]
    assert body["goal"]["goal"]["target_chars_novelpia"] == 5500
    assert body["history_count"] == 1

    # 재조회 — 재진입 복원 계약
    got = client.get(f"/api/v1/chapters/{cid}/goal").json()
    assert got["goal"]["goal_version"] == 1
    assert got["goal"]["goal"]["cost"] == "세가 복귀 가능성을 포기한다"


def test_goal_partial_and_empty_save_allowed(client):
    """저장 완성도 ≠ 생성 완성도 — 부분·빈 목표도 저장된다."""
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]

    partial = client.put(
        f"/api/v1/chapters/{cid}/goal",
        json={"goal": {"emotion_goal": "  일단 감정만  "}, "expected_goal_version": None},
    )
    assert partial.status_code == 200
    stored = partial.json()["goal"]["goal"]
    assert stored["emotion_goal"] == "일단 감정만"  # 정규화: trim
    assert stored["core_events"] is None

    # 정규화: 빈 배열 항목 제거, 빈 문자열 → null
    normalized = client.put(
        f"/api/v1/chapters/{cid}/goal",
        json={
            "goal": {
                "emotion_goal": "   ",
                "core_events": ["  ", "유지 항목", ""],
                "next_hook": "  ",
            },
            "expected_goal_version": 1,
        },
    )
    assert normalized.status_code == 200
    goal = normalized.json()["goal"]["goal"]
    assert goal["emotion_goal"] is None
    assert goal["core_events"] == ["유지 항목"]
    assert goal["next_hook"] is None

    # 전 필드 빈 값 = "빈 목표" 저장(삭제 아님)
    emptied = client.put(
        f"/api/v1/chapters/{cid}/goal",
        json={"goal": {}, "expected_goal_version": 2},
    )
    assert emptied.status_code == 200
    assert emptied.json()["goal"]["goal"]["emotion_goal"] is None


@pytest.mark.parametrize("field,value", [
    ("emotion_goal", "가" * 501),
    ("core_events", ["a"] * 4),
    ("core_events", ["가" * 501]),
    ("character_choices", ["a"] * 5),
    ("prohibitions", ["a"] * 11),
    ("scene_type", "애교"),
    ("target_chars_novelpia", 999),
    ("target_chars_novelpia", 10001),
])
def test_goal_payload_limit_violations_422(client, field, value):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    r = client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None, goal={field: value}))
    assert r.status_code == 422


def test_goal_write_requires_goal_and_expected_version(client):
    """계약상 goal·expected_goal_version은 필수 — 생략하면 CAS 의도가 숨겨지므로 422."""
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    assert client.put(
        f"/api/v1/chapters/{cid}/goal",
        json={"expected_goal_version": None},
    ).status_code == 422
    assert client.put(
        f"/api/v1/chapters/{cid}/goal",
        json={"goal": {}},
    ).status_code == 422
    assert client.post(
        f"/api/v1/chapters/{cid}/goal/restore",
        json={"goal_version": 1},
    ).status_code == 422


def test_goal_purpose_saved_and_mismatch_rejected(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    r = client.put(
        f"/api/v1/chapters/{cid}/goal",
        json=_write(cid, None, episode_purpose="series_finale"),
    )
    assert r.status_code == 200
    assert r.json()["goal"]["episode_purpose"] == "series_finale"

    bad = client.put(
        f"/api/v1/chapters/{cid}/goal",
        json=_write(cid, 1, episode_purpose="finale"),
    )
    assert bad.status_code == 422


def test_goal_project_id_mismatch_422(client):
    pid = _mk_project(client)
    other = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    r = client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None, project_id=other))
    assert r.status_code == 422
    ok = client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None, project_id=pid))
    assert ok.status_code == 200


def test_goals_isolated_between_chapters(client):
    pid = _mk_project(client)
    c1 = _mk_chapter(client, pid, title="1화")["id"]
    c2 = _mk_chapter(client, pid, title="2화")["id"]
    assert client.put(f"/api/v1/chapters/{c1}/goal", json=_write(c1, None)).status_code == 200
    assert client.get(f"/api/v1/chapters/{c2}/goal").json()["goal"] is None
    r = client.put(f"/api/v1/chapters/{c2}/goal", json=_write(c2, None, goal={"emotion_goal": "다른 목표"}))
    assert r.json()["goal"]["goal"]["emotion_goal"] == "다른 목표"
    assert client.get(f"/api/v1/chapters/{c1}/goal").json()["goal"]["goal"]["emotion_goal"] == "굴욕을 뒤집는 통쾌함"


# ---------- CAS ----------

def test_goal_create_conflict_when_exists(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    assert client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None)).status_code == 200
    r = client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None))
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "goal_version_conflict"
    assert r.json()["detail"]["current_goal_version"] == 1


def test_goal_update_stale_expected_conflict(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None))
    client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, 1))
    r = client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, 1))
    assert r.status_code == 409
    assert r.json()["detail"]["current_goal_version"] == 2


def test_goal_update_expected_on_absent_conflicts(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    r = client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, 3))
    assert r.status_code == 409
    assert r.json()["detail"]["current_goal_version"] is None


def test_goal_save_does_not_touch_manuscript_revision_snapshot_or_memo(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.put(f"/api/v1/chapters/{cid}/content", json={"content_md": "원고 본문", "expected_revision": 0})
    client.patch(f"/api/v1/chapters/{cid}", json={"memo": "메모 보존"})

    before = client.get(f"/api/v1/chapters/{cid}").json()
    snapshots_before = client.get(f"/api/v1/chapters/{cid}/snapshots").json()

    assert client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None)).status_code == 200

    after = client.get(f"/api/v1/chapters/{cid}").json()
    assert after["revision"] == before["revision"] == 1
    assert after["content_md"] == "원고 본문"
    assert after["memo"] == "메모 보존"
    assert client.get(f"/api/v1/chapters/{cid}/snapshots").json() == snapshots_before


def test_goal_base_revision_tracks_client_reported_value(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.put(f"/api/v1/chapters/{cid}/content", json={"content_md": "r1", "expected_revision": 0})
    r = client.put(
        f"/api/v1/chapters/{cid}/goal",
        json=_write(cid, None, base_manuscript_revision=1),
    )
    assert r.json()["goal"]["base_manuscript_revision"] == 1

    # 원문이 진행해도 목표 기준 revision은 자동 갱신되지 않는다 — current_chapter_revision 차이가 stale 근거
    client.put(f"/api/v1/chapters/{cid}/content", json={"content_md": "r2", "expected_revision": 1})
    got = client.get(f"/api/v1/chapters/{cid}/goal").json()
    assert got["goal"]["base_manuscript_revision"] == 1
    assert got["current_chapter_revision"] == 2


def test_manuscript_restore_does_not_change_goal(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.put(f"/api/v1/chapters/{cid}/content", json={"content_md": "v1", "expected_revision": 0})
    client.put(f"/api/v1/chapters/{cid}/content", json={"content_md": "v2", "expected_revision": 1})
    client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None, base_manuscript_revision=2))
    snapshot_id = client.get(f"/api/v1/chapters/{cid}/snapshots").json()[0]["id"]

    r = client.post(
        f"/api/v1/chapters/{cid}/restore",
        json={"snapshot_id": snapshot_id, "expected_revision": 2},
    )
    assert r.status_code == 200
    got = client.get(f"/api/v1/chapters/{cid}/goal").json()
    assert got["goal"]["goal_version"] == 1
    assert got["goal"]["base_manuscript_revision"] == 2
    assert got["current_chapter_revision"] == 3


# ---------- 삭제·이력 ----------

def test_goal_delete_keeps_history_and_next_version_continues(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None))
    client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, 1, goal={"emotion_goal": "v2"}))

    assert client.delete(f"/api/v1/chapters/{cid}/goal").status_code == 204
    got = client.get(f"/api/v1/chapters/{cid}/goal").json()
    assert got["goal"] is None
    assert got["history_count"] == 2

    history = client.get(f"/api/v1/chapters/{cid}/goal/history").json()
    assert [row["goal_version"] for row in history] == [2, 1]

    recreated = client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None))
    assert recreated.status_code == 200
    assert recreated.json()["goal"]["goal_version"] == 3


def test_goal_delete_absent_404_and_chapter_scoped(client):
    pid = _mk_project(client)
    c1 = _mk_chapter(client, pid)["id"]
    c2 = _mk_chapter(client, pid)["id"]
    client.put(f"/api/v1/chapters/{c1}/goal", json=_write(c1, None))
    assert client.delete(f"/api/v1/chapters/{c2}/goal").status_code == 404
    assert client.get(f"/api/v1/chapters/{c1}/goal").json()["goal"] is not None


def test_goal_delete_preserves_chapter_data_and_references(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.put(f"/api/v1/chapters/{cid}/content", json={"content_md": "본문", "expected_revision": 0})
    client.patch(f"/api/v1/chapters/{cid}", json={"memo": "메모"})
    memory = client.post(
        f"/api/v1/projects/{pid}/memories",
        json={"chapter_id": cid, "kind": "fact", "body": "연결된 기억"},
    )
    assert memory.status_code == 201
    client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None))

    assert client.delete(f"/api/v1/chapters/{cid}/goal").status_code == 204
    chapter = client.get(f"/api/v1/chapters/{cid}").json()
    assert chapter["content_md"] == "본문"
    assert chapter["memo"] == "메모"
    assert client.get(f"/api/v1/projects/{pid}/memories").json()[0]["body"] == "연결된 기억"


def test_chapter_delete_cascades_goal_and_history(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None))
    client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, 1))
    assert client.delete(f"/api/v1/chapters/{cid}").status_code == 204
    assert client.get(f"/api/v1/chapters/{cid}/goal").status_code == 404


def test_chapter_delete_still_blocked_by_foreshadow_reference(client):
    """기존 회차 삭제 409 정책은 목표 도입으로 확장·변경되지 않는다."""
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    fs = client.post(
        f"/api/v1/projects/{pid}/foreshadows",
        json={"title": "복선", "planted_chapter_id": cid},
    )
    assert fs.status_code == 201
    client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None))
    assert client.delete(f"/api/v1/chapters/{cid}").status_code == 409
    # 삭제가 거절됐으므로 목표도 남는다
    assert client.get(f"/api/v1/chapters/{cid}/goal").json()["goal"] is not None


def test_chapter_delete_blocked_by_memory_keeps_goal(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.post(f"/api/v1/projects/{pid}/memories", json={"chapter_id": cid, "kind": "fact", "body": "기억"})
    client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None))
    assert client.delete(f"/api/v1/chapters/{cid}").status_code == 409
    assert client.get(f"/api/v1/chapters/{cid}/goal").json()["goal"] is not None


# ---------- 이력 조회·복원 ----------

def test_goal_history_listing_descending(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None, goal={"emotion_goal": "v1"}))
    client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, 1, goal={"emotion_goal": "v2"}))
    client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, 2, goal={"emotion_goal": "v3"}))

    history = client.get(f"/api/v1/chapters/{cid}/goal/history").json()
    assert [row["goal_version"] for row in history] == [3, 2, 1]
    assert history[0]["goal"]["emotion_goal"] == "v3"
    assert history[0]["restored_from"] is None
    assert "created_at" in history[0]
    # 다른 회차 이력과 섞이지 않는다
    other = _mk_chapter(client, pid)["id"]
    assert client.get(f"/api/v1/chapters/{other}/goal/history").json() == []


def test_goal_restore_writes_new_version_and_restores_purpose(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.put(
        f"/api/v1/chapters/{cid}/goal",
        json=_write(cid, None, goal={"emotion_goal": "옛 목표"}, episode_purpose="series_finale"),
    )
    client.put(
        f"/api/v1/chapters/{cid}/goal",
        json=_write(cid, 1, goal={"emotion_goal": "새 목표"}, episode_purpose="serial"),
    )

    r = client.post(
        f"/api/v1/chapters/{cid}/goal/restore",
        json={"goal_version": 1, "expected_goal_version": 2},
    )
    assert r.status_code == 200
    goal = r.json()["goal"]
    assert goal["goal_version"] == 3
    assert goal["goal"]["emotion_goal"] == "옛 목표"
    assert goal["episode_purpose"] == "series_finale"

    history = client.get(f"/api/v1/chapters/{cid}/goal/history").json()
    assert history[0]["goal_version"] == 3
    assert history[0]["restored_from"] == 1
    # 원본 이력은 덮어쓰지 않는다
    assert [row["goal_version"] for row in history] == [3, 2, 1]


def test_goal_restore_missing_revision_404_and_cas(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None))
    missing = client.post(
        f"/api/v1/chapters/{cid}/goal/restore",
        json={"goal_version": 99, "expected_goal_version": 1},
    )
    assert missing.status_code == 404

    stale = client.post(
        f"/api/v1/chapters/{cid}/goal/restore",
        json={"goal_version": 1, "expected_goal_version": 7},
    )
    assert stale.status_code == 409


def test_goal_restore_requires_current_version_even_when_absent(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None))
    # 목표 삭제 후 복원 — expected None은 "현재 없음" 기대로 허용
    assert client.delete(f"/api/v1/chapters/{cid}/goal").status_code == 204
    r = client.post(
        f"/api/v1/chapters/{cid}/goal/restore",
        json={"goal_version": 1, "expected_goal_version": None},
    )
    assert r.status_code == 200
    assert r.json()["goal"]["goal_version"] == 2
    assert r.json()["goal"]["goal"]["emotion_goal"] == "굴욕을 뒤집는 통쾌함"


# ---------- 생성 연계: 저장본이 요청을 몰래 바꾸지 않는다 ----------

def test_saved_goal_does_not_alter_generation_request(client, fake_llm):
    """저장된 목표는 생성 요청에 자동 주입되지 않는다 — 요청 brief만 사용."""
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.put(f"/api/v1/chapters/{cid}/goal", json=_write(cid, None))

    r = client.post(
        "/api/v1/ai/generate",
        json={
            "prompt_override": "써줘",
            "context": {"project_id": pid, "chapter_id": cid},
        },
    )
    assert r.status_code == 200
    text = str(fake_llm["client"].last_kwargs.get("messages", ""))
    assert "굴욕을 뒤집는 통쾌함" not in text, "저장 목표가 요청 없이 주입되면 안 된다"


def test_generation_brief_block_unchanged_by_saved_goal(client, fake_llm):
    """요청 brief는 그대로 1회 주입 — 저장본과 섞이지 않는다."""

    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.put(
        f"/api/v1/chapters/{cid}/goal",
        json=_write(cid, None, goal={"emotion_goal": "저장본 목표"}),
    )

    brief = {
        "emotion_goal": "요청 브리프 목표",
        "core_events": ["사건"],
        "character_choices": ["선택"],
        "cost": "대가",
        "prohibitions": ["금지"],
        "next_hook": "훅",
    }
    r = client.post(
        "/api/v1/ai/generate",
        json={
            "prompt_override": "써줘",
            "context": {"project_id": pid, "chapter_id": cid, "brief": brief},
        },
    )
    assert r.status_code == 200
    text = str(fake_llm["client"].last_kwargs.get("messages", ""))
    assert "요청 브리프 목표" in text
    assert "저장본 목표" not in text


# ---------- 독립 세션 경쟁 (test_memory_concurrency 패턴) ----------

@pytest.fixture()
def goal_sessions(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'goal-races.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        project = Project(title="Race fixture")
        db.add(project)
        db.flush()
        chapter = Chapter(project_id=project.id, title="Source", sort_order=1)
        db.add(chapter)
        db.commit()
        ids = project.id, chapter.id
    yield factory, ids
    engine.dispose()


def _write_schema(expected, goal=None):
    return ChapterGoalWrite(
        goal=ChapterGoalPayload.model_validate(goal if goal is not None else _goal_payload()),
        expected_goal_version=expected,
    )


def test_concurrent_goal_update_loser_gets_409(goal_sessions, monkeypatch):
    factory, (pid, cid) = goal_sessions
    with factory() as seed:
        projects.put_chapter_goal(cid, _write_schema(None), seed)
    original = projects._get_chapter_or_404
    with factory() as stale_db, factory() as winning_db:
        def read_then_commit_winner(chapter_id, db):
            snapshot = original(chapter_id, db)
            if db is stale_db:
                projects.put_chapter_goal(cid, _write_schema(1, {"emotion_goal": "winner"}), winning_db)
            return snapshot
        monkeypatch.setattr(projects, "_get_chapter_or_404", read_then_commit_winner)
        with pytest.raises(HTTPException) as conflict:
            projects.put_chapter_goal(cid, _write_schema(1, {"emotion_goal": "loser"}), stale_db)
        assert conflict.value.status_code == 409
    with factory() as verify:
        stored = verify.scalar(select(ChapterGoal).where(ChapterGoal.chapter_id == cid))
        assert stored.goal_version == 2
        assert stored.goal_json["emotion_goal"] == "winner"
        versions = list(verify.scalars(
            select(ChapterGoalRevision.goal_version).where(ChapterGoalRevision.chapter_id == cid)
        ))
        assert sorted(versions) == [1, 2]


def test_concurrent_goal_create_loser_gets_409(goal_sessions, monkeypatch):
    factory, (pid, cid) = goal_sessions
    original = projects._get_chapter_or_404
    with factory() as stale_db, factory() as winning_db:
        def read_then_commit_winner(chapter_id, db):
            snapshot = original(chapter_id, db)
            if db is stale_db:
                projects.put_chapter_goal(cid, _write_schema(None), winning_db)
            return snapshot
        monkeypatch.setattr(projects, "_get_chapter_or_404", read_then_commit_winner)
        with pytest.raises(HTTPException) as conflict:
            projects.put_chapter_goal(cid, _write_schema(None), stale_db)
        assert conflict.value.status_code == 409
    with factory() as verify:
        stored = verify.scalar(select(ChapterGoal).where(ChapterGoal.chapter_id == cid))
        assert stored.goal_version == 1


def test_goal_write_sqlite_busy_returns_409(goal_sessions):
    factory, (pid, cid) = goal_sessions
    with factory() as holder, factory() as contender:
        contender.execute(text("PRAGMA busy_timeout=0"))
        holder.execute(text("BEGIN IMMEDIATE"))
        with pytest.raises(HTTPException) as conflict:
            projects.put_chapter_goal(cid, _write_schema(None), contender)
        assert conflict.value.status_code == 409
        assert not contender.in_transaction()


def test_goal_cascade_after_project_delete(goal_sessions):
    factory, (pid, cid) = goal_sessions
    with factory() as db:
        projects.put_chapter_goal(cid, _write_schema(None), db)
    with factory() as deleting_db:
        projects.delete_project(pid, deleting_db)
    with factory() as verify:
        assert verify.get(Chapter, cid) is None
        assert list(verify.scalars(select(ChapterGoal))) == []
        assert list(verify.scalars(select(ChapterGoalRevision))) == []


def test_goal_row_does_not_block_chapter_delete(goal_sessions):
    """목표는 회차 삭제의 409 참조 검사에 추가되지 않는다(삭제 허용 시 cascade)."""
    factory, (pid, cid) = goal_sessions
    with factory() as db:
        projects.put_chapter_goal(cid, _write_schema(None), db)
    with factory() as db:
        projects.delete_chapter(cid, db)
    with factory() as verify:
        assert verify.get(Chapter, cid) is None
        assert list(verify.scalars(select(ChapterGoal))) == []
        assert list(verify.scalars(select(ChapterGoalRevision))) == []
        assert list(verify.scalars(select(MemoryEntry))) == []
