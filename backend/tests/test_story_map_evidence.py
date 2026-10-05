import pytest

from app.models import ChapterGoal, Character, EventImpact, Foreshadow, MemoryEntry, Project, Relationship
from app.services.long_memory import content_sha256
from tests.test_story_map import seed


def read(client, pid, cid, view, **params):
    result = client.get(f"/api/v1/projects/{pid}/story-map/evidence", params={
        "chapter_id": cid, "view": view, **params,
    })
    assert result.status_code == 200, result.text
    return result.json()


def test_relationship_provenance_time_and_retired_successor(client):
    db, pid, chapters = seed(client, 6)
    a, b = Character(project_id=pid, name="해온"), Character(project_id=pid, name="서리")
    db.add_all([a, b]); db.flush()
    db.add(Relationship(from_character_id=a.id, to_character_id=b.id, label="동료"))
    def make(index, visibility="approved", digest=None, label="변화"):
        c = chapters[index]
        row = EventImpact(project_id=pid, chapter_id=c.id, label=label, visibility=visibility,
                          source_sha256=digest if digest is not None else content_sha256(c.content_md),
                          relationship_deltas_json=[{"pair": ["해온", "서리"], "from": "대립", "to": "협력"}])
        db.add(row); db.flush(); return row
    valid = make(1, label="현재 근거")
    stale = make(1, digest="0" * 64, label="옛 원문")
    future = make(5, label="미래 사건")
    draft = make(1, visibility="draft", label="미승인")
    retired = make(1, label="이후 폐기")
    successor = make(1, visibility="retired")
    successor.provenance_json = {"supersedes_id": retired.id}
    no_hash = make(1, label="버전 없는 수동 기록"); no_hash.source_sha256 = None
    db.commit()
    data = read(client, pid, chapters[3].id, "relations")
    assert data["total"] == 2
    static, change = data["items"]
    assert "시점 정보 없음" in static["basis"]
    assert static["source"] is None
    assert change["label"] == "현재 근거"
    assert change["source"]["id"] == chapters[1].id
    assert change["source"]["revision"] == chapters[1].revision
    assert {x["label"] for x in data["items"]}.isdisjoint({stale.label, future.label, draft.label, retired.label, no_hash.label})


def test_approved_event_edited_with_character_ids_stays_visible(client):
    db, pid, chapters = seed(client, 2)
    a, b = Character(project_id=pid, name="해온"), Character(project_id=pid, name="서리")
    db.add_all([a, b]); db.flush()
    event = EventImpact(project_id=pid, chapter_id=chapters[1].id, label="ID로 수정하는 변화", visibility="approved",
                        source_sha256=content_sha256(chapters[1].content_md), relationship_deltas_json=[])
    db.add(event); db.commit()
    updated = client.patch(f"/api/v1/projects/{pid}/event-impacts/{event.id}", json={
        "relationship_deltas": [{"pair": [a.id, b.id], "from": "대립", "to": "협력"}],
    })
    assert updated.status_code == 200
    data = read(client, pid, chapters[1].id, "relations")
    assert data["total"] == 1
    assert data["items"][0]["from_name"] == "해온"
    assert data["items"][0]["to_name"] == "서리"


def test_relation_source_is_hashed_once_per_chapter(client, monkeypatch):
    from app.services import story_map_evidence
    db, pid, chapters = seed(client, 2)
    db.add_all([EventImpact(project_id=pid, chapter_id=chapters[1].id, label=f"사건 {i}", visibility="approved",
                           source_sha256=content_sha256(chapters[1].content_md),
                           relationship_deltas_json=[{"pair": ["가", "나"], "to": "동료"}]) for i in range(120)])
    db.commit()
    calls = []
    def digest(text):
        calls.append(text)
        return content_sha256(text)
    monkeypatch.setattr(story_map_evidence, "content_sha256", digest)
    data = read(client, pid, chapters[1].id, "relations")
    assert data["total"] == 120 and len(data["items"]) == 50
    assert len(calls) == 1


def test_relation_id_pairs_reject_bool_and_foreign_character(client):
    db, pid, chapters = seed(client, 2)
    other = Project(title="외부 작품"); db.add(other); db.flush()
    a = Character(project_id=pid, name="주인공")
    foreign = Character(project_id=other.id, name="외부 인물")
    db.add_all([a, foreign]); db.flush()
    for pair in [[a.id, foreign.id], [True, a.id], [a.id, -1]]:
        db.add(EventImpact(project_id=pid, chapter_id=chapters[1].id, label="잘못된 참조", visibility="approved",
                           source_sha256=content_sha256(chapters[1].content_md), relationship_deltas_json=[{"pair": pair}]))
    db.commit()
    assert read(client, pid, chapters[1].id, "relations")["items"] == []


