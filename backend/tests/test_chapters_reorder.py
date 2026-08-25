"""bulk 회차 순서 변경 엔드포인트 테스트 (PATCH /projects/{pid}/chapters/reorder)."""


def _setup_chapters(client):
    res = client.post("/api/v1/projects", json={"title": "reorder 테스트"})
    pid = res.json()["id"]
    ids = []
    for i in range(3):
        res = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": f"{i}화"})
        ids.append(res.json()["id"])
    return pid, ids


class TestReorder:
    def test_bulk_sort_order_change(self, client):
        pid, ids = _setup_chapters(client)

        res = client.patch(
            f"/api/v1/projects/{pid}/chapters/reorder",
            json={"items": [{"id": ids[0], "sort_order": 30}, {"id": ids[2], "sort_order": 10}]},
        )
        assert res.status_code == 200
        ordered = res.json()
        # sort_order 기준 정렬: ids[2](10) < ids[1](0 아님 — 미변경 0.0)... 확인
        by_id = {c["id"]: c for c in ordered}
        assert by_id[ids[0]]["sort_order"] == 30
        assert by_id[ids[2]]["sort_order"] == 10

        # 목록 조회도 반영되는지
        res = client.get(f"/api/v1/projects/{pid}/chapters")
        titles = [c["id"] for c in res.json()]
        assert set(titles) == set(ids)

    def test_volume_move_included(self, client):
        pid, ids = _setup_chapters(client)
        res = client.patch(
            f"/api/v1/projects/{pid}/chapters/reorder",
            json={"items": [{"id": ids[1], "volume": 2, "sort_order": 1}]},
        )
        assert res.status_code == 200
        moved = next(c for c in res.json() if c["id"] == ids[1])
        assert moved["volume"] == 2

    def test_foreign_chapter_422(self, client):
        pid, ids = _setup_chapters(client)
        # 다른 프로젝트 소속 회차
        res = client.post("/api/v1/projects", json={"title": "다른 작품"})
        other_pid = res.json()["id"]
        foreign = client.post(f"/api/v1/projects/{other_pid}/chapters", json={"title": "외부"}).json()["id"]

        res = client.patch(
            f"/api/v1/projects/{pid}/chapters/reorder",
            json={"items": [{"id": foreign, "sort_order": 1}]},
        )
        assert res.status_code == 422

    def test_duplicate_ids_422(self, client):
        pid, ids = _setup_chapters(client)
        res = client.patch(
            f"/api/v1/projects/{pid}/chapters/reorder",
            json={"items": [{"id": ids[0], "sort_order": 5}, {"id": ids[0], "sort_order": 6}]},
        )
        assert res.status_code == 422

    def test_empty_items_422(self, client):
        pid, _ = _setup_chapters(client)
        res = client.patch(f"/api/v1/projects/{pid}/chapters/reorder", json={"items": []})
        assert res.status_code == 422

    def test_atomic_no_partial_apply(self, client):
        """일부 id가 유효하지 않으면 어떤 변경도 적용되지 않아야 한다."""
        pid, ids = _setup_chapters(client)
        res = client.patch(
            f"/api/v1/projects/{pid}/chapters/reorder",
            json={"items": [{"id": ids[0], "sort_order": 99}, {"id": 99999, "sort_order": 1}]},
        )
        assert res.status_code == 422
        res = client.get(f"/api/v1/projects/{pid}/chapters")
        assert all(c["sort_order"] == 0.0 for c in res.json())
