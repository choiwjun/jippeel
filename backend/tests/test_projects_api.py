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
