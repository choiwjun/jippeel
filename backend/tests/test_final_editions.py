"""D03-6 완결본 관리 — project_final_editions + 완결 점검표 계약 테스트.

- 완결본은 명시적 생성의 불변 스냅샷(본문 복사본) — 회차 변경·삭제와 무관하게 보존.
- 점검표는 파생 읽기 전용 — 자동 완결 판정 없음.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import Base, create_db_engine, get_db
from app.main import app
from app.models import RefineRun
from app.services.presets_seed import ensure_builtin_presets


@pytest.fixture()
def client_db(tmp_path):
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


def _mk_project(client, **fields) -> int:
    return client.post("/api/v1/projects", json={"title": "완결 작품", **fields}).json()["id"]


def _mk_chapter(client, pid: int, title: str, content: str = "", **fields) -> dict:
    ch = client.post(
        f"/api/v1/projects/{pid}/chapters", json={"title": title, **fields}
    ).json()
    if content:
        client.put(
            f"/api/v1/chapters/{ch['id']}/content",
            json={"content_md": content, "expected_revision": ch["revision"]},
        )
        ch = client.get(f"/api/v1/chapters/{ch['id']}").json()
    return ch


def _transition(client, cid: int, to: str, expected: str):
    r = client.post(
        f"/api/v1/chapters/{cid}/flow/transition",
        json={"to_stage": to, "expected_flow_stage": expected},
    )
    assert r.status_code == 200, r.text


def _confirm(client, cid: int):
    _transition(client, cid, "writing", "planning")
    _transition(client, cid, "revising", "writing")
    _transition(client, cid, "confirmed", "revising")


def _mk_foreshadow(client, pid: int, title: str, status: str = "설치", **extra) -> dict:
    r = client.post(
        f"/api/v1/projects/{pid}/foreshadows",
        json={"title": title, "status": status, **extra},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _checklist(client, pid: int):
    r = client.get(f"/api/v1/projects/{pid}/completion-checklist")
    assert r.status_code == 200, r.text
    return r.json()


# ---------- 완결 점검표 ----------

def test_checklist_empty_project(client):
    pid = _mk_project(client)
    body = _checklist(client, pid)
    assert body["serial_state"] == "ongoing"
    assert body["serial_completed_at"] is None
    assert body["chapters"] == {
        "total": 0,
        "by_stage": {"planning": 0, "writing": 0, "revising": 0, "confirmed": 0},
        "unconfirmed": 0,
    }
    assert body["foreshadows"]["total"] == 0
    assert body["foreshadows"]["open"] == []
    assert body["foreshadows"]["by_disposition"] == {
        "resolved": 0,
        "intentional_unresolved": 0,
        "side_story": 0,
        "closed_unclassified": 0,
    }
    assert body["pending_refine_runs"] == 0
    assert body["broken_evidence_links"] == 0
    assert body["finale_goals_missing_ending"] == []


def test_checklist_missing_project_404(client):
    assert client.get("/api/v1/projects/9999/completion-checklist").status_code == 404


def test_checklist_chapter_stage_counts(client):
    pid = _mk_project(client)
    _mk_chapter(client, pid, "1화")  # planning
    c2 = _mk_chapter(client, pid, "2화")
    _transition(client, c2["id"], "writing", "planning")
    c3 = _mk_chapter(client, pid, "3화")
    _confirm(client, c3["id"])

    body = _checklist(client, pid)
    assert body["chapters"]["total"] == 3
    assert body["chapters"]["by_stage"] == {
        "planning": 1, "writing": 1, "revising": 0, "confirmed": 1,
    }
    assert body["chapters"]["unconfirmed"] == 2


def test_checklist_foreshadow_disposition_buckets(client):
    pid = _mk_project(client)
    _mk_foreshadow(client, pid, "미회수 복선")  # 설치 → open
    _mk_foreshadow(client, pid, "해결 복선", status="회수", disposition="resolved")
    _mk_foreshadow(client, pid, "미해결 복선", status="보류", disposition="intentional_unresolved")
    _mk_foreshadow(client, pid, "외전 복선", status="회수", disposition="side_story")
    _mk_foreshadow(client, pid, "미분류 복선", status="회수")  # 닫혔으나 미분류

    body = _checklist(client, pid)
    f = body["foreshadows"]
    assert f["total"] == 5
    assert [o["title"] for o in f["open"]] == ["미회수 복선"]
    assert f["open"][0]["status"] == "설치"
    assert f["by_disposition"] == {
        "resolved": 1, "intentional_unresolved": 1,
        "side_story": 1, "closed_unclassified": 1,
    }


def test_checklist_pending_refine_runs(client_db):
    client, Session = client_db
    pid = _mk_project(client)
    c1 = _mk_chapter(client, pid, "1화")
    c2 = _mk_chapter(client, pid, "2화")
    with Session() as db:
        db.add(RefineRun(chapter_id=c1["id"], route_hint="standard", result_text="a", accepted=False))
        db.add(RefineRun(chapter_id=c1["id"], route_hint="light", result_text="b", accepted=True))
        db.add(RefineRun(chapter_id=c2["id"], route_hint="light", result_text="c", accepted=False))
        db.commit()

    assert _checklist(client, pid)["pending_refine_runs"] == 2


def test_checklist_broken_evidence_links(client):
    pid = _mk_project(client)
    ch = _mk_chapter(client, pid, "1화", content="검을 뽑아 달렸다")
    cid = ch["id"]
    client.put(
        f"/api/v1/chapters/{cid}/goal",
        json={
            "goal": {"core_events": ["검을 뽑는다"], "next_hook": "그림자"},
            "expected_goal_version": None,
        },
    )
    r = client.post(
        f"/api/v1/chapters/{cid}/evidence-links",
        json={"goal_field": "core_events", "item_index": 0, "excerpt": "검을 뽑아"},
    )
    assert r.status_code == 201, r.text

    assert _checklist(client, pid)["broken_evidence_links"] == 0

    # 원문에서 발췌를 지워 링크 파손
    client.put(
        f"/api/v1/chapters/{cid}/content",
        json={"content_md": "그냥 달렸다", "expected_revision": ch["revision"]},
    )
    assert _checklist(client, pid)["broken_evidence_links"] == 1


def test_checklist_finale_goal_missing_ending(client):
    pid = _mk_project(client)
    c1 = _mk_chapter(client, pid, "최종화")
    # 부분 저장 허용 — series_finale인데 ending_intent 없음
    r = client.put(
        f"/api/v1/chapters/{c1['id']}/goal",
        json={
            "goal": {"emotion_goal": "여운"},
            "expected_goal_version": None,
            "episode_purpose": "series_finale",
        },
    )
    assert r.status_code == 200, r.text
    c2 = _mk_chapter(client, pid, "에필로그")
    r = client.put(
        f"/api/v1/chapters/{c2['id']}/goal",
        json={
            "goal": {"ending_intent": "주인공은 고향으로"},
            "expected_goal_version": None,
            "episode_purpose": "series_finale",
        },
    )
    assert r.status_code == 200, r.text

    missing = _checklist(client, pid)["finale_goals_missing_ending"]
    assert missing == [{"chapter_id": c1["id"], "title": "최종화"}]


def test_checklist_is_derived_and_read_only(client):
    pid = _mk_project(client)
    _mk_chapter(client, pid, "1화", content="본문")
    before = _checklist(client, pid)
    _checklist(client, pid)  # 재조회
    assert _checklist(client, pid) == before


# ---------- 완결본 생성 ----------

def test_create_final_edition_assembles_chapters(client):
    pid = _mk_project(client)
    # 생성 순서와 sort_order를 거꾸로 — 조립 순서는 sort_order를 따라야 한다
    c2 = _mk_chapter(client, pid, "2화", content="둘째 본문", sort_order=2.0)
    c1 = _mk_chapter(client, pid, "1화", content="첫째 본문", sort_order=1.0)
    _confirm(client, c1["id"])

    r = client.post(f"/api/v1/projects/{pid}/final-editions", json={"label": "1차 완결본"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["label"] == "1차 완결본"
    assert body["serial_state"] == "ongoing"
    assert body["chapter_count"] == 2
    assert body["total_chars"] == len(body["content_md"])
    assert "## 1화" in body["content_md"] and "첫째 본문" in body["content_md"]
    assert body["content_md"].index("첫째 본문") < body["content_md"].index("둘째 본문")
    # manifest — 캡처 순서=sort_order, 각 항목에 상태 기록
    assert [m["chapter_id"] for m in body["manifest"]] == [c1["id"], c2["id"]]
    m1 = body["manifest"][0]
    assert m1["title"] == "1화"
    assert m1["revision"] == 1
    assert m1["flow_stage"] == "confirmed"
    assert body["manifest"][1]["flow_stage"] == "planning"
    # checklist는 캡처 시점 동결본
    assert body["checklist"]["chapters"]["by_stage"]["confirmed"] == 1


def test_create_final_edition_label_optional_and_blank_normalizes(client):
    pid = _mk_project(client)
    r = client.post(f"/api/v1/projects/{pid}/final-editions", json={})
    assert r.status_code == 201
    assert r.json()["label"] is None
    r = client.post(f"/api/v1/projects/{pid}/final-editions", json={"label": "   "})
    assert r.status_code == 201
    assert r.json()["label"] is None


def test_create_final_edition_missing_project_404_and_empty_project(client):
    assert client.post("/api/v1/projects/9999/final-editions", json={}).status_code == 404
    pid = _mk_project(client)
    r = client.post(f"/api/v1/projects/{pid}/final-editions", json={})
    assert r.status_code == 201
    assert r.json()["chapter_count"] == 0
    assert r.json()["manifest"] == []


def test_final_edition_is_immutable_snapshot(client):
    pid = _mk_project(client)
    ch = _mk_chapter(client, pid, "1화", content="검을 뽑아 원래 본문")
    cid = ch["id"]
    client.put(
        f"/api/v1/chapters/{cid}/goal",
        json={
            "goal": {"core_events": ["검을 뽑는다"], "next_hook": "그림자"},
            "expected_goal_version": None,
        },
    )
    r = client.post(
        f"/api/v1/chapters/{cid}/evidence-links",
        json={"goal_field": "core_events", "item_index": 0, "excerpt": "검을 뽑아"},
    )
    assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/projects/{pid}/final-editions", json={"label": "보존본"})
    eid = r.json()["id"]
    assert r.json()["checklist"]["broken_evidence_links"] == 0
    assert r.json()["checklist"]["foreshadows"]["total"] == 0

    # 원고 수정(링크 파손) + 복선 추가 + 회차 삭제 후에도 스냅샷은 그대로
    client.put(
        f"/api/v1/chapters/{cid}/content",
        json={"content_md": "바뀐 본문", "expected_revision": ch["revision"]},
    )
    _mk_foreshadow(client, pid, "나중 복선")
    detail = client.get(f"/api/v1/projects/{pid}/final-editions/{eid}").json()
    assert "검을 뽑아 원래 본문" in detail["content_md"]
    assert "바뀐 본문" not in detail["content_md"]
    # checklist_json은 캡처 시점 동결본 — 이후 변경이 반영되지 않는다
    live = _checklist(client, pid)
    assert live["broken_evidence_links"] == 1
    assert live["foreshadows"]["total"] == 1
    assert detail["checklist"]["broken_evidence_links"] == 0
    assert detail["checklist"]["foreshadows"]["total"] == 0

    assert client.delete(f"/api/v1/chapters/{cid}").status_code == 204
    detail = client.get(f"/api/v1/projects/{pid}/final-editions/{eid}").json()
    assert "검을 뽑아 원래 본문" in detail["content_md"]


# ---------- 목록·상세·삭제 ----------

def test_list_final_editions_metadata_only(client):
    pid = _mk_project(client)
    _mk_chapter(client, pid, "1화", content="본문")
    client.post(f"/api/v1/projects/{pid}/final-editions", json={"label": "첫째"})
    client.post(f"/api/v1/projects/{pid}/final-editions", json={"label": "둘째"})

    r = client.get(f"/api/v1/projects/{pid}/final-editions")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    assert rows[0]["label"] == "둘째"  # created_at 내림차순
    for row in rows:
        assert "content_md" not in row
        assert "manifest" not in row
        assert "checklist" not in row
        assert row["chapter_count"] == 1


def test_list_final_editions_cross_project_isolation(client):
    pid = _mk_project(client)
    other = _mk_project(client)
    client.post(f"/api/v1/projects/{pid}/final-editions", json={"label": "A본"})
    client.post(f"/api/v1/projects/{other}/final-editions", json={"label": "B본"})

    mine = client.get(f"/api/v1/projects/{pid}/final-editions").json()
    assert [e["label"] for e in mine] == ["A본"]
    theirs = client.get(f"/api/v1/projects/{other}/final-editions").json()
    assert [e["label"] for e in theirs] == ["B본"]


def test_get_final_edition_detail_and_cross_project_404(client):
    pid = _mk_project(client)
    other = _mk_project(client)
    eid = client.post(f"/api/v1/projects/{pid}/final-editions", json={}).json()["id"]

    r = client.get(f"/api/v1/projects/{pid}/final-editions/{eid}")
    assert r.status_code == 200
    assert "content_md" in r.json() and "manifest" in r.json() and "checklist" in r.json()
    assert client.get(f"/api/v1/projects/{other}/final-editions/{eid}").status_code == 404
    assert client.get(f"/api/v1/projects/{pid}/final-editions/9999").status_code == 404
    assert client.get(f"/api/v1/projects/9999/final-editions/{eid}").status_code == 404


def test_delete_final_edition(client):
    pid = _mk_project(client)
    other = _mk_project(client)
    eid = client.post(f"/api/v1/projects/{pid}/final-editions", json={}).json()["id"]

    assert client.delete(f"/api/v1/projects/{other}/final-editions/{eid}").status_code == 404
    assert client.delete(f"/api/v1/projects/{pid}/final-editions/{eid}").status_code == 204
    assert client.get(f"/api/v1/projects/{pid}/final-editions/{eid}").status_code == 404
    assert client.delete(f"/api/v1/projects/{pid}/final-editions/{eid}").status_code == 404
    assert client.get(f"/api/v1/projects/{pid}/final-editions").json() == []


def test_final_edition_records_serial_state_at_capture(client):
    pid = _mk_project(client)
    r = client.patch(f"/api/v1/projects/{pid}", json={"serial_state": "completed"})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/projects/{pid}/final-editions", json={})
    assert r.json()["serial_state"] == "completed"
    client.patch(f"/api/v1/projects/{pid}", json={"serial_state": "ongoing"})
    eid = r.json()["id"]
    assert client.get(f"/api/v1/projects/{pid}/final-editions/{eid}").json()["serial_state"] == "completed"
