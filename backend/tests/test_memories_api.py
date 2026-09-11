"""장편 기억 거버넌스 API 계약 테스트."""
import hashlib


def _create_project(client, title: str) -> int:
    response = client.post("/api/v1/projects", json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


def _create_chapter(client, pid: int, title: str = "현재 회차", sort_order: float = 1) -> dict:
    response = client.post(
        f"/api/v1/projects/{pid}/chapters",
        json={"title": title, "sort_order": sort_order},
    )
    assert response.status_code == 201
    return response.json()


def _create_memory(client, pid: int, **overrides) -> dict:
    payload = {
        "kind": "fact",
        "body": "주인공은 북부 관문을 지킨다.",
        **overrides,
    }
    response = client.post(f"/api/v1/projects/{pid}/memories", json=payload)
    assert response.status_code == 201
    return response.json()


def test_create_memory_derives_current_chapter_provenance_and_starts_as_draft(client):
    pid = _create_project(client, "기억 API")
    chapter = _create_chapter(client, pid)
    content = "현재 회차의 정본 본문"
    write_response = client.put(
        f"/api/v1/chapters/{chapter['id']}/content",
        json={"content_md": content, "expected_revision": chapter["revision"]},
    )
    assert write_response.status_code == 200
    current = write_response.json()

    response = client.post(
        f"/api/v1/projects/{pid}/memories",
        json={"chapter_id": chapter["id"], "kind": "summary", "body": "현재 회차 요약"},
    )

    assert response.status_code == 201
    memory = response.json()
    assert memory["visibility"] == "draft"
    assert memory["source_revision"] == current["revision"]
    assert memory["source_sha256"] == hashlib.sha256(content.encode()).hexdigest()
    assert memory["stale"] is False
    assert memory["source_chapter_title"] == "현재 회차"


def test_create_memory_rejects_chapter_from_another_project_without_writing(client):
    first_pid = _create_project(client, "첫 작품")
    second_pid = _create_project(client, "둘째 작품")
    foreign_chapter = _create_chapter(client, second_pid)

    response = client.post(
        f"/api/v1/projects/{first_pid}/memories",
        json={"chapter_id": foreign_chapter["id"], "kind": "fact", "body": "소속 오류"},
    )

    assert response.status_code == 422
    assert client.get(f"/api/v1/projects/{first_pid}/memories").json() == []

    foreign_memory = _create_memory(client, second_pid, body="다른 작품의 기억")
    cross_project_patch = client.patch(
        f"/api/v1/projects/{first_pid}/memories/{foreign_memory['id']}",
        json={"visibility": "retired"},
    )
    assert cross_project_patch.status_code == 422


def test_memory_state_transitions_are_explicit_and_retired_is_terminal(client):
    pid = _create_project(client, "상태 전환")
    memory = _create_memory(client, pid)

    approved = client.patch(
        f"/api/v1/projects/{pid}/memories/{memory['id']}",
        json={"visibility": "approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["visibility"] == "approved"

    retired = client.patch(
        f"/api/v1/projects/{pid}/memories/{memory['id']}",
        json={"visibility": "retired"},
    )
    assert retired.status_code == 200
    assert retired.json()["visibility"] == "retired"

    invalid = client.patch(
        f"/api/v1/projects/{pid}/memories/{memory['id']}",
        json={"visibility": "approved"},
    )
    assert invalid.status_code == 422


def test_list_is_project_scoped_filterable_and_reports_stale_memory(client):
    first_pid = _create_project(client, "첫 작품")
    second_pid = _create_project(client, "둘째 작품")
    chapter = _create_chapter(client, first_pid)
    memory = _create_memory(client, first_pid, chapter_id=chapter["id"], kind="summary")
    _create_memory(client, second_pid, kind="summary", body="다른 작품 기억")

    approved = client.patch(
        f"/api/v1/projects/{first_pid}/memories/{memory['id']}",
        json={"visibility": "approved"},
    )
    assert approved.status_code == 200
    changed = client.put(
        f"/api/v1/chapters/{chapter['id']}/content",
        json={"content_md": "원문 변경", "expected_revision": chapter["revision"]},
    )
    assert changed.status_code == 200

    all_memories = client.get(f"/api/v1/projects/{first_pid}/memories")
    assert all_memories.status_code == 200
    assert [row["id"] for row in all_memories.json()] == [memory["id"]]
    assert all_memories.json()[0]["stale"] is True

    stale_only = client.get(
        f"/api/v1/projects/{first_pid}/memories", params={"stale": "true", "visibility": "approved"}
    )
    assert [row["id"] for row in stale_only.json()] == [memory["id"]]

    other_project = client.get(f"/api/v1/projects/{second_pid}/memories")
    assert [row["body"] for row in other_project.json()] == ["다른 작품 기억"]


def test_chapter_delete_preserves_memory_by_rejecting_the_delete(client):
    pid = _create_project(client, "기억 보존")
    chapter = _create_chapter(client, pid)
    memory = _create_memory(client, pid, chapter_id=chapter["id"])

    response = client.delete(f"/api/v1/chapters/{chapter['id']}")

    assert response.status_code == 409
    assert client.get(f"/api/v1/chapters/{chapter['id']}").status_code == 200
    assert client.get(f"/api/v1/projects/{pid}/memories").json()[0]["id"] == memory["id"]


def test_memory_list_orders_by_source_before_applying_the_bound(client):
    pid = _create_project(client, "정렬")
    high_chapter = _create_chapter(client, pid, title="늦은 근거", sort_order=100)
    low_chapter = _create_chapter(client, pid, title="이른 근거", sort_order=1)
    for index in range(500):
        _create_memory(client, pid, chapter_id=high_chapter["id"], body=f"늦은 기억 {index}")
    low_memory = _create_memory(client, pid, chapter_id=low_chapter["id"], body="이른 기억")
    stale_chapter = _create_chapter(client, pid, title="늦은 stale 근거", sort_order=200)
    stale_memory = _create_memory(client, pid, chapter_id=stale_chapter["id"], body="늦은 stale 기억")
    changed = client.put(
        f"/api/v1/chapters/{stale_chapter['id']}/content",
        json={"content_md": "stale 원문", "expected_revision": stale_chapter["revision"]},
    )
    assert changed.status_code == 200

    response = client.get(f"/api/v1/projects/{pid}/memories", params={"limit": 1})
    stale_response = client.get(
        f"/api/v1/projects/{pid}/memories", params={"stale": "true", "limit": 1}
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == low_memory["id"]
    assert stale_response.status_code == 200
    assert stale_response.json()[0]["id"] == stale_memory["id"]


def test_memory_validation_rejects_invalid_range_and_unbounded_limit(client):
    pid = _create_project(client, "검증")

    invalid_range = client.post(
        f"/api/v1/projects/{pid}/memories",
        json={
            "kind": "fact",
            "body": "범위 오류",
            "effective_from_sort_order": 5,
            "effective_to_sort_order": 2,
        },
    )
    assert invalid_range.status_code == 422

    invalid_chapter = client.post(
        f"/api/v1/projects/{pid}/memories",
        json={"chapter_id": 0, "kind": "fact", "body": "회차 오류"},
    )
    assert invalid_chapter.status_code == 422

    invalid_limit = client.get(f"/api/v1/projects/{pid}/memories", params={"limit": 501})
    assert invalid_limit.status_code == 422


def test_memory_list_missing_project_is_not_a_global_query(client):
    assert client.get("/api/v1/projects/9999/memories").status_code == 404
    assert client.patch(
        "/api/v1/projects/9999/memories/9999", json={"visibility": "retired"}
    ).status_code == 404
