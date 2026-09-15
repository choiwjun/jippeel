"""D02 인지 상태·사건 영향 API contract tests."""
import pytest
from fastapi.testclient import TestClient

from app.models import Chapter


def _project(client, title="cognitive") -> int:
    r = client.post("/api/v1/projects", json={"title": title})
    assert r.status_code == 201
    return r.json()["id"]


def _chapter(client, pid, sort_order=1, title="ch1", content="본문") -> int:
    r = client.post(
        f"/api/v1/projects/{pid}/chapters",
        json={"title": title, "sort_order": sort_order},
    )
    assert r.status_code == 201
    chapter_id = r.json()["id"]
    if content is not None:
        r = client.put(
            f"/api/v1/chapters/{chapter_id}/content",
            json={"content_md": content, "expected_revision": 0},
        )
        assert r.status_code == 200
    return chapter_id


def _character(client, pid, name="인물A") -> int:
    r = client.post(f"/api/v1/projects/{pid}/characters", json={"name": name})
    assert r.status_code == 201
    return r.json()["id"]


def _memory(client, pid, chapter_id=None, body="사실") -> int:
    r = client.post(
        f"/api/v1/projects/{pid}/memories",
        json={"kind": "fact", "body": body, "chapter_id": chapter_id},
    )
    assert r.status_code == 201
    return r.json()["id"]


def _foreshadow(client, pid, title="복선") -> int:
    r = client.post(f"/api/v1/projects/{pid}/foreshadows", json={"title": title})
    assert r.status_code == 201
    return r.json()["id"]


# ---- knowledge states ----

