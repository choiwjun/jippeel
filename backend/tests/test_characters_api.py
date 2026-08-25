"""캐릭터 카드 API 테스트 (FR-201~205 / Sprint 2)."""


def _create_project(client) -> int:
    res = client.post("/api/v1/projects", json={"title": "테스트 작품"})
    assert res.status_code == 201
    return res.json()["id"]


def _create_character(client, pid: int, name: str = "주인공", **kwargs) -> dict:
    payload = {"name": name, **kwargs}
    res = client.post(f"/api/v1/projects/{pid}/characters", json=payload)
    assert res.status_code == 201
    return res.json()


class TestCharacterCRUD:
    def test_create_and_list(self, client):
        pid = _create_project(client)
        created = _create_character(
            client,
            pid,
            name="이설",
            aliases=["설아"],
            role="주연",
            speech_style="차분한 존댓말",
            card_json={"species": "인간"},
        )
        assert created["project_id"] == pid
        assert created["aliases"] == ["설아"]
        assert created["role"] == "주연"
        assert created["card_json"] == {"species": "인간"}

        res = client.get(f"/api/v1/projects/{pid}/characters")
        assert res.status_code == 200
        assert [c["name"] for c in res.json()] == ["이설"]

    def test_get_update_delete(self, client):
        pid = _create_project(client)
        chid = _create_character(client, pid)["id"]

        res = client.get(f"/api/v1/characters/{chid}")
        assert res.status_code == 200

        res = client.patch(f"/api/v1/characters/{chid}", json={"personality": "냉정", "role": "조연"})
        assert res.status_code == 200
        body = res.json()
        assert body["personality"] == "냉정"
        assert body["role"] == "조연"
        assert body["name"] == "주인공"  # 미지정 필드 유지

        res = client.delete(f"/api/v1/characters/{chid}")
        assert res.status_code == 204
        assert client.get(f"/api/v1/characters/{chid}").status_code == 404

    def test_create_in_missing_project_404(self, client):
        res = client.post("/api/v1/projects/9999/characters", json={"name": "x"})
        assert res.status_code == 404

    def test_name_required(self, client):
        pid = _create_project(client)
        res = client.post(f"/api/v1/projects/{pid}/characters", json={"name": ""})
        assert res.status_code == 422


class TestCardJsonPatch:
    def test_merge_patch_nested(self, client):
        pid = _create_project(client)
        chid = _create_character(
            client, pid, card_json={"name": "이설", "stats": {"hp": 100, "mp": 30}}
        )["id"]

        # 부분 업데이트: stats.mp만 변경, 나머지 유지
        res = client.patch(f"/api/v1/characters/{chid}/card_json", json={"patch": {"stats": {"mp": 50}}})
        assert res.status_code == 200
        assert res.json()["card_json"] == {"name": "이설", "stats": {"hp": 100, "mp": 50}}

        # None 값 키 제거
        res = client.patch(f"/api/v1/characters/{chid}/card_json", json={"patch": {"name": None}})
        assert res.status_code == 200
        assert res.json()["card_json"] == {"stats": {"hp": 100, "mp": 50}}

    def test_patch_on_empty_card_json(self, client):
        pid = _create_project(client)
        chid = _create_character(client, pid)["id"]
        res = client.patch(f"/api/v1/characters/{chid}/card_json", json={"patch": {"a": 1}})
        assert res.status_code == 200
        assert res.json()["card_json"] == {"a": 1}


class TestRelationships:
    def test_create_list_delete_relation(self, client):
        pid = _create_project(client)
        a = _create_character(client, pid, name="A")["id"]
        b = _create_character(client, pid, name="B")["id"]

        res = client.post(
            f"/api/v1/projects/{pid}/characters/relations",
            json={"from_character_id": a, "to_character_id": b, "label": "주군-가신", "note": "맹약"},
        )
        assert res.status_code == 201
        rid = res.json()["id"]

        res = client.get(f"/api/v1/characters/{a}/relations")
        assert res.status_code == 200
        assert len(res.json()) == 1
        assert res.json()[0]["label"] == "주군-가신"

        res = client.delete(f"/api/v1/relations/{rid}")
        assert res.status_code == 204
        assert client.get(f"/api/v1/characters/{a}/relations").json() == []

    def test_relation_across_projects_422(self, client):
        pid1 = _create_project(client)
        pid2 = _create_project(client)
        a = _create_character(client, pid1)["id"]
        other = _create_character(client, pid2, name="타작품")["id"]

        res = client.post(
            f"/api/v1/projects/{pid1}/characters/relations",
            json={"from_character_id": a, "to_character_id": other},
        )
        assert res.status_code == 422

    def test_delete_missing_relation_404(self, client):
        assert client.delete("/api/v1/relations/9999").status_code == 404
