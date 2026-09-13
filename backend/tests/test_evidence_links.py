"""D03-4 근거 연결 — chapter_goal_evidence_links 계약 테스트.

- 목표 필드(core_events/character_choices/cost) ↔ 원문 발췌의 수동 링크.
- 읽기 시 파생 상태(원문 파손·목표 드리프트)만 계산 — 자동 판정 없음(§6.3).
"""

EXCERPT = "주인공이 검을 뽑았다"
CONTENT = f"첫 문단이다. {EXCERPT} 그리고 달렸다."


def _mk_project(client) -> int:
    return client.post("/api/v1/projects", json={"title": "근거 작품"}).json()["id"]


def _mk_chapter(client, pid: int, content: str = CONTENT) -> dict:
    ch = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화"}).json()
    client.put(
        f"/api/v1/chapters/{ch['id']}/content",
        json={"content_md": content, "expected_revision": ch["revision"]},
    )
    return client.get(f"/api/v1/chapters/{ch['id']}").json()


def _put_goal(client, cid: int, expected, **goal_fields) -> dict:
    return client.put(
        f"/api/v1/chapters/{cid}/goal",
        json={"goal": goal_fields, "expected_goal_version": expected},
    ).json()


def _seed_goal(client, cid: int):
    return _put_goal(
        client, cid, None,
        emotion_goal="긴장감",
        core_events=["검을 뽑는다", "도망친다"],
        character_choices=["공주를 구한다"],
        cost="왼팔을 잃는다",
        next_hook="그림자 등장",
    )


def _link(client, cid: int, **body):
    return client.post(f"/api/v1/chapters/{cid}/evidence-links", json=body)


# ---------- 생성 ----------

def test_create_link_anchors_current_goal_version(client):
    cid = _mk_chapter(client, _mk_project(client))["id"]
    _seed_goal(client, cid)

    r = _link(client, cid, goal_field="core_events", item_index=0, excerpt=EXCERPT)
    assert r.status_code == 201
    body = r.json()
    assert body["goal_version"] == 1
    assert body["goal_item_text"] == "검을 뽑는다"
    assert body["excerpt"] == EXCERPT

    # 스칼라 필드(cost)는 item_index 없이
    r = _link(client, cid, goal_field="cost", excerpt="달렸다")
    assert r.status_code == 201
    assert r.json()["goal_field"] == "cost"
    assert r.json()["item_index"] is None
    assert r.json()["goal_item_text"] == "왼팔을 잃는다"

    # 두 번째 목록 필드(character_choices)도 정상 생성
    r = _link(client, cid, goal_field="character_choices", item_index=0, excerpt=EXCERPT)
    assert r.status_code == 201
    assert r.json()["goal_item_text"] == "공주를 구한다"


def test_create_link_rejections(client):
    cid = _mk_chapter(client, _mk_project(client))["id"]
    _seed_goal(client, cid)

    # 사전 외 필드
    assert _link(client, cid, goal_field="emotion_goal", excerpt=EXCERPT).status_code == 422
    # 목록 필드에 item_index 누락
    assert _link(client, cid, goal_field="core_events", excerpt=EXCERPT).status_code == 422
    # 범위 밖 인덱스
    assert _link(client, cid, goal_field="core_events", item_index=9, excerpt=EXCERPT).status_code == 422
    # 스칼라에 인덱스 제공
    assert _link(client, cid, goal_field="cost", item_index=0, excerpt="달렸다").status_code == 422
    # 빈 excerpt / 원문에 없는 excerpt
    assert _link(client, cid, goal_field="cost", excerpt="  ").status_code == 422
    assert _link(client, cid, goal_field="cost", excerpt="없는 문장").status_code == 422
    # 음수 인덱스 / 500자 초과 / 알 수 없는 추가 키
    assert _link(client, cid, goal_field="core_events", item_index=-1, excerpt=EXCERPT).status_code == 422
    assert _link(client, cid, goal_field="cost", excerpt=EXCERPT * 100).status_code == 422
    assert _link(client, cid, goal_field="cost", excerpt=EXCERPT, bogus=1).status_code == 422


def test_link_endpoints_404_on_missing_chapter(client):
    missing = 999999
    assert client.get(f"/api/v1/chapters/{missing}/evidence-links").status_code == 404
    assert _link(client, missing, goal_field="cost", excerpt=EXCERPT).status_code == 404
    assert client.delete(f"/api/v1/chapters/{missing}/evidence-links/1").status_code == 404


def test_create_link_requires_existing_goal_item(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]

    # 목표 자체가 없으면 422
    assert _link(client, cid, goal_field="cost", excerpt=EXCERPT).status_code == 422

    # 필드가 저장돼 있어도 해당 항목이 비어 있으면 422
    _put_goal(client, cid, None, core_events=["하나뿐"])
    assert _link(client, cid, goal_field="character_choices", item_index=0, excerpt=EXCERPT).status_code == 422


