"""병렬 원고의 결정적 품질 가드 테스트."""

import pytest

from app.schemas import ParallelScenePlan
from app.services.parallel_writer import (
    SceneResult,
    build_review_source,
    validate_results,
    validate_scene_result,
)


def valid_scene(order: int) -> ParallelScenePlan:
    return ParallelScenePlan(
        order=order, title=f"장면 {order}", purpose="갈등을 진행한다",
        objective="즉시 목표를 이룬다", choice="핵심 선택을 한다", cost="대가를 감수한다",
        required_beats=["행동 비트"], characters=["주인공"],
        opening_state="직전 결과에서 시작한다", closing_hook="다음 질문을 남긴다",
    )


def test_scene_result_rejects_empty_oversized_and_meta_leak():
    plan = valid_scene(1)
    assert validate_scene_result(plan, " ")
    assert validate_scene_result(plan, "x" * 13, max_chars=12)
    assert validate_scene_result(plan, "[장면 계약] objective를 출력함")
    assert validate_scene_result(plan, "[감수] 문제가 없음")


def test_validate_results_rejects_duplicate_missing_and_plan_mismatch():
    plans = [valid_scene(1), valid_scene(2)]
    duplicate = [
        SceneResult(order=1, title="장면 1", text="A"),
        SceneResult(order=1, title="장면 2", text="B"),
    ]
    assert any("order" in issue for issue in validate_results(duplicate, plans))
    mismatch = [
        SceneResult(order=1, title="장면 1", text="A"),
        SceneResult(order=2, title="다른 제목", text="B"),
    ]
    assert any("title" in issue for issue in validate_results(mismatch, plans))


def test_review_source_labels_contracts_without_polluting_user_draft():
    plans = [valid_scene(1), valid_scene(2)]
    results = [
        SceneResult(order=2, title="장면 2", text="B"),
        SceneResult(order=1, title="장면 1", text="A"),
    ]
    source = build_review_source(results, plans)
    assert source.index("[장면 1 — 장면 1]") < source.index("[장면 2 — 장면 2]")
    assert "objective" in source
    assert "[장면 원고]\nA" in source
