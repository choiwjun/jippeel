"""D03-3 완결 분리 — projects.serial_state/serial_completed_at 계약 테스트.

- 회차 flow_stage·status와 독립이다(§6.3 서로 다른 수명주기).
- 관리 라벨이므로 자유 전환 — completed 진입/이탈만 completed_at을 관리한다.
"""


def _mk_project(client, **kwargs) -> dict:
    return client.post("/api/v1/projects", json={"title": "연재 작품", **kwargs}).json()


def _mk_chapter(client, pid: int, **kwargs) -> dict:
    return client.post(f"/api/v1/projects/{pid}/chapters", json=kwargs).json()


def _patch(client, pid: int, **kwargs):
    return client.patch(f"/api/v1/projects/{pid}", json=kwargs)


def _transition(client, cid: int, to_stage: str, expected: str):
    return client.post(
        f"/api/v1/chapters/{cid}/flow/transition",
        json={"to_stage": to_stage, "expected_flow_stage": expected},
    )


# ---------- 기본값·조회 ----------

def test_new_project_defaults_to_ongoing(client):
    p = _mk_project(client)
    assert p["serial_state"] == "ongoing"
    assert p["serial_completed_at"] is None

    listed = client.get("/api/v1/projects").json()
    assert listed[0]["serial_state"] == "ongoing"


# ---------- 전이 ----------

def test_serial_state_transitions_and_completed_at(client):
    pid = _mk_project(client)["id"]

    r = _patch(client, pid, serial_state="hiatus")
    assert r.status_code == 200
    assert r.json()["serial_state"] == "hiatus"
    assert r.json()["serial_completed_at"] is None

    r = _patch(client, pid, serial_state="completed")
    assert r.status_code == 200
    assert r.json()["serial_state"] == "completed"
    first_completed_at = r.json()["serial_completed_at"]
    assert first_completed_at is not None

    # 완결 이탈 → completed_at 제거
    r = _patch(client, pid, serial_state="ongoing")
    assert r.json()["serial_state"] == "ongoing"
    assert r.json()["serial_completed_at"] is None

    # 재진입 → 새 시각 (직전 completed_at과 달라야 한다)
    r = _patch(client, pid, serial_state="completed")
    assert r.json()["serial_completed_at"] is not None
    assert r.json()["serial_completed_at"] != first_completed_at


def test_serial_state_invalid_value_422(client):
    pid = _mk_project(client)["id"]
    r = _patch(client, pid, serial_state="bogus")
    assert r.status_code == 422

    # 명시적 null도 "필드 생략"이 아니라 잘못된 값이다
    r = _patch(client, pid, serial_state=None)
    assert r.status_code == 422


def test_partial_patch_preserves_completed_at(client):
    """serial_state 없는 PATCH는 completed_at을 건드리지 않는다."""
    pid = _mk_project(client)["id"]
    completed_at = _patch(client, pid, serial_state="completed").json()["serial_completed_at"]

    r = _patch(client, pid, title="제목 변경")
    assert r.status_code == 200
    assert r.json()["serial_state"] == "completed"
    assert r.json()["serial_completed_at"] == completed_at


def test_serial_state_patch_preserves_other_fields(client):
    p = _mk_project(client, genre="판타지", synopsis="시놉")
    _patch(client, p["id"], serial_state="hiatus")
    body = client.get(f"/api/v1/projects/{p['id']}").json()
    assert body["genre"] == "판타지"
    assert body["synopsis"] == "시놉"
    assert body["title"] == "연재 작품"


# ---------- 수명주기 독립 ----------

def test_serial_state_independent_of_chapter_flow(client):
    pid = _mk_project(client)["id"]
    cid = _mk_chapter(client, pid)["id"]

    _patch(client, pid, serial_state="completed")
    # 완결이어도 회차 전이는 계속 가능 — 완결은 동결이 아니다
    r = _transition(client, cid, "writing", "planning")
    assert r.status_code == 200

    # 회차 confirmed도 serial_state를 바꾸지 않는다
    _transition(client, cid, "revising", "writing")
    _transition(client, cid, "confirmed", "revising")
    p = client.get(f"/api/v1/projects/{pid}").json()
    assert p["serial_state"] == "completed"

    # 반대 방향: serial_state 변경은 회차를 건드리지 않는다
    _patch(client, pid, serial_state="ongoing")
    ch = client.get(f"/api/v1/chapters/{cid}").json()
    assert ch["status"] == "초고"
    assert client.get(f"/api/v1/chapters/{cid}/flow").json()["flow_stage"] == "confirmed"
