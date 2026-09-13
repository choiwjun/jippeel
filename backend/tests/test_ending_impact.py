"""D03-7 결말 변경 영향 — projects.ending_* + /projects/{pid}/ending-impact 계약 테스트.

- 결말 후보는 작품 수준 저장값 — 잠글 수 있지만 변경 가능.
- ending_updated_at은 값이 실제로 바뀐 시각만 기록한다.
- 영향 표시는 파생 읽기 — 자동 판정 없음.
"""


def _mk_project(client) -> int:
    return client.post("/api/v1/projects", json={"title": "결말 작품"}).json()["id"]


def _mk_chapter(client, pid: int, title: str = "1화") -> dict:
    return client.post(
        f"/api/v1/projects/{pid}/chapters", json={"title": title}
    ).json()


def _patch(client, pid: int, **fields):
    return client.patch(f"/api/v1/projects/{pid}", json=fields)


def _impact(client, pid: int) -> dict:
    r = client.get(f"/api/v1/projects/{pid}/ending-impact")
    assert r.status_code == 200, r.text
    return r.json()


# ---------- 결말 후보 저장·잠금 ----------

def test_project_out_exposes_ending_fields(client):
    pid = _mk_project(client)
    body = client.get(f"/api/v1/projects/{pid}").json()
    assert body["ending_intent"] is None
    assert body["ending_locked"] is False
    assert body["ending_updated_at"] is None


def test_set_ending_intent_records_timestamp(client):
    pid = _mk_project(client)
    r = _patch(client, pid, ending_intent="주인공은 고향으로")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ending_intent"] == "주인공은 고향으로"
    assert body["ending_updated_at"] is not None


def test_same_value_does_not_update_timestamp(client):
    pid = _mk_project(client)
    first = _patch(client, pid, ending_intent="결말 A").json()["ending_updated_at"]
    second = _patch(client, pid, ending_intent="결말 A").json()["ending_updated_at"]
    assert second == first


def test_changed_value_updates_timestamp_and_clear(client):
    pid = _mk_project(client)
    first = _patch(client, pid, ending_intent="결말 A").json()["ending_updated_at"]
    r = _patch(client, pid, ending_intent="결말 B")
    body = r.json()
    assert body["ending_intent"] == "결말 B"
    assert body["ending_updated_at"] != first
    # 명시적 null 지우기 — 변경으로 간주해 시각 갱신
    cleared = _patch(client, pid, ending_intent=None).json()
    assert cleared["ending_intent"] is None
    assert cleared["ending_updated_at"] != body["ending_updated_at"]


def test_locked_ending_rejects_change_with_409(client):
    pid = _mk_project(client)
    _patch(client, pid, ending_intent="결말 A")
    r = _patch(client, pid, ending_locked=True)
    assert r.status_code == 200
    assert r.json()["ending_locked"] is True

    r = _patch(client, pid, ending_intent="결말 B")
    assert r.status_code == 409
    # 잠긴 상태에서 동일값은 변경이 아니므로 허용
    r = _patch(client, pid, ending_intent="결말 A")
    assert r.status_code == 200
    # 같은 요청에 해제를 포함하면 허용 — 잠금은 실수 방지지 금지가 아니다
    r = _patch(client, pid, ending_locked=False, ending_intent="결말 B")
    assert r.status_code == 200
    assert r.json()["ending_intent"] == "결말 B"
    assert r.json()["ending_locked"] is False


def test_null_and_blank_edge_cases(client):
    pid = _mk_project(client)
    # 명시적 ending_locked: null — NOT NULL 컬럼이므로 422(500 아님)
    r = _patch(client, pid, ending_locked=None)
    assert r.status_code == 422
    # 빈 문자열 결말은 null로 정규화
    _patch(client, pid, ending_intent="결말 A")
    r = _patch(client, pid, ending_intent="")
    assert r.status_code == 200
    assert r.json()["ending_intent"] is None


