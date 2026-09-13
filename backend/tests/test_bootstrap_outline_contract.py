"""bootstrap outline slot selection, original reproduction shapes and persistence."""
from copy import deepcopy
import json

import pytest
from sqlalchemy import select

from app.database import get_db
from app.models import Chapter, Project, VolumeNote
from app.services import bootstrap
from tests.test_bootstrap_api import fake_llm, GOOD_IDEA, GOOD_CHARACTERS, GOOD_RELLORE  # noqa: F401


def volume(number, orders):
    return {"volume": number, "title": f"V{number}", "chapters": [
        {"order": order, "title": f"V{number}C{i}", "synopsis": f"S{i}", "key_event": f"K{i}"}
        for i, order in enumerate(orders, 1)]}


REPRO_CASES = [
    ("O01-normal", [volume(1, [1, 2]), volume(2, [1, 2])], ["V1C1", "V1C2", "V2C1", "V2C2"]),
    ("O02-missing-earlier-volume", [volume(2, [1, 2])], [None, None, "V2C1", "V2C2"]),
    ("O03-uneven-volumes", [volume(1, [1]), volume(2, [1, 2])], ["V1C1", None, "V2C1", "V2C2"]),
    ("O04-duplicate-volume", [volume(1, [1, 2]), volume(1, [1, 2])], ["V1C1", "V1C2", None, None]),
    ("O05-out-of-range-volume", [volume(3, [1, 2]), volume(2, [1, 2])], [None, None, "V2C1", "V2C2"]),
    ("O06-duplicate-order", [volume(1, [1, 1]), volume(2, [1, 2])], ["V1C1", None, "V2C1", "V2C2"]),
    ("O07-out-of-range-order", [volume(1, [99, 2]), volume(2, [1, 2])], [None, "V1C2", "V2C1", "V2C2"]),
    ("O08-all-missing", [], [None, None, None, None]),
    ("O09-short-last-volume", [volume(1, [1, 2]), volume(2, [1])], ["V1C1", "V1C2", "V2C1", None]),
    ("O10-reversed-order", [volume(1, [2, 1]), volume(2, [1, 2])], ["V1C2", "V1C1", "V2C1", "V2C2"]),
    ("O11-reversed-volumes", [volume(2, [1, 2]), volume(1, [1, 2])], ["V1C1", "V1C2", "V2C1", "V2C2"]),
    ("O12-invalid-volume-after-short", [volume(1, [1]), volume(0, [1, 2])], ["V1C1", None, None, None]),
    ("O13-boolean-identifiers", [volume(True, [True, 2]), volume(2, [1, 2])], [None, None, "V2C1", "V2C2"]),
]


def assert_grid(chapters, volumes, cpv):
    assert [(c.volume, c.order, c.sort_order) for c in chapters] == [
        (v, o, float((v - 1) * cpv + o - 1))
        for v in range(1, volumes + 1) for o in range(1, cpv + 1)]
    assert all(type(c.volume) is int and type(c.order) is int for c in chapters)


@pytest.mark.parametrize("name,volumes,titles", REPRO_CASES, ids=[c[0] for c in REPRO_CASES])
def test_coerce_outline_original_reproductions(name, volumes, titles):
    data = {"volumes": volumes} if volumes else {}
    before = deepcopy(data)
    chapters = bootstrap._coerce_outline(data, 2, 2)
    assert_grid(chapters, 2, 2)
    originals = {c["title"]: c for v in volumes for c in v["chapters"]}
    for chapter, title in zip(chapters, titles, strict=True):
        if title is None:
            assert (chapter.title, chapter.synopsis, chapter.key_event) == (
                f"{chapter.volume}권 {chapter.order}화", "", "")
        else:
            original = originals[title]
            assert (chapter.title, chapter.synopsis, chapter.key_event) == (
                title, original["synopsis"], original["key_event"])
    assert data == before