# ---------- 파생 상태 ----------

def _get_links(client, cid: int):
    r = client.get(f"/api/v1/chapters/{cid}/evidence-links")
    assert r.status_code == 200
    return r.json()["links"]


def test_link_manuscript_status_derives_from_content(client):
    pid = _mk_project(client)
    ch = _mk_chapter(client, pid)
    cid = ch["id"]
    _seed_goal(client, cid)
    link_id = _link(client, cid, goal_field="core_events", item_index=0, excerpt=EXCERPT).json()["id"]

    (link,) = _get_links(client, cid)
    assert link["id"] == link_id
    assert link["manuscript_status"] == "intact"
    assert link["goal_status"] == "unchanged"
    assert link["current_goal_version"] == 1

    # 원문에서 excerpt 제거 → broken (expected_revision은 현재 revision)
    r = client.put(
        f"/api/v1/chapters/{cid}/content",
        json={"content_md": "전부 다른 이야기", "expected_revision": ch["revision"]},
    )
    assert r.status_code == 200
    (link,) = _get_links(client, cid)
    assert link["manuscript_status"] == "broken"


def test_link_goal_status_derives_from_current_goal(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    _seed_goal(client, cid)
    _link(client, cid, goal_field="core_events", item_index=0, excerpt=EXCERPT)

    # 목표 v2 — 인덱스 0 항목 텍스트 변경 → drifted
    _put_goal(client, cid, 1, core_events=["칼을 든다", "도망친다"],
              character_choices=["공주를 구한다"], cost="왼팔을 잃는다")
    (link,) = _get_links(client, cid)
    assert link["goal_status"] == "drifted"
    assert link["current_goal_version"] == 2
    assert link["goal_version"] == 1  # 앵커는 생성 시점 유지

    # 목표 삭제 → goal_deleted
    client.delete(f"/api/v1/chapters/{cid}/goal")
    (link,) = _get_links(client, cid)
    assert link["goal_status"] == "goal_deleted"


def test_link_goal_status_drifts_when_item_removed(client):
    """텍스트 변경뿐 아니라 항목 누락(목록 축소)도 drifted다."""
    cid = _mk_chapter(client, _mk_project(client))["id"]
    _seed_goal(client, cid)
    _link(client, cid, goal_field="core_events", item_index=1, excerpt=EXCERPT)

    # 목표 v2 — core_events에서 인덱스 1 항목("도망친다") 제거
    _put_goal(client, cid, 1, core_events=["검을 뽑는다"],
              character_choices=["공주를 구한다"], cost="왼팔을 잃는다")
    (link,) = _get_links(client, cid)
    assert link["goal_status"] == "drifted"
    assert link["current_goal_version"] == 2


# ---------- 삭제·보존 ----------

def test_delete_link_and_404s(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    _seed_goal(client, cid)
    link_id = _link(client, cid, goal_field="cost", excerpt="달렸다").json()["id"]

    # 다른 회차 경로로는 지울 수 없다
    cid2 = _mk_chapter(client, pid)["id"]
    assert client.delete(f"/api/v1/chapters/{cid2}/evidence-links/{link_id}").status_code == 404

    assert client.delete(f"/api/v1/chapters/{cid}/evidence-links/{link_id}").status_code == 204
    assert _get_links(client, cid) == []
    assert client.delete(f"/api/v1/chapters/{cid}/evidence-links/{link_id}").status_code == 404


def test_links_do_not_touch_goal_or_manuscript(client):
    pid = _mk_project(client)
    ch = _mk_chapter(client, pid)
    cid = ch["id"]
    _seed_goal(client, cid)
    before = client.get(f"/api/v1/chapters/{cid}").json()

    link_id = _link(client, cid, goal_field="core_events", item_index=1, excerpt=EXCERPT).json()["id"]
    after = client.get(f"/api/v1/chapters/{cid}").json()
    assert after["revision"] == before["revision"]
    goal = client.get(f"/api/v1/chapters/{cid}/goal").json()
    assert goal["goal"]["goal_version"] == 1

    # 삭제도 원고 revision·목표 버전을 건드리지 않는다
    assert client.delete(f"/api/v1/chapters/{cid}/evidence-links/{link_id}").status_code == 204
    after = client.get(f"/api/v1/chapters/{cid}").json()
    assert after["revision"] == before["revision"]
    goal = client.get(f"/api/v1/chapters/{cid}/goal").json()
    assert goal["goal"]["goal_version"] == 1


def test_links_cascade_with_chapter(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    _seed_goal(client, cid)
    _link(client, cid, goal_field="cost", excerpt="달렸다")

    assert client.delete(f"/api/v1/chapters/{cid}").status_code == 204
    # 회차가 없으므로 링크 조회도 404
    assert client.get(f"/api/v1/chapters/{cid}/evidence-links").status_code == 404
