"""Story map contract against isolated synthetic data, without a provider."""
import pytest
from sqlalchemy import event

from app.models import Chapter, ChapterGoal, Project, Scene
from tests.conftest import _db


def seed(client, count=60):
    db = _db(client)
    project = Project(title="지도 합성 작품")
    db.add(project)
    db.flush()
    rows = [Chapter(project_id=project.id, title=f"회차 {i + 1}", volume=1,
                    sort_order=i, content_md="합성 본문" if i % 2 else "",
                    word_count_cache=4 if i % 2 else 0, revision=i,
                    flow_stage="confirmed" if i % 3 == 0 else "planning") for i in range(count)]
    db.add_all(rows)
    db.commit()
    return db, project.id, rows


@pytest.mark.parametrize("scope", ["volume", "all"])
def test_scope_opens_on_anchor_page(client, scope):
    _, pid, rows = seed(client)
    data = client.get(f"/api/v1/projects/{pid}/story-map", params={
        "scope": scope, "anchor_id": rows[52].id,
    }).json()
    assert data["offset"] == 50
    assert rows[52].id in [node["id"] for node in data["nodes"]]
    assert data["counts"] == {"total": 60, "written": 30, "confirmed": 20}
    first = client.get(f"/api/v1/projects/{pid}/story-map", params={
        "scope": scope, "anchor_id": rows[52].id, "offset": 0,
    }).json()
    assert first["offset"] == 0
    assert len(first["nodes"]) == 25
    assert first["next_offset"] == 25


def test_near_order_goal_provenance_and_empty_volume(client):
    db, pid, rows = seed(client, 10)
    rows[0].volume = None
    rows[0].sort_order = -100
    rows[1].sort_order = rows[2].sort_order = 1
    goal = ChapterGoal(chapter_id=rows[4].id, goal_json={"core_events": ["앞으로의 사건"]},
                       goal_version=1, base_manuscript_revision=0)
    db.add_all([goal, Scene(chapter_id=rows[4].id, title="합성 장면")])
    db.commit()
    data = client.get(f"/api/v1/projects/{pid}/story-map?anchor_id={rows[4].id}").json()
    assert [n["id"] for n in data["nodes"]] == [r.id for r in rows[2:10]]
    node = next(n for n in data["nodes"] if n["id"] == rows[4].id)
    assert node["goal"]["core_events"] == ["앞으로의 사건"]
    assert node["goal_base_revision"] == 0
    assert node["revision"] == 4
    assert node["scene_count"] == 1
    assert "content_md" not in node
    tail = client.get(f"/api/v1/projects/{pid}/story-map?scope=volume&anchor_id={rows[0].id}").json()
    assert [n["id"] for n in tail["nodes"]] == [rows[0].id]
    assert tail["nodes"][0]["position"] == 10


def test_empty_project_and_foreign_anchor(client):
    db, pid, rows = seed(client, 1)
    second = Project(title="다른 작품")
    db.add(second); db.commit()
    for scope in ["near", "volume", "all"]:
        response = client.get(f"/api/v1/projects/{second.id}/story-map?scope={scope}")
        assert response.status_code == 200
        assert response.json()["nodes"] == []
        assert response.json()["counts"]["total"] == 0
    assert client.get(f"/api/v1/projects/{second.id}/story-map?anchor_id={rows[0].id}").status_code == 404
    assert client.get("/api/v1/projects/999999/story-map").status_code == 404
    assert client.get(f"/api/v1/projects/{pid}/story-map?anchor_id=999999").status_code == 404


@pytest.mark.parametrize("params", [{"offset": -1}, {"offset": "abc"}, {"scope": "bogus"}, {"anchor_id": 0}])
def test_invalid_query(client, params):
    _, pid, _ = seed(client, 0)
    assert client.get(f"/api/v1/projects/{pid}/story-map", params=params).status_code == 422


def test_500_chapters_bounded_payload_queries_and_page_clamping(client):
    db, pid, rows = seed(client, 500)
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(db.bind, "before_cursor_execute", collect)
    try:
        response = client.get(f"/api/v1/projects/{pid}/story-map?scope=all&anchor_id={rows[300].id}")
    finally:
        event.remove(db.bind, "before_cursor_execute", collect)
    assert response.status_code == 200
    data = response.json()
    assert len(data["nodes"]) == 25
    assert data["counts"]["total"] == 500
    assert len(statements) <= 4
    assert not any("content_md" in s for s in statements)
    end = client.get(f"/api/v1/projects/{pid}/story-map?scope=all&offset=999999").json()
    assert end["offset"] == 475
    assert end["next_offset"] is None
