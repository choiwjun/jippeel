"""T-002 chapter.volume nullable 전환 검증 (기술설계 §4.2 변경 1 — Q1 결정안)."""


def _mk_project(client) -> int:
    return client.post("/api/v1/projects", json={"title": "테스트 작품"}).json()["id"]


def _mk_chapter(client, pid: int, **kwargs) -> dict:
    return client.post(f"/api/v1/projects/{pid}/chapters", json=kwargs).json()


def test_create_chapter_without_volume_is_null(client):
    pid = _mk_project(client)
    flat = _mk_chapter(client, pid, title="평면 회차")
    assert flat["volume"] is None


def test_create_chapter_with_explicit_volume_kept(client):
    pid = _mk_project(client)
    body = _mk_chapter(client, pid, title="1권 1화", volume=1)
    assert body["volume"] == 1


def test_patch_volume_to_null_and_back(client):
    """PATCH로 권 속성 제거(None) 후 재부여 가능 — 평면 회차 전환."""
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid, volume=2)["id"]
    r = client.patch(f"/api/v1/chapters/{cid}", json={"volume": None})
    assert r.status_code == 200
    assert r.json()["volume"] is None
    r = client.patch(f"/api/v1/chapters/{cid}", json={"volume": 3})
    assert r.json()["volume"] == 3


def test_list_orders_null_volume_last(client):
    pid = _mk_project(client)
    _mk_chapter(client, pid, title="flat", sort_order=0.0)          # volume NULL
    _mk_chapter(client, pid, title="v2", volume=2, sort_order=0.0)
    _mk_chapter(client, pid, title="v1", volume=1, sort_order=0.0)
    items = client.get(f"/api/v1/projects/{pid}/chapters").json()
    assert [c["title"] for c in items] == ["v1", "v2", "flat"]


def test_reorder_sets_null_volume_sorted_last(client):
    pid = _mk_project(client)
    a = _mk_chapter(client, pid, title="a")                          # NULL
    b = _mk_chapter(client, pid, title="b", volume=1)
    items = client.patch(
        f"/api/v1/projects/{pid}/chapters/reorder",
        json={"items": [{"id": b["id"], "sort_order": 5.0}, {"id": a["id"], "sort_order": 1.0}]},
    ).json()
    titles = [c["title"] for c in items]
    # sort_order 기준으로는 a가 먼저지만 volume NULL은 항상 마지막
    assert titles == ["b", "a"]
    assert [c["volume"] for c in items] == [1, None]


def test_reorder_can_assign_null_via_explicit_items(client):
    """reorder에서 volume 미지정 시 기존 값 유지, 명시적 null은 유지된다(변경 없음)."""
    pid = _mk_project(client)
    a = _mk_chapter(client, pid, title="a")
    items = client.patch(
        f"/api/v1/projects/{pid}/chapters/reorder",
        json={"items": [{"id": a["id"], "sort_order": 2.0}]},
    ).json()
    assert items[0]["volume"] is None
    assert items[0]["sort_order"] == 2.0
