"""B03 approved count contract; original RED evidence is preserved in recovery.

No literary-quality threshold is asserted. External metrics are synthetic only.
Run only through scripts/run_backend_pytest.py; conftest requires isolation.
"""
import json

import pytest

from app.services import quality


@pytest.fixture(autouse=True)
def no_external_metrics(monkeypatch):
    monkeypatch.setattr(quality, "_metrics_v2_loaded", True)
    monkeypatch.setattr(quality, "_metrics_v2_module", None)


def save_observation(tmp_path, name, payload):
    (tmp_path / f"b03-{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


@pytest.mark.parametrize("text,score,ratio,ending", [
    ("", 65, 0.0, 0.0),
    (" \t\n ", 65, 0.0, 0.0),
    ("!", 85, 0.0, 0.0),
    ('"!"!', 100, 0.25, 0.0),
    ("하게 된다", 50, 0.0, 200.0),
    ("~하게 된다", 50, 0.0, 166.67),
    ("일 뿐이다", 50, 0.0, 200.0),
    ("~일 뿐이다", 50, 0.0, 166.67),
    ("것이었다", 50, 0.0, 250.0),
    ("~것이었다", 50, 0.0, 200.0),
    ("기도 했다", 50, 0.0, 200.0),
    ("~기도 했다", 50, 0.0, 166.67),
    ("고요한 밤", 65, 0.0, 0.0),
])
def test_observed_short_text_and_endings(tmp_path, text, score, ratio, ending):
    result = quality.analyze_chapter(text)
    save_observation(tmp_path, "short", {"input": text, "result": result})
    assert result["score"] == score
    assert result["metrics"]["dialogue_ratio"] == ratio
    assert result["metrics"]["ending_repeat_per_1k"] == ending


@pytest.mark.parametrize("length", [199, 200, 201, 400])
@pytest.mark.parametrize("quotes", [('"', '"'), ("“", "”"), ("「", "」"), ("『", "』")])
def test_closed_quoted_spans_include_full_interior(tmp_path, length, quotes):
    text = quotes[0] + "가" * length + quotes[1]
    result = quality.analyze_chapter(text)
    save_observation(tmp_path, "quoted", {"input": text, "result": result})
    expected = round(length / (length + 2), 4)
    assert result["metrics"]["dialogue_ratio"] == expected
    assert result["score"] == 70


@pytest.mark.parametrize("text,ratio", [
    ("가" * 201, 0.0),
    ('"가', 0.0),
    ('“가"', 0.3333),  # current regex also accepts mismatched quote families
    ('"용어"는 표제다.', 0.2),  # quoted term, not dialogue: heuristic cannot distinguish
    ("'가'", 0.0),
    ('"가"\n"나"', 0.2857),
])
def test_observed_quote_selection(tmp_path, text, ratio):
    result = quality.analyze_chapter(text)
    save_observation(tmp_path, "selection", {"input": text, "result": result})
    assert result["metrics"]["dialogue_ratio"] == ratio


@pytest.mark.parametrize("text", ["", "고요한 밤", '"!"!'])
def test_observed_purpose_invariants(tmp_path, text):
    results = {purpose: quality.analyze_chapter(text, episode_purpose=purpose)
               for purpose in ("serial", "volume_end", "series_finale")}
    save_observation(tmp_path, "purposes", {"input": text, "results": results})
    serial = results["serial"]
    difference = 0 if serial["metrics"]["hook_present"] else 20
    for purpose in ("volume_end", "series_finale"):
        assert results[purpose]["score"] == serial["score"] + difference
        assert results[purpose]["metrics"]["hook_score_applicable"] is False
        assert "장 끝 후크" not in results[purpose]["suggested_preset_names"]


def test_observed_loader_essay_and_fallback(monkeypatch, tmp_path):
    import sys

    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(quality, "_METRICS_DIR", tmp_path)
    monkeypatch.setattr(quality, "_metrics_v2_loaded", False)
    assert quality.try_metrics_v2("가") is None
    (tmp_path / "metrics_v2.py").write_text(
        'def compute_all_v2(text, genre):\n'
        '    if text == "RAISE":\n'
        '        raise ValueError("synthetic")\n'
        '    return {"captured_text": text, "captured_genre": genre, "score": 7}\n',
        encoding="utf-8",
    )
    # A previous missing-file result is process-cached, not retried automatically.
    assert quality.try_metrics_v2("가") is None
    monkeypatch.setattr(quality, "_metrics_v2_loaded", False)
    result = quality.analyze_chapter('"!"!')
    save_observation(tmp_path, "loader", result)
    assert result["score"] == 100  # nested external score does not drive built-in score
    assert result["metrics"]["v2"] == {
        "captured_text": '"!"!', "captured_genre": "essay", "score": 7,
    }
    assert quality.try_metrics_v2("RAISE") is None


def test_observed_api_empty_history_and_record_false(client, tmp_path):
    project = client.post("/api/v1/projects", json={"title": "B03 synthetic"}).json()
    chapter = client.post(f"/api/v1/projects/{project['id']}/chapters",
                          json={"title": "empty"}).json()
    url = f"/api/v1/chapters/{chapter['id']}/quality"
    no_record = client.get(url + "?record=false").json()
    first = client.get(url).json()
    repeat = client.get(url).json()
    finale = client.get(url + "?episode_purpose=series_finale").json()
    history = client.get(url + "/history").json()
    save_observation(tmp_path, "api", {"no_record": no_record, "first": first,
                     "repeat": repeat, "finale": finale, "history": history})
    assert no_record["score"] == first["score"] == repeat["score"] == 65
    assert no_record["recorded"] is repeat["recorded"] is False
    assert first["recorded"] is finale["recorded"] is True
    assert finale["score"] == 85
    assert sorted(row["score"] for row in history) == [65, 85]


def test_intended_regression_weak_ending_without_notation_is_counted():
    """Regression: documented ending should be detected without a literal notation tilde."""
    assert quality.analyze_text("하게 된다")["ending_repeat_per_1k"] == 200.0


def test_intended_regression_complete_201_character_quote_is_counted():
    """Regression: full closed span must not disappear at the undocumented 200-char cap."""
    assert quality.analyze_text('"' + "가" * 201 + '"')["dialogue_ratio"] == 0.9901


def test_observed_normalization_and_denominators(tmp_path):
    text = ' \t"가 나!"\n\n그리고 끝. \n'
    result = quality.analyze_chapter(text)
    save_observation(tmp_path, "denominators", {"input": text, "result": result})
    metrics = result["metrics"]
    # strip leaves 14 code points; punctuation/newlines/spaces remain in denominator.
    assert metrics["dialogue_ratio"] == 0.2857  # 4 / 14
    assert metrics["chars_novelpia"] == 6  # only Unicode letters/numbers
    assert metrics["para_count"] == 2
    assert metrics["avg_para_chars"] == 7.0  # total 14 / 2, includes separators
    assert metrics["connector_per_1k"] == 71.43  # 1 / (14 / 1000)
    assert metrics["para_opener_variety"] == 1.0
    assert quality.try_metrics_v2(text) is None


@pytest.mark.parametrize("text,expected_count", [
    ("하게 된다 것이라면 일 뿐이다 기도 했다 것이었다 했다 이었다 였다", 7),
    ("~하게 된다 ~일 뿐이다 ~기도 했다 ~것이었다", 4),
    ("기도 했다기도 했다", 2),
    ("고요한 밤", 0),
])
def test_configured_endings_are_longest_first_nonoverlapping(text, expected_count):
    assert quality.analyze_text(text)["ending_repeat_per_1k"] == round(
        expected_count * 1000 / len(text), 2
    )


@pytest.mark.parametrize("text,dialogue_chars", [
    ('""', 0), ('""가"', 1), ('“”가', 0), ('“「가”', 2),
    ('“가"', 1), ('"가”', 1), ('"가" "나"', 2),
    ('"가""나"', 2), ('“”"가"', 1), ('"가\n나"', 3),
    ('“' + "가" * 401 + '」', 401),
])
def test_closed_span_compatibility_and_multiple_quotes(text, dialogue_chars):
    assert quality.analyze_text(text)["dialogue_ratio"] == round(
        dialogue_chars / len(text), 4
    )


def test_long_malformed_quotes_have_bounded_work():
    from time import perf_counter

    # Many potential openers with no closer must not repeatedly rescan the suffix.
    text = "“「『가" * 50_000
    started = perf_counter()
    assert quality.analyze_text(text)["dialogue_ratio"] == 0.0
    assert quality.analyze_text(text + "”")["dialogue_ratio"] == 1.0
    # Generous smoke bound, not a performance benchmark; 400k code points total.
    assert perf_counter() - started < 5.0



def test_short_quote_selection_matches_legacy_family_policy():
    import itertools
    import re

    legacy = re.compile(r'[“"『「]([^”"』」]{1,200}?)[”"』」]')
    # Exhaustive short malformed/mixed/empty cases establish family compatibility,
    # independently of the new single-pass implementation (all below old cap).
    for length in range(1, 5):
        for chars in itertools.product('“”"「」가', repeat=length):
            text = "".join(chars)
            expected = round(sum(map(len, legacy.findall(text))) / length, 4)
            assert quality.analyze_text(text)["dialogue_ratio"] == expected, text


def test_reanalysis_keeps_old_score_and_content_purpose_dedup(client):
    import hashlib

    from app.database import get_db
    from app.models import QualityCheck

    project = client.post("/api/v1/projects", json={"title": "B03 history"}).json()
    chapter = client.post(f"/api/v1/projects/{project['id']}/chapters",
                          json={"title": "same text"}).json()
    text = "하게 된다"
    assert client.put(f"/api/v1/chapters/{chapter['id']}/content", json={
        "content_md": text, "expected_revision": 0,
    }).status_code == 200
    db = next(iter(client.app.dependency_overrides[get_db]()))
    db.add(QualityCheck(
        chapter_id=chapter["id"], score=65,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        metrics_json={"episode_purpose": "serial"},
        suggestions_json=[], presets_json=[],
    ))
    db.commit()
    url = f"/api/v1/chapters/{chapter['id']}/quality"
    response = client.get(url)
    assert response.status_code == 200
    assert response.json()["score"] == 50
    assert response.json()["recorded"] is False
    assert [row["score"] for row in client.get(url + "/history").json()] == [65]
