"""프로젝트 CRUD 통합 테스트."""


def test_create_and_list_projects(client):
    r = client.post("/api/v1/projects", json={"title": "내 작품", "genre": "판타지"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == "내 작품"
    assert body["id"] > 0

    r = client.get("/api/v1/projects")
    assert r.status_code == 200
    assert "내 작품" in [p["title"] for p in r.json()]


def test_create_project_requires_title(client):
    assert client.post("/api/v1/projects", json={}).status_code == 422


def test_get_update_delete_project(client):
    pid = client.post("/api/v1/projects", json={"title": "원래"}).json()["id"]

    assert client.get(f"/api/v1/projects/{pid}").json()["title"] == "원래"

    r = client.patch(f"/api/v1/projects/{pid}", json={"synopsis": "시놉시스", "genre": "무협"})
    body = r.json()
    assert body["synopsis"] == "시놉시스" and body["genre"] == "무협" and body["title"] == "원래"

    assert client.delete(f"/api/v1/projects/{pid}").status_code == 204
    assert client.get(f"/api/v1/projects/{pid}").status_code == 404


def test_get_missing_project_returns_404(client):
    assert client.get("/api/v1/projects/9999").status_code == 404


def test_delete_project_cascades_chapters(client):
    pid = client.post("/api/v1/projects", json={"title": "삭제 캐스케이드"}).json()["id"]
    cid = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화"}).json()["id"]

    client.delete(f"/api/v1/projects/{pid}")
    assert client.get(f"/api/v1/chapters/{cid}").status_code == 404


def test_delete_project_cascades_characters_with_relations(client):
    """회귀: 관계(relationships)가 있어도 프로젝트 삭제가 FK 오류 없이 통과해야 한다."""
    pid = client.post("/api/v1/projects", json={"title": "관계 캐스케이드"}).json()["id"]
    a = client.post(f"/api/v1/projects/{pid}/characters", json={"name": "A"}).json()
    b = client.post(f"/api/v1/projects/{pid}/characters", json={"name": "B"}).json()
    client.post(f"/api/v1/characters/relations",
                json={"from_character_id": a["id"], "to_character_id": b["id"], "label": "주군-가신"})

    resp = client.delete(f"/api/v1/projects/{pid}")
    assert resp.status_code == 204, resp.text
    assert client.get(f"/api/v1/characters/{a['id']}").status_code == 404
    assert client.get(f"/api/v1/characters/{b['id']}").status_code == 404


def test_list_projects_includes_card_aggregates(client):
    """목록 응답에 회차 수·누적 글자 수 집계가 포함된다(홈 카드용)."""
    pid = client.post("/api/v1/projects", json={"title": "집계"}).json()["id"]
    c1 = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화"}).json()
    client.put(f"/api/v1/chapters/{c1['id']}/content", json={"content_md": "가나다라마바사", "expected_revision": 0})  # 공백제외 7자
    client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "2화"})

    rows = client.get("/api/v1/projects").json()
    row = next(r for r in rows if r["id"] == pid)
    assert row["chapter_count"] == 2
    assert row["total_chars"] == 7