def test_create_knowledge_state_manual_is_approved(client):
    pid = _project(client)
    mid = _memory(client, pid)
    r = client.post(
        f"/api/v1/projects/{pid}/knowledge-states",
        json={
            "subject_type": "reader",
            "target_kind": "fact",
            "target_id": mid,
            "status": "unaware",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["visibility"] == "approved"
    assert body["subject_type"] == "reader"
    assert body["character_id"] is None


def test_create_knowledge_state_character_requires_character_id(client):
    pid = _project(client)
    mid = _memory(client, pid)
    r = client.post(
        f"/api/v1/projects/{pid}/knowledge-states",
        json={
            "subject_type": "character",
            "target_kind": "fact",
            "target_id": mid,
            "status": "aware",
        },
    )
    assert r.status_code == 422


def test_create_knowledge_state_rejects_character_id_for_non_character(client):
    pid = _project(client)
    cid = _character(client, pid)
    mid = _memory(client, pid)
    r = client.post(
        f"/api/v1/projects/{pid}/knowledge-states",
        json={
            "subject_type": "reader",
            "character_id": cid,
            "target_kind": "fact",
            "target_id": mid,
            "status": "aware",
        },
    )
    assert r.status_code == 422


def test_create_knowledge_state_rejects_foreign_target(client):
    pid = _project(client)
    other = _project(client, "other")
    foreign_memory = _memory(client, other)
    r = client.post(
        f"/api/v1/projects/{pid}/knowledge-states",
        json={
            "subject_type": "reader",
            "target_kind": "fact",
            "target_id": foreign_memory,
            "status": "unaware",
        },
    )
    assert r.status_code == 422


def test_create_knowledge_state_rejects_missing_target(client):
    pid = _project(client)
    r = client.post(
        f"/api/v1/projects/{pid}/knowledge-states",
        json={
            "subject_type": "reader",
            "target_kind": "fact",
            "target_id": 99999,
            "status": "unaware",
        },
    )
    assert r.status_code == 422


def test_create_knowledge_state_rejects_foreign_chapter(client):
    pid = _project(client)
    other = _project(client, "other")
    foreign_ch = _chapter(client, other)
    mid = _memory(client, pid)
    r = client.post(
        f"/api/v1/projects/{pid}/knowledge-states",
        json={
            "subject_type": "reader",
            "target_kind": "fact",
            "target_id": mid,
            "status": "aware",
            "revealed_chapter_id": foreign_ch,
        },
    )
    assert r.status_code == 422


def test_knowledge_state_update_and_visibility(client):
    pid = _project(client)
    mid = _memory(client, pid)
    r = client.post(
        f"/api/v1/projects/{pid}/knowledge-states",
        json={
            "subject_type": "reader",
            "target_kind": "fact",
            "target_id": mid,
            "status": "unaware",
        },
    )
    kid = r.json()["id"]
    r = client.patch(
        f"/api/v1/projects/{pid}/knowledge-states/{kid}",
        json={"status": "aware", "visibility": "approved"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "aware"
    assert r.json()["visibility"] == "approved"
    assert r.json()["id"] != kid
    rows = client.get(f"/api/v1/projects/{pid}/knowledge-states").json()
    assert [row["status"] for row in rows] == ["unaware", "aware"]


def test_knowledge_state_delete_appends_retired_transition(client):
    pid = _project(client)
    mid = _memory(client, pid)
    r = client.post(
        f"/api/v1/projects/{pid}/knowledge-states",
        json={
            "subject_type": "reader",
            "target_kind": "fact",
            "target_id": mid,
            "status": "unaware",
        },
    )
    kid = r.json()["id"]
    assert client.delete(f"/api/v1/projects/{pid}/knowledge-states/{kid}").status_code == 204
    rows = client.get(f"/api/v1/projects/{pid}/knowledge-states").json()
    assert len(rows) == 2
    assert rows[-1]["visibility"] == "retired"


def test_knowledge_visible_rejects_invalid_subject_character_combination(client):
    pid = _project(client)
    response = client.post(
        f"/api/v1/projects/{pid}/knowledge-visible",
        json={"subject_type": "character"},
    )
    assert response.status_code == 422
    response = client.post(
        f"/api/v1/projects/{pid}/knowledge-visible",
        json={"subject_type": "reader", "character_id": _character(client, pid)},
    )
    assert response.status_code == 422


def test_knowledge_visible_returns_latest_only(client):
    pid = _project(client)
    ch1 = _chapter(client, pid, 1, "c1")
    ch2 = _chapter(client, pid, 2, "c2")
    mid = _memory(client, pid)
    # 초기 unaware
    client.post(
        f"/api/v1/projects/{pid}/knowledge-states",
        json={
            "subject_type": "reader", "target_kind": "fact", "target_id": mid,
            "status": "unaware", "effective_from_sort_order": 0,
        },
    )
    # ch2에서 aware로 전이
    client.post(
        f"/api/v1/projects/{pid}/knowledge-states",
        json={
            "subject_type": "reader", "target_kind": "fact", "target_id": mid,
            "status": "aware", "effective_from_sort_order": 2,
            "revealed_chapter_id": ch2,
        },
    )
    # 시점 1 → unaware
    r = client.post(
        f"/api/v1/projects/{pid}/knowledge-visible",
        json={"subject_type": "reader", "at_sort_order": 1},
    )
    assert r.status_code == 200
    assert r.json()["entries"] == [{"target_kind": "fact", "target_id": mid, "status": "unaware"}]
    # 시점 3 → aware
    r = client.post(
        f"/api/v1/projects/{pid}/knowledge-visible",
        json={"subject_type": "reader", "at_sort_order": 3},
    )
    assert r.json()["entries"] == [{"target_kind": "fact", "target_id": mid, "status": "aware"}]


def test_context_rejects_foreign_pov_character(client):
    pid = _project(client)
    other = _project(client, "other")
    chapter_id = _chapter(client, pid)
    foreign_character_id = _character(client, other, "타 프로젝트 인물")

    from app.services.ai_context import build_context_bundle, request_from_generate
    from app.schemas import GenerateContext, GenerateRequest
    from tests.conftest import _db

    db = _db(client)
    try:
        payload = GenerateRequest(context=GenerateContext(
            project_id=pid,
            chapter_id=chapter_id,
            pov_character_id=foreign_character_id,
        ))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            build_context_bundle(db, request_from_generate(payload))
        assert exc_info.value.status_code == 422
        assert "pov character" in str(exc_info.value.detail).lower()
    finally:
        db.close()


def test_pov_filter_uses_latest_aware_transition(client):
    pid = _project(client)
    ch = _chapter(client, pid, 1)
    char_id = _character(client, pid)
    mid = _memory(client, pid, ch, "비밀 사실")
    for status, sort_order in (("unaware", 0), ("aware", 2)):
        response = client.post(f"/api/v1/projects/{pid}/knowledge-states", json={
            "subject_type": "character", "character_id": char_id,
            "target_kind": "fact", "target_id": mid, "status": status,
            "effective_from_sort_order": sort_order,
        })
        assert response.status_code == 201
    from app.services.ai_context import _pov_unaware_targets
    from tests.conftest import _db
    db = _db(client)
    try:
        assert ("fact", mid) not in _pov_unaware_targets(db, pid, char_id, 3)
    finally:
        db.close()


def test_pov_filter_hides_unrecorded_and_non_aware_targets(client):
    pid = _project(client)
    ch = _chapter(client, pid, 1)
    char_id = _character(client, pid)
    unrecorded = _memory(client, pid, ch, "기록되지 않은 비밀")
    false_belief = _memory(client, pid, ch, "잘못 알려진 비밀")
    forgotten = _memory(client, pid, ch, "잊은 비밀")
    aware = _memory(client, pid, ch, "아는 사실")
    for mid, status in (
        (false_belief, "false_belief"),
        (forgotten, "forgotten"),
        (aware, "aware"),
    ):
        response = client.post(f"/api/v1/projects/{pid}/knowledge-states", json={
            "subject_type": "character", "character_id": char_id,
            "target_kind": "fact", "target_id": mid, "status": status,
        })
        assert response.status_code == 201

    from app.services.ai_context import _filter_memory_by_pov
    from tests.conftest import _db
    db = _db(client)
    try:
        from app.models import MemoryEntry
        entries = list(db.query(MemoryEntry).filter(MemoryEntry.project_id == pid))
        visible = _filter_memory_by_pov(db, entries, pid, char_id, 2)
        assert {entry.id for entry in visible} == {aware}
        assert unrecorded not in {entry.id for entry in visible}
    finally:
        db.close()


def test_canon_pov_filters_unaware_lore_and_foreshadow(client):
    pid = _project(client)
    ch = _chapter(client, pid, 1)
    char_id = _character(client, pid, "시점 인물")
    lore_id = client.post(
        f"/api/v1/projects/{pid}/lore",
        json={"title": "숨은 설정", "content": "인물이 모르는 설정"},
    ).json()["id"]
    foreshadow_id = _foreshadow(client, pid, "숨은 복선")

    from app.services.ai_context import build_context_bundle, request_from_canon
    from app.schemas import CanonCheckRequest
    from tests.conftest import _db
    db = _db(client)
    try:
        request = CanonCheckRequest(
            chapter_id=ch,
            pov_character_id=char_id,
            approved_foreshadow_ids=[foreshadow_id],
        )
        bundle = build_context_bundle(db, request_from_canon(request, db.get(Chapter, ch)))
        assert lore_id not in bundle.metadata["included_lore_ids"]
        assert foreshadow_id not in bundle.metadata["included_foreshadow_ids"]
        assert "숨은 설정" not in "\\n".join(bundle.blocks)
        assert "숨은 복선" not in "\\n".join(bundle.blocks)
    finally:
        db.close()


def test_pov_filter_hides_explicitly_approved_foreshadow_without_awareness(client):
    pid = _project(client)
    ch = _chapter(client, pid, 1)
    char_id = _character(client, pid, "시점 인물")
    foreshadow = client.post(
        f"/api/v1/projects/{pid}/foreshadows",
        json={"title": "숨은 복선", "content": "아직 모르는 진실", "status": "설치"},
    ).json()["id"]

    from app.services.ai_context import build_context_bundle, request_from_generate
    from app.schemas import GenerateContext, GenerateRequest
    from tests.conftest import _db
    db = _db(client)
    try:
        request = GenerateRequest(context=GenerateContext(
            project_id=pid,
            chapter_id=ch,
            auto_foreshadow=True,
            approved_foreshadow_ids=[foreshadow],
            pov_character_id=char_id,
        ))
        bundle = build_context_bundle(db, request_from_generate(request))
        assert foreshadow not in bundle.metadata["included_foreshadow_ids"]
        assert "숨은 복선" not in "\\n".join(bundle.blocks)
    finally:
        db.close()


def test_knowledge_visible_excludes_draft(client):
    pid = _project(client)
    mid = _memory(client, pid)
    r = client.post(
        f"/api/v1/projects/{pid}/knowledge-states",
        json={
            "subject_type": "reader", "target_kind": "fact", "target_id": mid,
            "status": "unaware",
        },
    )
    kid = r.json()["id"]
    client.patch(
        f"/api/v1/projects/{pid}/knowledge-states/{kid}",
        json={"visibility": "draft"},
    )
    r = client.post(
        f"/api/v1/projects/{pid}/knowledge-visible",
        json={"subject_type": "reader"},
    )
    assert r.json()["entries"] == []


def test_knowledge_visible_character_scope(client):
    pid = _project(client)
    cid = _character(client, pid, "인물B")
    mid = _memory(client, pid)
    client.post(
        f"/api/v1/projects/{pid}/knowledge-states",
        json={
            "subject_type": "character", "character_id": cid,
            "target_kind": "fact", "target_id": mid, "status": "aware",
        },
    )
    r = client.post(
        f"/api/v1/projects/{pid}/knowledge-visible",
        json={"subject_type": "character", "character_id": cid},
    )
    assert r.json()["entries"] == [{"target_kind": "fact", "target_id": mid, "status": "aware"}]
    # 다른 캐릭터는 비어 있어야 함
    cid2 = _character(client, pid, "인물C")
    r = client.post(
        f"/api/v1/projects/{pid}/knowledge-visible",
        json={"subject_type": "character", "character_id": cid2},
    )
    assert r.json()["entries"] == []


# ---- event impacts ----

def test_create_event_impact_manual_is_approved(client):
    pid = _project(client)
    ch = _chapter(client, pid)
    character = client.post(
        f"/api/v1/projects/{pid}/characters", json={"name": "A"}
    ).json()["id"]
    other_character = client.post(
        f"/api/v1/projects/{pid}/characters", json={"name": "B"}
    ).json()["id"]
    foreshadow = _foreshadow(client, pid, "복선")
    r = client.post(
        f"/api/v1/projects/{pid}/event-impacts",
        json={
            "chapter_id": ch,
            "label": "결투",
            "character_deltas": [{"character_id": character, "delta": "부상"}],
            "relationship_deltas": [{"pair": [character, other_character], "from": "우호", "to": "적대"}],
            "foreshadow_deltas": [{"foreshadow_id": foreshadow, "진전": "진행"}],
            "state_after": "A 부상, B와 적대",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["visibility"] == "approved"
    assert body["label"] == "결투"
    assert body["character_deltas"][0]["delta"] == "부상"


def test_event_impact_update_is_append_only(client):
    pid = _project(client)
    ch = _chapter(client, pid)
    r = client.post(
        f"/api/v1/projects/{pid}/event-impacts",
        json={"chapter_id": ch, "label": "사건", "state_after": "처음 상태"},
    )
    iid = r.json()["id"]
    r = client.patch(
        f"/api/v1/projects/{pid}/event-impacts/{iid}",
        json={"label": "수정", "visibility": "approved", "state_after": "바뀐 상태"},
    )
    assert r.status_code == 200
    successor = r.json()
    assert successor["id"] != iid
    assert successor["label"] == "수정"
    assert successor["visibility"] == "approved"
    assert successor["provenance"]["supersedes_id"] == iid

    rows = client.get(f"/api/v1/projects/{pid}/event-impacts").json()
    assert [row["id"] for row in rows] == [iid, successor["id"]]
    assert rows[0]["label"] == "사건"
    assert rows[0]["state_after"] == "처음 상태"


def test_event_impact_delete_appends_retired_transition(client):
    pid = _project(client)
    ch = _chapter(client, pid)
    iid = client.post(
        f"/api/v1/projects/{pid}/event-impacts",
        json={"chapter_id": ch, "label": "사건"},
    ).json()["id"]

    assert client.delete(f"/api/v1/projects/{pid}/event-impacts/{iid}").status_code == 204
    rows = client.get(f"/api/v1/projects/{pid}/event-impacts").json()
    assert len(rows) == 2
    assert rows[0]["id"] == iid
    assert rows[0]["visibility"] == "approved"
    assert rows[1]["visibility"] == "retired"
    assert rows[1]["provenance"]["supersedes_id"] == iid


def test_event_impact_rejects_foreign_chapter(client):
    pid = _project(client)
    other = _project(client, "other")
    foreign_ch = _chapter(client, other)
    r = client.post(
        f"/api/v1/projects/{pid}/event-impacts",
        json={"chapter_id": foreign_ch, "label": "x"},
    )
    assert r.status_code == 422


def test_character_lifecycle_rejects_foreign_chapter(client):
    pid = _project(client)
    other = _project(client, "other")
    foreign_ch = _chapter(client, other)
    r = client.post(f"/api/v1/projects/{pid}/characters", json={
        "name": "외부 인물",
        "lifecycle_chapter_id": foreign_ch,
    })
    assert r.status_code == 422

    cid = _character(client, pid, "내부 인물")
    r = client.patch(f"/api/v1/characters/{cid}", json={
        "lifecycle_chapter_id": foreign_ch,
    })
    assert r.status_code == 422


def test_event_impact_rejects_foreign_nested_relationship_references(client):
    pid = _project(client)
    other = _project(client, "other")
    chapter = _chapter(client, pid)
    local_character = client.post(
        f"/api/v1/projects/{pid}/characters", json={"name": "내부 인물"}
    ).json()["id"]
    foreign_character = client.post(
        f"/api/v1/projects/{other}/characters", json={"name": "외부 인물"}
    ).json()["id"]
    r = client.post(
        f"/api/v1/projects/{pid}/event-impacts",
        json={
            "chapter_id": chapter,
            "label": "잘못된 관계",
            "relationship_deltas": [{"pair": [local_character, foreign_character]}],
        },
    )
    assert r.status_code == 422


def test_event_impact_rejects_foreign_nested_references(client):
    pid = _project(client)
    other = _project(client, "other")
    chapter = _chapter(client, pid)
    foreign_character = client.post(
        f"/api/v1/projects/{other}/characters", json={"name": "외부 인물"}
    ).json()["id"]
    foreign_foreshadow = _foreshadow(client, other, "외부 복선")
    r = client.post(
        f"/api/v1/projects/{pid}/event-impacts",
        json={
            "chapter_id": chapter,
            "label": "잘못된 사건",
            "character_deltas": [{"character_id": foreign_character, "delta": "부상"}],
            "foreshadow_deltas": [{"foreshadow_id": foreign_foreshadow, "진전": "진행"}],
        },
    )
    assert r.status_code == 422


def test_event_impact_rejects_changing_historical_transition(client):
    pid = _project(client)
    ch = _chapter(client, pid)
    original = client.post(f"/api/v1/projects/{pid}/event-impacts", json={"chapter_id": ch, "label": "원본"}).json()
    successor = client.patch(
        f"/api/v1/projects/{pid}/event-impacts/{original['id']}", json={"label": "후속"}
    ).json()
    r = client.patch(
        f"/api/v1/projects/{pid}/event-impacts/{original['id']}", json={"label": "부활"}
    )
    assert r.status_code == 409
    assert successor["label"] == "후속"


def test_event_impact_rejects_retired_transition(client):
    pid = _project(client)
    ch = _chapter(client, pid)
    original = client.post(f"/api/v1/projects/{pid}/event-impacts", json={"chapter_id": ch, "label": "원본"}).json()
    client.delete(f"/api/v1/projects/{pid}/event-impacts/{original['id']}")
    r = client.patch(
        f"/api/v1/projects/{pid}/event-impacts/{original['id']}", json={"label": "부활"}
    )
    assert r.status_code == 409


def test_event_impact_rejects_historical_transition(client):
    pid = _project(client)
    ch = _chapter(client, pid)
    original = client.post(f"/api/v1/projects/{pid}/event-impacts", json={"chapter_id": ch, "label": "원본"}).json()
    successor = client.patch(
        f"/api/v1/projects/{pid}/event-impacts/{original['id']}", json={"label": "후속"}
    ).json()
    r = client.patch(
        f"/api/v1/projects/{pid}/event-impacts/{original['id']}", json={"label": "부활"}
    )
    assert r.status_code == 409
    assert successor["label"] == "후속"


def test_event_impact_list_filter_by_chapter(client):
    pid = _project(client)
    ch1 = _chapter(client, pid, 1, "c1")
    ch2 = _chapter(client, pid, 2, "c2")
    client.post(f"/api/v1/projects/{pid}/event-impacts",
                json={"chapter_id": ch1, "label": "e1"})
    client.post(f"/api/v1/projects/{pid}/event-impacts",
                json={"chapter_id": ch2, "label": "e2"})
    r = client.get(f"/api/v1/projects/{pid}/event-impacts?chapter_id={ch1}")
    assert len(r.json()) == 1
    assert r.json()[0]["label"] == "e1"


# ---- 파생 endpoint 계약 ----


def test_derive_cognitive_uses_provider_without_real_network(client, monkeypatch):
    pid = _project(client)
    ch = _chapter(client, pid, content="김철수가 비밀을 알게 되었다.")
    mid = _memory(client, pid, ch, "secret")
    calls = []

    def fake_provider(system: str, user: str) -> str:
        calls.append((system, user))
        return (
            '{"events": [{"label": "discovery", "state_after": "secret learned"}],'
            ' "knowledge": [{"subject_type": "reader", "target_kind": "fact",'
            '  "target_hint": "secret", "status": "aware"}]}'
        )

    monkeypatch.setattr(
        "app.routers.cognitive.make_gpt_cognitive_provider",
        lambda: fake_provider,
    )
    r = client.post(f"/api/v1/projects/{pid}/derive-cognitive", json={"chapter_ids": [ch]})
    assert r.status_code == 200
    assert r.json() == [{
        "chapter_id": ch,
        "events_created": 1,
        "knowledge_created": 1,
        "skipped": False,
    }]
    assert calls

    rows = client.get(f"/api/v1/projects/{pid}/knowledge-states").json()
    assert any(row["target_id"] == mid and row["visibility"] == "draft" for row in rows)

    events = client.get(f"/api/v1/projects/{pid}/event-impacts").json()
    assert any(event["label"] == "discovery" and event["visibility"] == "draft" for event in events)


def test_derive_cognitive_rederives_when_chapter_source_changes(client, monkeypatch):
    pid = _project(client)
    ch = _chapter(client, pid, content="첫 번째 본문")
    calls = []

    def fake_provider(system: str, user: str) -> str:
        calls.append(user)
        return '{"events": [{"label": "발견"}], "knowledge": []}'

    monkeypatch.setattr(
        "app.routers.cognitive.make_gpt_cognitive_provider",
        lambda: fake_provider,
    )
    first = client.post(f"/api/v1/projects/{pid}/derive-cognitive", json={"chapter_ids": [ch]})
    assert first.status_code == 200
    assert first.json()[0]["events_created"] == 1

    update = client.put(
        f"/api/v1/chapters/{ch}/content",
        json={"content_md": "두 번째 본문", "expected_revision": 1},
    )
    assert update.status_code == 200
    second = client.post(f"/api/v1/projects/{pid}/derive-cognitive", json={"chapter_ids": [ch]})
    assert second.status_code == 200
    assert second.json()[0] == {
        "chapter_id": ch,
        "events_created": 1,
        "knowledge_created": 0,
        "skipped": False,
    }
    assert len(calls) == 2
    events = client.get(f"/api/v1/projects/{pid}/event-impacts").json()
    assert len(events) == 2
    assert len({event["source_sha256"] for event in events}) == 2


def test_derive_cognitive_rejects_malformed_provider_output(client, monkeypatch):
    pid = _project(client)
    ch = _chapter(client, pid)

    monkeypatch.setattr(
        "app.routers.cognitive.make_gpt_cognitive_provider",
        lambda: (lambda system, user: "not-json"),
    )
    r = client.post(f"/api/v1/projects/{pid}/derive-cognitive", json={"chapter_ids": [ch]})
    assert r.status_code == 502
    assert r.json()["detail"] == "cognitive derivation provider failed"
    assert client.get(f"/api/v1/projects/{pid}/event-impacts").json() == []
    assert client.get(f"/api/v1/projects/{pid}/knowledge-states").json() == []


def test_derive_cognitive_rejects_wrong_provider_shape(client, monkeypatch):
    pid = _project(client)
    ch = _chapter(client, pid)

    monkeypatch.setattr(
        "app.routers.cognitive.make_gpt_cognitive_provider",
        lambda: (lambda system, user: '{"events": {}, "knowledge": []}'),
    )
    r = client.post(f"/api/v1/projects/{pid}/derive-cognitive", json={"chapter_ids": [ch]})
    assert r.status_code == 502


def test_derive_cognitive_reports_provider_failure(client, monkeypatch):
    pid = _project(client)
    ch = _chapter(client, pid)

    def failing_provider(system: str, user: str) -> str:
        raise ConnectionError("bridge offline")

    monkeypatch.setattr(
        "app.routers.cognitive.make_gpt_cognitive_provider",
        lambda: failing_provider,
    )
    r = client.post(f"/api/v1/projects/{pid}/derive-cognitive", json={"chapter_ids": [ch]})
    assert r.status_code == 502
    assert r.json()["detail"] == "cognitive derivation provider failed"


def test_derive_cognitive_returns_empty_for_no_content(client):
    pid = _project(client)
    ch = _chapter(client, pid, content=None)
    r = client.post(f"/api/v1/projects/{pid}/derive-cognitive", json={"chapter_ids": [ch]})
    assert r.status_code == 200
    assert r.json() == []


def test_gpt_cognitive_provider_closes_sync_client(monkeypatch):
    from types import SimpleNamespace
    from app.services.cognitive_worker import make_gpt_cognitive_provider

    closed = []
    class FakeClient:
        def close(self):
            closed.append("sync")

    async def complete_chat(*args, **kwargs):
        return "{}"

    monkeypatch.setattr(
        "app.services.gpt_oauth.get_provider",
        lambda: SimpleNamespace(
            base_url="http://127.0.0.1:10531/v1",
            default_model="fake-model",
            reasoning_effort="low",
        ),
    )
    monkeypatch.setattr("app.services.llm.complete_chat", complete_chat)

    provider = make_gpt_cognitive_provider(client_factory=FakeClient)
    assert provider("system", "user") == "{}"
    assert closed == ["sync"]


def test_gpt_cognitive_provider_awaits_async_close(monkeypatch):
    from types import SimpleNamespace
    from app.services.cognitive_worker import make_gpt_cognitive_provider

    closed = []
    class FakeClient:
        async def close(self):
            closed.append("async")

    async def complete_chat(*args, **kwargs):
        return "{}"

    monkeypatch.setattr(
        "app.services.gpt_oauth.get_provider",
        lambda: SimpleNamespace(
            base_url="http://127.0.0.1:10531/v1",
            default_model="fake-model",
            reasoning_effort="low",
        ),
    )
    monkeypatch.setattr("app.services.llm.complete_chat", complete_chat)

    provider = make_gpt_cognitive_provider(client_factory=FakeClient)
    assert provider("system", "user") == "{}"
    assert closed == ["async"]


# ---- 캐릭터 라이프사이클 + canon 사전검사 (감사 잔여) ----


def test_character_lifecycle_fields(client: TestClient):
    """캐릭터 라이프사이클 first-class 필드 CRUD."""
    pid = _project(client)
    ch_resp = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화"})
    ch_id = ch_resp.json()["id"]

    # 생성 시 라이프사이클 지정
    r = client.post(f"/api/v1/projects/{pid}/characters", json={
        "name": "테스트 인물",
        "lifecycle_status": "active",
        "volume_roles": [{"volume": 1, "role": "주연"}],
    })
    assert r.status_code == 201
    char_id = r.json()["id"]
    assert r.json()["lifecycle_status"] == "active"
    assert r.json()["volume_roles"] == [{"volume": 1, "role": "주연"}]

    # 퇴장으로 변경
    r2 = client.patch(f"/api/v1/characters/{char_id}", json={
        "lifecycle_status": "departed",
        "lifecycle_chapter_id": ch_id,
        "lifecycle_note": "2권에서 해외로 떠남",
    })
    assert r2.status_code == 200
    assert r2.json()["lifecycle_status"] == "departed"
    assert r2.json()["lifecycle_chapter_title"] == "1화"
    assert r2.json()["lifecycle_note"] == "2권에서 해외로 떠남"

    # 사망으로 변경
    r3 = client.patch(f"/api/v1/characters/{char_id}", json={
        "lifecycle_status": "deceased",
    })
    assert r3.status_code == 200
    assert r3.json()["lifecycle_status"] == "deceased"


def test_canon_deterministic_precheck_does_not_flag_lifecycle_chapter(client: TestClient):
    pid = _project(client)
    ch_resp = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화", "sort_order": 1})
    ch_id = ch_resp.json()["id"]
    client.put(f"/api/v1/chapters/{ch_id}/content", json={
        "content_md": "김철수가 마지막으로 손을 흔들었다.",
        "expected_revision": 0,
    })
    client.post(f"/api/v1/projects/{pid}/characters", json={
        "name": "김철수",
        "lifecycle_status": "departed",
        "lifecycle_chapter_id": ch_id,
    })

    from app.services.canon import deterministic_precheck
    from tests.conftest import _db
    db = _db(client)
    try:
        chapter = db.get(Chapter, ch_id)
        assert not deterministic_precheck(db, chapter)
    finally:
        db.close()


def test_canon_deterministic_precheck_departed_character(client: TestClient):
    """퇴장 인물이 lifecycle 회차 이후 본문에 등장하면 error를 반환한다."""
    pid = _project(client)
    ch_resp = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화", "sort_order": 1})
    ch_id = ch_resp.json()["id"]
    later_resp = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "2화", "sort_order": 2})
    later_id = later_resp.json()["id"]
    client.put(f"/api/v1/chapters/{later_id}/content", json={"content_md": "김철수가 검을 뽑았다.", "expected_revision": 0})

    char_resp = client.post(f"/api/v1/projects/{pid}/characters", json={
        "name": "김철수",
        "lifecycle_status": "departed",
        "lifecycle_chapter_id": ch_id,
    })
    assert char_resp.status_code == 201

    # canon-check 호출 (provider 없으므로 503 예상, 하지만 precheck는 run_canon_check 내부에서 실행)
    # 대신 직접 precheck를 테스트
    from app.services.canon import deterministic_precheck
    from tests.conftest import _db
    db = _db(client)
    try:
        chapter = db.get(Chapter, later_id)
        issues = deterministic_precheck(db, chapter)
        assert len(issues) >= 1
        assert any("퇴장" in i["reason"] for i in issues)
        assert any(i["severity"] == "error" for i in issues)
    finally:
        db.close()


def test_canon_deterministic_precheck_unresolved_foreshadow(client: TestClient):
    """미회수 복선이 본문에서 해결 방향으로 언급되면 warn."""
    pid = _project(client)
    ch_resp = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화"})
    ch_id = ch_resp.json()["id"]
    client.put(f"/api/v1/chapters/{ch_id}/content", json={
        "content_md": "그는 마법검의 진실을 알게 되었다.", "expected_revision": 0,
    })
    client.post(f"/api/v1/projects/{pid}/foreshadows", json={
        "title": "마법검",
        "content": "주인공의 검에 숨겨진 비밀",
        "status": "설치",
    })

    from app.services.canon import deterministic_precheck
    from tests.conftest import _db
    db = _db(client)
    chapter = db.get(Chapter, ch_id)
    issues = deterministic_precheck(db, chapter)
    assert any("미회수 복선" in i["reason"] for i in issues)


def test_canon_deterministic_precheck_approved_foreshadow_skipped(client: TestClient):
    """작가가 공개 허용한 복선은 사전검사에서 제외."""
    pid = _project(client)
    ch_resp = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화"})
    ch_id = ch_resp.json()["id"]
    client.put(f"/api/v1/chapters/{ch_id}/content", json={
        "content_md": "그는 마법검의 진실을 알게 되었다.", "expected_revision": 0,
    })
    fs_resp = client.post(f"/api/v1/projects/{pid}/foreshadows", json={
        "title": "마법검",
        "content": "주인공의 검에 숨겨진 비밀",
        "status": "설치",
    })
    fs_id = fs_resp.json()["id"]

    from app.services.canon import deterministic_precheck
    from tests.conftest import _db
    db = _db(client)
    chapter = db.get(Chapter, ch_id)
    issues = deterministic_precheck(db, chapter, approved_foreshadow_ids=[fs_id])
    assert not any("미회수 복선" in i["reason"] for i in issues)


def test_pov_filter_excludes_explicit_unaware_lore(client):
    pid = _project(client)
    ch_id = _chapter(client, pid)
    char_id = client.post(f"/api/v1/projects/{pid}/characters", json={"name": "시점"}).json()["id"]
    lore_id = client.post(f"/api/v1/projects/{pid}/lore", json={
        "title": "비밀 설정", "content": "POV가 모르는 설정"
    }).json()["id"]
    client.post(f"/api/v1/projects/{pid}/knowledge-states", json={
        "subject_type": "character", "character_id": char_id,
        "target_kind": "lore", "target_id": lore_id, "status": "unaware",
    })
    from app.services.ai_context import build_context_bundle, request_from_generate
    from app.schemas import GenerateContext, GenerateRequest
    from tests.conftest import _db
    db = _db(client)
    try:
        bundle = build_context_bundle(db, request_from_generate(GenerateRequest(
            context=GenerateContext(chapter_id=ch_id, lore_ids=[lore_id], pov_character_id=char_id),
        )))
        assert "POV가 모르는 설정" not in "\n".join(bundle.blocks)
    finally:
        db.close()


def test_pov_filter_excludes_unaware_fact(client: TestClient):
    """POV 인물이 모르는 fact는 컨텍스트에서 제외된다."""
    pid = _project(client)
    ch_resp = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화"})
    ch_id = ch_resp.json()["id"]

    # 인물 생성
    char_resp = client.post(f"/api/v1/projects/{pid}/characters", json={"name": "주인공"})
    char_id = char_resp.json()["id"]

    # fact 기억 생성
    mem_resp = client.post(f"/api/v1/projects/{pid}/memories", json={
        "chapter_id": ch_id,
        "kind": "fact",
        "body": "왕은 사실 배신자였다",
    })
    mem_id = mem_resp.json()["id"]
    client.patch(f"/api/v1/projects/{pid}/memories/{mem_id}", json={"visibility": "approved"})

    # 주인공이 이 사실을 모른다고 기록
    client.post(f"/api/v1/projects/{pid}/knowledge-states", json={
        "subject_type": "character",
        "character_id": char_id,
        "target_kind": "fact",
        "target_id": mem_id,
        "status": "unaware",
        "effective_from_sort_order": 0,
    })

    # POV 없이 컨텍스트 빌드 → fact 포함
    from app.services.ai_context import build_context_bundle, request_from_generate
    from app.schemas import GenerateRequest, GenerateContext
    from tests.conftest import _db
    db = _db(client)
    try:
        payload = GenerateRequest(
            context=GenerateContext(chapter_id=ch_id, include_memory=True),
        )
        bundle = build_context_bundle(db, request_from_generate(payload))
        text = "\n".join(bundle.blocks)
        assert "배신자" in text

        # POV 지정 → fact 제외
        payload2 = GenerateRequest(
            context=GenerateContext(
                chapter_id=ch_id,
                include_memory=True,
                pov_character_id=char_id,
            ),
        )
        bundle2 = build_context_bundle(db, request_from_generate(payload2))
        text2 = "\n".join(bundle2.blocks)
        assert "배신자" not in text2
    finally:
        db.close()