@pytest.mark.parametrize("invalid", [0, -1, True, False, "1", 1.0, 3, 10**400, [], {}])
def test_coerce_outline_explicit_invalid_ids_never_fill_vacancies(invalid):
    data = {"volumes": [volume(invalid, [1]), volume(2, [invalid, 2])]}
    chapters = bootstrap._coerce_outline(data, 2, 2)
    assert_grid(chapters, 2, 2)
    assert [c.title for c in chapters] == ["1권 1화", "1권 2화", "2권 1화", "V2C2"]


def test_coerce_outline_reserves_explicit_ids_before_missing_and_null():
    data = {"volumes": [
        {"title": "missing-volume", "chapters": [
            {"title": "missing-order", "synopsis": "  원본 시놉시스  ", "key_event": "사건"},
            {"order": 2, "title": "explicit-order"},
            {"order": 2, "title": "duplicate-order"},
            {"order": None, "title": "null-order"},
            {"title": "excess-order"}]},
        {"volume": None, "title": "null-volume", "chapters": [{"title": "third-volume"}]},
        {"volume": 2, "title": "explicit-volume", "chapters": [{"order": 3, "title": "reserved"}]},
        {"volume": 2, "title": "duplicate-volume", "chapters": [{"order": 1, "title": "discard"}]},
        {"chapters": [{"title": "excess-volume"}]}, None, "invalid",
    ]}
    before = deepcopy(data)
    chapters = bootstrap._coerce_outline(data, 3, 3)
    assert_grid(chapters, 3, 3)
    assert [c.title for c in chapters] == [
        "missing-order", "explicit-order", "null-order", "2권 1화", "2권 2화", "reserved",
        "third-volume", "3권 2화", "3권 3화"]
    assert (chapters[0].synopsis, chapters[0].key_event) == ("원본 시놉시스", "사건")
    assert data == before


def test_coerce_outline_first_duplicate_wins_without_merging_empty_content():
    data = {"volumes": [{"volume": 1, "chapters": [
        {"order": 1}, {"order": 1, "title": "must not replace"}, None, 5]},
        {"volume": 1, "chapters": [{"order": 2, "title": "must not merge"}]}]}
    chapters = bootstrap._coerce_outline(data, 2, 2)
    assert_grid(chapters, 2, 2)
    assert [c.title for c in chapters] == ["1권 1화", "1권 2화", "2권 1화", "2권 2화"]


@pytest.mark.parametrize("value", [None, {}, "bad", 3])
def test_coerce_outline_invalid_containers_use_template(value):
    chapters = bootstrap._coerce_outline({"volumes": value}, 1, 2)
    assert_grid(chapters, 1, 2)
    chapters = bootstrap._coerce_outline({"volumes": [{"volume": 1, "chapters": value}]}, 1, 2)
    assert_grid(chapters, 1, 2)
    assert [c.title for c in chapters] == ["1권 1화", "1권 2화"]


def test_safe_sort_order_overflow_boundary_remains_value_error():
    with pytest.raises(ValueError, match="정렬"):
        bootstrap._safe_sort_order(10**400)


