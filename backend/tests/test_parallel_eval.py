"""고정 병렬 집필 평가 corpus와 offline runner 테스트."""

import json
from pathlib import Path

from scripts.evaluate_parallel import load_cases, offline_result, protocol_pass


CASE_FILE = Path(__file__).parents[1] / "evals" / "parallel_cases.json"


def test_parallel_corpus_has_twenty_unique_bounded_cases():
    cases = load_cases(CASE_FILE)
    assert len(cases) == 20
    assert len({case["id"] for case in cases}) == 20
    assert all(2 <= case["scene_count"] <= 4 for case in cases)


def test_offline_runner_reports_schema_only_without_claiming_prose_quality():
    cases = load_cases(CASE_FILE)
    result = offline_result(cases)
    assert result["cases"] == 20
    assert result["protocol_pass"] == 20
    assert result["draft_nonempty"] is None
    assert "does not claim prose quality" in result["note"]


def test_protocol_requires_review_and_done_events():
    events = [
        "parallel_start", "planner_done", "worker_start", "worker_start",
        "worker_done", "worker_done", "message", "review_start", "review", "done",
    ]
    assert protocol_pass(events, "draft", "review")
    assert not protocol_pass(events[:-1], "draft", "review")