def test_lock_toggle_only_and_partial_patch_preserves(client):
    pid = _mk_project(client)
    _patch(client, pid, ending_intent="결말 A", serial_state="hiatus")
    r = _patch(client, pid, ending_locked=True)
    body = r.json()
    assert body["ending_intent"] == "결말 A"
    assert body["serial_state"] == "hiatus"
    assert body["ending_locked"] is True


# ---------- 변경 영향(파생) ----------

def test_impact_missing_project_404(client):
    assert client.get("/api/v1/projects/9999/ending-impact").status_code == 404


def test_impact_lists_open_foreshadows_only(client):
    pid = _mk_project(client)
    client.post(
        f"/api/v1/projects/{pid}/foreshadows",
        json={"title": "미해결 복선", "status": "설치"},
    )
    client.post(
        f"/api/v1/projects/{pid}/foreshadows",
        json={"title": "해결 복선", "status": "회수", "disposition": "resolved"},
    )
    client.post(
        f"/api/v1/projects/{pid}/foreshadows",
        json={"title": "보류 복선", "status": "보류"},
    )
    body = _impact(client, pid)
    assert [f["title"] for f in body["open_foreshadows"]] == ["미해결 복선"]
    assert body["ending_intent"] is None
    assert body["ending_locked"] is False
    assert body["stale_goal_chapters"] == []  # ending_updated_at 없음 → 비교 기준 없음


def test_impact_stale_goal_chapters(client):
    pid = _mk_project(client)
    c1 = _mk_chapter(client, pid, "1화")
    c2 = _mk_chapter(client, pid, "2화")
    # 결말 설정 전에 저장된 목표 — 이후 결말 변경 시 stale
    r = client.put(
        f"/api/v1/chapters/{c1['id']}/goal",
        json={"goal": {"emotion_goal": "긴장"}, "expected_goal_version": None},
    )
    assert r.status_code == 200, r.text
    _patch(client, pid, ending_intent="결말 A")
    # 결말 변경 이후에 저장된 목표 — stale 아님
    r = client.put(
        f"/api/v1/chapters/{c2['id']}/goal",
        json={"goal": {"emotion_goal": "여운"}, "expected_goal_version": None},
    )
    assert r.status_code == 200, r.text

    stale = _impact(client, pid)["stale_goal_chapters"]
    assert stale == [{"chapter_id": c1["id"], "title": "1화", "goal_version": 1}]

    # 목표를 다시 저장하면 stale 해소(새 결말 이후 기록)
    r = client.put(
        f"/api/v1/chapters/{c1['id']}/goal",
        json={"goal": {"emotion_goal": "긴장"}, "expected_goal_version": 1},
    )
    assert r.status_code == 200, r.text
    assert _impact(client, pid)["stale_goal_chapters"] == []


def test_impact_finale_chapters(client):
    pid = _mk_project(client)
    c1 = _mk_chapter(client, pid, "최종화")
    client.put(
        f"/api/v1/chapters/{c1['id']}/goal",
        json={
            "goal": {"ending_intent": "주인공은 고향으로"},
            "expected_goal_version": None,
            "episode_purpose": "series_finale",
        },
    )
    c2 = _mk_chapter(client, pid, "진 최종화")
    client.put(
        f"/api/v1/chapters/{c2['id']}/goal",
        json={
            "goal": {"emotion_goal": "여운"},
            "expected_goal_version": None,
            "episode_purpose": "series_finale",
        },
    )
    c3 = _mk_chapter(client, pid, "일반 회차")
    client.put(
        f"/api/v1/chapters/{c3['id']}/goal",
        json={"goal": {"next_hook": "후크"}, "expected_goal_version": None},
    )

    finale = _impact(client, pid)["finale_chapters"]
    assert finale == [
        {"chapter_id": c1["id"], "title": "최종화", "has_ending_intent": True},
        {"chapter_id": c2["id"], "title": "진 최종화", "has_ending_intent": False},
    ]


def test_impact_is_derived_and_read_only(client):
    pid = _mk_project(client)
    _patch(client, pid, ending_intent="결말 A")
    before = _impact(client, pid)
    _impact(client, pid)
    assert _impact(client, pid) == before
    assert client.get(f"/api/v1/projects/{pid}").json()["ending_intent"] == "결말 A"