def test_bootstrap_duplicate_volume_metadata_matches_first_winner(client, fake_llm):
    first = {"volume": 1, "title": "FIRST", "overview": "FIRST overview",
             "chapters": [{"order": 1, "title": "FIRST chapter"}]}
    duplicate = {"volume": 1, "title": "LATER", "overview": "LATER overview",
                 "chapters": [{"order": 2, "title": "LATER chapter"}]}
    fake_llm["queue"] = [json.dumps(GOOD_IDEA), json.dumps({"volumes": [first, duplicate]}),
                         json.dumps(GOOD_CHARACTERS), json.dumps(GOOD_RELLORE)]
    response = client.post("/api/v1/projects/bootstrap", json={
        "genre": "판타지", "volume_count": 2, "chapters_per_volume": 2})
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(fake_llm["calls"]) == 4
    with next(iter(client.app.dependency_overrides[get_db]())) as db:
        notes = db.scalars(select(VolumeNote).where(VolumeNote.project_id == body["project_id"])).all()
        assert [(n.volume, n.title, n.overview) for n in notes] == [(1, "FIRST", "FIRST overview")]
        chapters = db.scalars(select(Chapter).where(
            Chapter.project_id == body["project_id"]).order_by(Chapter.sort_order)).all()
        assert [(c.volume, c.sort_order, c.title) for c in chapters] == [
            (1, 0.0, "FIRST chapter"), (1, 1.0, "1권 2화"),
            (2, 2.0, "2권 1화"), (2, 3.0, "2권 2화")]
        project = db.get(Project, body["project_id"])
        assert project is not None
        assert json.loads(project.memo)["bootstrap"]["outline_summary"] == body["outline_summary"]
    assert "1권. FIRST" in body["outline_summary"]
    assert "LATER" not in body["outline_summary"]
    for call in fake_llm["calls"][2:]:
        prompt = str(call["messages"])
        assert "FIRST" in prompt
        assert "LATER" not in prompt


def test_bootstrap_missing_null_invalid_metadata_and_slots_agree(client, fake_llm):
    data = {"volumes": [
        {"title": "MISSING", "overview": "missing overview", "emotion_curve": "curve",
         "climax_note": "climax", "chapters": [{"title": "missing chapter", "synopsis": "syn", "key_event": "event"}]},
        {"volume": None, "title": "NULL", "chapters": [{"order": None, "title": "null chapter"}]},
        {"volume": 2, "title": "EXPLICIT", "chapters": [{"order": 2, "title": "explicit chapter"}]},
        *({"volume": invalid, "title": "EXCLUDED", "chapters": [{"title": "EXCLUDED"}]}
          for invalid in (True, False, 0, -1, "1", 1.0, 5)),
    ]}
    before = deepcopy(data)
    fake_llm["queue"] = [json.dumps(GOOD_IDEA), json.dumps(data),
                         json.dumps(GOOD_CHARACTERS), json.dumps(GOOD_RELLORE)]
    response = client.post("/api/v1/projects/bootstrap", json={
        "genre": "판타지", "volume_count": 4, "chapters_per_volume": 2})
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(fake_llm["calls"]) == 4
    assert body["volume_note_count"] == 3
    with next(iter(client.app.dependency_overrides[get_db]())) as db:
        notes = db.scalars(select(VolumeNote).where(
            VolumeNote.project_id == body["project_id"]).order_by(VolumeNote.volume)).all()
        assert [(n.volume, n.title) for n in notes] == [(1, "MISSING"), (2, "EXPLICIT"), (3, "NULL")]
        assert (notes[0].overview, notes[0].emotion_curve, notes[0].climax_note) == (
            "missing overview", "curve", "climax")
        chapters = db.scalars(select(Chapter).where(
            Chapter.project_id == body["project_id"]).order_by(Chapter.sort_order)).all()
        assert [(c.volume, c.sort_order, c.title) for c in chapters] == [
            (1, 0.0, "missing chapter"), (1, 1.0, "1권 2화"),
            (2, 2.0, "2권 1화"), (2, 3.0, "explicit chapter"),
            (3, 4.0, "null chapter"), (3, 5.0, "3권 2화"),
            (4, 6.0, "4권 1화"), (4, 7.0, "4권 2화")]
        assert chapters[0].memo == "syn\n\n[핵심 사건] event"
        project = db.get(Project, body["project_id"])
        assert project is not None
        assert json.loads(project.memo)["bootstrap"]["outline_summary"] == body["outline_summary"]
    for text in [body["outline_summary"], *(str(c["messages"]) for c in fake_llm["calls"][2:])]:
        for title in ("1권. MISSING", "2권. EXPLICIT", "3권. NULL"):
            assert title in text
        assert "EXCLUDED" not in text
    assert data == before