def test_foreshadow_timeline_separates_actual_future_record(client):
    db, pid, chapters = seed(client, 6)
    chapters[0].volume = None  # no-volume chapters come last, independent of sort_order
    db.add(Foreshadow(project_id=pid, title="동전", status="회수",
                      planted_chapter_id=chapters[1].id, resolved_chapter_id=chapters[0].id))
    db.add(Foreshadow(project_id=pid, title="기록 없는 복선", status="설치"))
    db.commit()
    data = read(client, pid, chapters[3].id, "foreshadows")
    first = data["items"][0]
    assert first["planted"]["future"] is False
    assert first["resolved"]["future"] is True
    assert first["resolved"]["position"] == 6
    assert first["registered_status"] == "회수"
    assert data["items"][1]["planted"] is None
    assert "planned" not in first  # never invent a planned payoff from a real resolution


def test_reviews_follow_recursive_sources_and_goal_versions(client):
    db, pid, chapters = seed(client, 3)
    c = chapters[1]
    memory = MemoryEntry(project_id=pid, chapter_id=c.id, kind="summary", body="기존 요약",
                         visibility="approved", source_sha256=content_sha256(c.content_md), source_revision=c.revision)
    db.add(memory); db.flush()
    parent = MemoryEntry(project_id=pid, kind="arc_summary", body="기존 아크", visibility="approved",
                         source_sha256="manual", provenance_json={"arc_source_entry_ids": [memory.id]})
    db.add_all([parent, ChapterGoal(chapter_id=c.id, goal_version=1, goal_json={"core_events": ["계획"]},
                                   base_manuscript_revision=c.revision)])
    db.commit()
    assert read(client, pid, c.id, "review")["total"] == 0
    c.content_md = "바뀐 원문"; c.revision += 1; db.commit()
    data = read(client, pid, c.id, "review")
    assert data["total"] == 3
    assert {x["kind"] for x in data["items"]} == {"stale_memory", "goal_drift"}
    direct = next(x for x in data["items"] if x["id"] == f"memory-{memory.id}")
    assert direct["source_revision"] == 1
    assert direct["source"]["revision"] == 2
    parent_item = next(x for x in data["items"] if x["id"] == f"memory-{parent.id}")
    assert "연결 근거 불일치" in parent_item["basis"]
    assert parent_item["source"] is None
    assert memory.visibility == "approved" and memory.body == "기존 요약"


@pytest.mark.parametrize("view", ["relations", "foreshadows", "review"])
def test_evidence_requires_project_owned_chapter(client, view):
    db, pid, chapters = seed(client, 1)
    other = Project(title="다른 작품"); db.add(other); db.commit()
    response = client.get(f"/api/v1/projects/{other.id}/story-map/evidence", params={"chapter_id": chapters[0].id, "view": view})
    assert response.status_code == 404
    assert client.get(f"/api/v1/projects/{pid}/story-map/evidence", params={"chapter_id": 999999, "view": view}).status_code == 404


def test_foreign_records_excluded_and_page_limit(client):
    db, pid, chapters = seed(client, 1)
    other = Project(title="타 작품"); db.add(other); db.flush()
    db.add(Foreshadow(project_id=other.id, title="타 작품 비공개"))
    db.add_all([Foreshadow(project_id=pid, title=f"복선 {i}") for i in range(55)])
    db.commit()
    first = read(client, pid, chapters[0].id, "foreshadows")
    assert first["total"] == 55 and len(first["items"]) == 50 and first["next_offset"] == 50
    last = read(client, pid, chapters[0].id, "foreshadows", offset=999999)
    assert last["offset"] == 50 and len(last["items"]) == 5 and last["next_offset"] is None
    assert all(x["label"] != "타 작품 비공개" for x in first["items"] + last["items"])


@pytest.mark.parametrize("params", [{"view": "invalid"}, {"offset": -1}, {"chapter_id": 0}])
def test_invalid_evidence_query(client, params):
    _, pid, chapters = seed(client, 1)
    query = {"chapter_id": chapters[0].id, **params}
    assert client.get(f"/api/v1/projects/{pid}/story-map/evidence", params=query).status_code == 422
