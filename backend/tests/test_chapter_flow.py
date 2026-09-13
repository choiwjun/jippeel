"""D03-1 회차 집필 흐름(flow_stage) — 상태 기계·전이 근거 앵커·재개 정보 계약 테스트.

- flow_stage는 Chapter.status와 독립이다 — 어느 쪽 전이도 다른 쪽을 바꾸지 않는다.
- 전이는 Chapter.revision·snapshot·memo·목표 쓰기와 무관하다.
- 전이 이벤트는 append-only이며 회차 삭제에 cascade된다.
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from app.database import Base, create_db_engine
from app.models import Chapter, ChapterFlowEvent, Project
from app.routers import projects
from app.schemas import ChapterFlowTransition


def _mk_project(client) -> int:
    return client.post("/api/v1/projects", json={"title": "흐름 작품"}).json()["id"]


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
        json={"goal": {"emotion_goal": "통쾌한 반격"}, "expected_goal_version": expected},
    )


# ---------- 기본값·조회 ----------

def test_new_chapter_defaults_to_planning(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    r = client.get(f"/api/v1/chapters/{cid}/flow")
    assert r.status_code == 200
    body = r.json()
    assert body["chapter_id"] == cid
    assert body["project_id"] == pid
    assert body["flow_stage"] == "planning"
    assert body["last_event"] is None
    assert body["current_goal_version"] is None
    assert body["current_chapter_revision"] == 0


def test_flow_missing_chapter_404(client):
    assert client.get("/api/v1/chapters/9999/flow").status_code == 404
    assert client.get("/api/v1/chapters/9999/flow/events").status_code == 404
    assert _transition(client, 9999, "writing", "planning").status_code == 404


# ---------- 허용 전이 ----------

def test_legal_transitions_accumulate_events(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]

    path = [
        ("writing", "planning"),
        ("revising", "writing"),
        ("confirmed", "revising"),
        ("revising", "confirmed"),
        ("writing", "revising"),
    ]
    for to_stage, expected in path:
        r = _transition(client, cid, to_stage, expected)
        assert r.status_code == 200, (to_stage, r.text)
        assert r.json()["flow_stage"] == to_stage
        assert r.json()["last_event"]["to_stage"] == to_stage

    events = client.get(f"/api/v1/chapters/{cid}/flow/events").json()
    assert len(events) == 5
    # 최신 먼저
    assert [e["to_stage"] for e in events] == [
        "writing", "revising", "confirmed", "revising", "writing",
    ]
    assert events[-1]["from_stage"] == "planning"


# ---------- 불법 전이 ----------

@pytest.mark.parametrize("to_stage", ["revising", "confirmed", "planning"])
def test_illegal_transitions_from_planning_rejected(client, to_stage):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    r = _transition(client, cid, to_stage, "planning")
    assert r.status_code == 422


def test_illegal_skip_and_same_stage_rejected(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    _transition(client, cid, "writing", "planning")
    # writing → confirmed 건너뛰기 불법
    assert _transition(client, cid, "confirmed", "writing").status_code == 422
    # 동일 단계 전이도 불법
    assert _transition(client, cid, "writing", "writing").status_code == 422


def test_confirmed_cannot_go_back_to_writing_or_planning(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    _transition(client, cid, "writing", "planning")
    _transition(client, cid, "revising", "writing")
    _transition(client, cid, "confirmed", "revising")
    assert _transition(client, cid, "writing", "confirmed").status_code == 422
    assert _transition(client, cid, "planning", "confirmed").status_code == 422
    # confirmed → revising 재개는 허용
    assert _transition(client, cid, "revising", "confirmed").status_code == 200


# ---------- CAS ----------

def test_transition_expected_stage_conflict_409(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    r = _transition(client, cid, "writing", "writing")  # 실제는 planning
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["code"] == "flow_stage_conflict"
    assert detail["current_flow_stage"] == "planning"


def test_transition_requires_expected_stage(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    r = client.post(
        f"/api/v1/chapters/{cid}/flow/transition", json={"to_stage": "writing"}
    )
    assert r.status_code == 422
    r = client.post(
        f"/api/v1/chapters/{cid}/flow/transition",
        json={"to_stage": "writing", "expected_flow_stage": "bogus"},
    )
    assert r.status_code == 422


def test_stale_expected_and_illegal_to_stage_returns_409_first(client):
    """CAS 불일치는 전이 합법성보다 먼저 판정 — stale expected + illegal to_stage 조합은 409."""
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    r = _transition(client, cid, "confirmed", "writing")  # 실제 planning — 둘 다 위반
    assert r.status_code == 409
    assert r.json()["detail"]["current_flow_stage"] == "planning"


# ---------- 근거 앵커 (D01 접점) ----------

def test_transition_records_goal_version_and_revision_anchor(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    _save_goal(client, cid)  # goal_version 1
    client.put(
        f"/api/v1/chapters/{cid}/content",
        json={"content_md": "원고 본문", "expected_revision": 0},
    )  # revision 1

    r = _transition(client, cid, "writing", "planning")
    event = r.json()["last_event"]
    assert event["goal_version"] == 1
    assert event["manuscript_revision"] == 1
    assert r.json()["current_goal_version"] == 1
    assert r.json()["current_chapter_revision"] == 1


def test_transition_without_saved_goal_anchors_null(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    r = _transition(client, cid, "writing", "planning")
    assert r.json()["last_event"]["goal_version"] is None


def test_transition_after_goal_deleted_anchors_null(client):
    """목표 저장본이 삭제된 뒤의 전이는 goal_version NULL로 기록한다(버전 자체는 이력에 남는다)."""
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    _save_goal(client, cid)  # v1
    assert client.delete(f"/api/v1/chapters/{cid}/goal").status_code == 204

    r = _transition(client, cid, "writing", "planning")
    assert r.status_code == 200
    assert r.json()["last_event"]["goal_version"] is None
    assert r.json()["current_goal_version"] is None


def test_anchor_uses_version_reference_not_goal_content(client):
    """앵커는 목표 내용 복사가 아닌 버전 참조 — 이후 목표 저장이 과거 이벤트를 바꾸지 않는다."""
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    _save_goal(client, cid)  # v1
    _transition(client, cid, "writing", "planning")
    _save_goal(client, cid, expected=1)  # v2
    _transition(client, cid, "revising", "writing")

    events = client.get(f"/api/v1/chapters/{cid}/flow/events").json()
    assert events[1]["goal_version"] == 1
    assert events[0]["goal_version"] == 2
    assert "goal" not in events[0] or events[0].get("goal") is None


# ---------- 보존 계약 ----------

def test_transition_preserves_revision_snapshot_memo_goal_status(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.put(
        f"/api/v1/chapters/{cid}/content",
        json={"content_md": "본문", "expected_revision": 0},
    )
    client.put(
        f"/api/v1/chapters/{cid}/content",
        json={"content_md": "본문2", "expected_revision": 1},
    )  # 교체 → snapshot 1개 생성
    client.patch(f"/api/v1/chapters/{cid}", json={"memo": "메모", "status": "수정중"})
    _save_goal(client, cid)
    snapshots_before = client.get(f"/api/v1/chapters/{cid}/snapshots").json()

    _transition(client, cid, "writing", "planning")

    chapter = client.get(f"/api/v1/chapters/{cid}").json()
    assert chapter["revision"] == 2
    assert chapter["memo"] == "메모"
    assert chapter["status"] == "수정중"  # flow 전이가 status를 바꾸지 않음
    assert chapter["content_md"] == "본문2"
    assert client.get(f"/api/v1/chapters/{cid}/snapshots").json() == snapshots_before
    goal = client.get(f"/api/v1/chapters/{cid}/goal").json()
    assert goal["goal"]["goal_version"] == 1
    assert goal["history_count"] == 1  # flow 전이는 목표 이력을 만들지 않음


def test_status_change_does_not_move_flow_stage(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    client.patch(f"/api/v1/chapters/{cid}", json={"status": "완료"})
    body = client.get(f"/api/v1/chapters/{cid}/flow").json()
    assert body["flow_stage"] == "planning"


# ---------- 독립 세션 경쟁·cascade (test_chapter_goals 패턴) ----------

@pytest.fixture()
def flow_sessions(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'flow-races.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        project = Project(title="Flow fixture")
        db.add(project)
        db.flush()
        chapter = Chapter(project_id=project.id, title="Source", sort_order=1)
        db.add(chapter)
        db.commit()
        ids = project.id, chapter.id
    yield factory, ids
    engine.dispose()


def _transition_schema(to_stage, expected):
    return ChapterFlowTransition(to_stage=to_stage, expected_flow_stage=expected)


def test_flow_transition_sqlite_busy_returns_409(flow_sessions):
    factory, (pid, cid) = flow_sessions
    with factory() as holder, factory() as contender:
        contender.execute(text("PRAGMA busy_timeout=0"))
        holder.execute(text("BEGIN IMMEDIATE"))
        with pytest.raises(HTTPException) as conflict:
            projects.transition_chapter_flow(
                cid, _transition_schema("writing", "planning"), contender
            )
        assert conflict.value.status_code == 409
        assert not contender.in_transaction()


def test_flow_events_cascade_after_chapter_delete(flow_sessions):
    factory, (pid, cid) = flow_sessions
    with factory() as db:
        projects.transition_chapter_flow(cid, _transition_schema("writing", "planning"), db)
    with factory() as db:
        projects.delete_chapter(cid, db)
    with factory() as verify:
        assert verify.get(Chapter, cid) is None
        assert list(verify.scalars(select(ChapterFlowEvent))) == []


def test_flow_events_cascade_after_project_delete(flow_sessions):
    factory, (pid, cid) = flow_sessions
    with factory() as db:
        projects.transition_chapter_flow(cid, _transition_schema("writing", "planning"), db)
    with factory() as deleting_db:
        projects.delete_project(pid, deleting_db)
    with factory() as verify:
        assert verify.get(Chapter, cid) is None
        assert verify.get(Project, pid) is None
        assert list(verify.scalars(select(ChapterFlowEvent))) == []
