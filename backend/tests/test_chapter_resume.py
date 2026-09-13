"""D03-2 회차 재개 계약 — /chapters/{cid}/resume 파생 읽기 테스트.

- resume은 순수 읽기: 전이 이벤트·snapshot·목표·원고를 만들거나 바꾸지 않는다.
- 드리프트 플래그는 D03-1 last_event 앵커 대비 현재값 비교다.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database import Base, create_db_engine, get_db
from app.main import app
from app.models import ChapterFlowEvent, ChapterSnapshot, RefineRun
from app.services.presets_seed import ensure_builtin_presets


@pytest.fixture()
def client_db(tmp_path):
    """conftest의 client와 동일한 격리 DB이되 세션 팩토리를 함께 노출한다."""
    db_path = tmp_path / "test.db"
    engine = create_db_engine(f"sqlite:///{db_path}")
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    seed = TestingSessionLocal()
    try:
        ensure_builtin_presets(seed)
        seed.commit()
    finally:
        seed.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c, TestingSessionLocal
    app.dependency_overrides.clear()
    engine.dispose()


def _mk_project(client) -> int:
    return client.post("/api/v1/projects", json={"title": "재개 작품"}).json()["id"]


def _mk_chapter(client, pid: int, **kwargs) -> dict:
    return client.post(f"/api/v1/projects/{pid}/chapters", json=kwargs).json()


def _transition(client, cid: int, to_stage: str, expected: str):
    return client.post(
        f"/api/v1/chapters/{cid}/flow/transition",
        json={"to_stage": to_stage, "expected_flow_stage": expected},
    )


def _save_goal(client, cid: int, expected=None):
    return client.put(
        f"/api/v1/chapters/{cid}/goal",
        json={"goal": {"emotion_goal": "목표"}, "expected_goal_version": expected},
    )


def _save_content(client, cid: int, text: str, expected: int):
    return client.put(
        f"/api/v1/chapters/{cid}/content",
        json={"content_md": text, "expected_revision": expected},
    )


def _resume(client, cid: int):
    return client.get(f"/api/v1/chapters/{cid}/resume")


# ---------- 기본 ----------

def test_resume_new_chapter_defaults(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    r = _resume(client, cid)
    assert r.status_code == 200
    body = r.json()
    assert body["chapter_id"] == cid
    assert body["project_id"] == pid
    assert body["flow_stage"] == "planning"
    assert body["last_event"] is None
    assert body["current_goal_version"] is None
    assert body["current_chapter_revision"] == 0
    assert body["goal_changed_since_transition"] is False
    assert body["manuscript_changed_since_transition"] is False
    assert body["pending_refine_runs"] == 0
    assert body["next_scene"] is None
    assert body["scene_count"] == 0


def test_resume_missing_chapter_404(client):
    assert _resume(client, 9999).status_code == 404


# ---------- 드리프트 ----------

def test_resume_goal_drift_after_transition(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    _save_goal(client, cid)  # v1
    _transition(client, cid, "writing", "planning")
    assert _resume(client, cid).json()["goal_changed_since_transition"] is False

    _save_goal(client, cid, expected=1)  # v2
    body = _resume(client, cid).json()
    assert body["goal_changed_since_transition"] is True
    assert body["last_event"]["goal_version"] == 1
    assert body["current_goal_version"] == 2


def test_resume_manuscript_drift_after_transition(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    _transition(client, cid, "writing", "planning")
    assert _resume(client, cid).json()["manuscript_changed_since_transition"] is False

    _save_content(client, cid, "본문", 0)
    body = _resume(client, cid).json()
    assert body["manuscript_changed_since_transition"] is True
    assert body["last_event"]["manuscript_revision"] == 0
    assert body["current_chapter_revision"] == 1


def test_resume_no_drift_without_events(client):
    """전이 이력이 없으면 목표·원고 변경이 있어도 drift는 false다."""
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    _save_goal(client, cid)
    _save_content(client, cid, "본문", 0)
    body = _resume(client, cid).json()
    assert body["goal_changed_since_transition"] is False
    assert body["manuscript_changed_since_transition"] is False
    assert body["current_goal_version"] == 1
    assert body["current_chapter_revision"] == 1


def test_resume_goal_created_after_null_anchor_is_drift(client):
    """전이 시점 goal_version=None → 이후 목표 생성은 드리프트다."""
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    _transition(client, cid, "writing", "planning")  # 앵커 goal_version=None
    assert _resume(client, cid).json()["goal_changed_since_transition"] is False

    _save_goal(client, cid)  # v1 생성
    body = _resume(client, cid).json()
    assert body["goal_changed_since_transition"] is True
    assert body["last_event"]["goal_version"] is None
    assert body["current_goal_version"] == 1


def test_resume_goal_deleted_after_anchor_is_drift(client):
    """전이 시점 goal_version=v1 → 이후 목표 삭제는 드리프트다."""
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    _save_goal(client, cid)
    _transition(client, cid, "writing", "planning")

    client.delete(f"/api/v1/chapters/{cid}/goal")
    body = _resume(client, cid).json()
    assert body["goal_changed_since_transition"] is True
    assert body["last_event"]["goal_version"] == 1
    assert body["current_goal_version"] is None


def test_resume_both_drifts_simultaneously(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    _save_goal(client, cid)
    _save_content(client, cid, "본문", 0)
    _transition(client, cid, "writing", "planning")

    _save_goal(client, cid, expected=1)  # v2
    _save_content(client, cid, "본문2", 1)  # r2
    body = _resume(client, cid).json()
    assert body["goal_changed_since_transition"] is True
    assert body["manuscript_changed_since_transition"] is True


def test_resume_drift_compares_against_latest_event_only(client):
    """드리프트는 마지막 이벤트 앵커 기준 — 이전 이벤트는 무관하다."""
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    _save_goal(client, cid)  # v1
    _transition(client, cid, "writing", "planning")  # event1: goal v1, r0
    _save_goal(client, cid, expected=1)  # v2 — event1 기준 drift
    _transition(client, cid, "revising", "writing")  # event2: goal v2, r0

    body = _resume(client, cid).json()
    assert body["last_event"]["goal_version"] == 2
    assert body["goal_changed_since_transition"] is False


# ---------- 미해결 감수 ----------

def test_resume_pending_refine_runs_counts_unaccepted(client_db):
    client, Session = client_db
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    with Session() as db:
        db.add(RefineRun(chapter_id=cid, route_hint="standard", result_text="a", accepted=False))
        db.add(RefineRun(chapter_id=cid, route_hint="light", result_text="b", accepted=True))
        db.add(RefineRun(chapter_id=cid, route_hint="light", result_text="c", accepted=False))
        db.commit()

    assert _resume(client, cid).json()["pending_refine_runs"] == 2


# ---------- 다음 장면 ----------

def test_resume_next_scene_is_first_empty(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.post(f"/api/v1/chapters/{cid}/scenes", json={"title": "s1", "content_md": "본문"})
    client.post(f"/api/v1/chapters/{cid}/scenes", json={"title": "s2"})
    client.post(f"/api/v1/chapters/{cid}/scenes", json={"title": "s3"})

    body = _resume(client, cid).json()
    assert body["scene_count"] == 3
    assert body["next_scene"]["title"] == "s2"


def test_resume_next_scene_none_when_all_written(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.post(f"/api/v1/chapters/{cid}/scenes", json={"title": "s1", "content_md": "본문"})

    body = _resume(client, cid).json()
    assert body["scene_count"] == 1
    assert body["next_scene"] is None


def test_resume_next_scene_follows_sort_order_not_id(client):
    """next_scene은 id가 아니라 sort_order 순서를 따른다."""
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.post(f"/api/v1/chapters/{cid}/scenes", json={"title": "늦게만든앞장면", "sort_order": 1.0})
    client.post(f"/api/v1/chapters/{cid}/scenes", json={"title": "먼저만든뒷장면", "sort_order": 2.0})

    body = _resume(client, cid).json()
    assert body["next_scene"]["title"] == "늦게만든앞장면"


def test_resume_next_scene_whitespace_counts_as_empty(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.post(f"/api/v1/chapters/{cid}/scenes", json={"title": "공백만", "content_md": "  \n\t  "})

    body = _resume(client, cid).json()
    assert body["next_scene"]["title"] == "공백만"
    assert set(body["next_scene"].keys()) == {"id", "sort_order", "title"}


# ---------- 보존 ----------

def test_resume_is_read_only(client_db):
    client, Session = client_db
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    _save_goal(client, cid)
    _save_content(client, cid, "본문", 0)
    _transition(client, cid, "writing", "planning")

    with Session() as db:
        events_before = len(list(db.scalars(select(ChapterFlowEvent))))
        snaps_before = len(list(db.scalars(select(ChapterSnapshot))))

    r = _resume(client, cid)
    assert r.status_code == 200

    with Session() as db:
        assert len(list(db.scalars(select(ChapterFlowEvent)))) == events_before
        assert len(list(db.scalars(select(ChapterSnapshot)))) == snaps_before
    assert client.get(f"/api/v1/chapters/{cid}/goal").json()["history_count"] == 1
