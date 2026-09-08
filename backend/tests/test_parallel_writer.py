"""병렬 장면 집필 오케스트레이터의 순서·동시성 계약 테스트."""
import asyncio

import pytest
from pydantic import ValidationError

from app.schemas import ParallelPlan, ParallelScenePlan
from app.services.parallel_writer import SceneResult, assemble_scene_results, run_parallel_workers


def valid_scene(order: int) -> ParallelScenePlan:
    return ParallelScenePlan(
        order=order,
        title=f"장면 {order}",
        purpose="갈등을 한 단계 진행한다",
        objective="폐역 안에서 열쇠의 위치를 확인한다",
        choice="열쇠를 직접 집어 든다",
        cost="추격자에게 위치가 노출될 위험을 감수한다",
        required_beats=["행동 비트"],
        characters=["주인공"],
        opening_state="직전 장면의 결과에서 시작한다",
        closing_hook="다음 장면의 질문을 남긴다",
    )


def test_parallel_plan_requires_two_to_four_contiguous_scenes():
    with pytest.raises(ValidationError):
        ParallelPlan(scenes=[valid_scene(1)])
    with pytest.raises(ValidationError):
        ParallelPlan(scenes=[valid_scene(1), valid_scene(3)])
    assert len(ParallelPlan(scenes=[valid_scene(1), valid_scene(2)]).scenes) == 2


def test_parallel_scene_requires_motivation_contract_fields():
    payload = valid_scene(1).model_dump()
    payload.pop("objective")
    with pytest.raises(ValidationError):
        ParallelScenePlan(**payload)


def test_assemble_scene_results_uses_scene_order_not_completion_order():
    result = assemble_scene_results([
        SceneResult(order=2, title="둘", text="B"),
        SceneResult(order=1, title="하나", text="A"),
    ])
    assert result == "A\n\nB"


def test_assemble_scene_results_rejects_duplicate_or_empty_results():
    with pytest.raises(ValueError, match="duplicate or missing"):
        assemble_scene_results([
            SceneResult(order=1, title="하나", text="A"),
            SceneResult(order=1, title="중복", text="B"),
        ])
    with pytest.raises(ValueError, match="empty"):
        assemble_scene_results([SceneResult(order=1, title="하나", text=" ")])


def test_parallel_workers_are_bounded_and_cancel_on_failure():
    async def exercise():
        active = 0
        max_active = 0
        cancelled: list[int] = []
        never = asyncio.Event()

        async def fake_worker(scene: ParallelScenePlan) -> SceneResult:
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            try:
                if scene.order == 2:
                    raise RuntimeError("worker failed")
                await never.wait()
                return SceneResult(order=scene.order, title=scene.title, text=scene.title)
            except asyncio.CancelledError:
                cancelled.append(scene.order)
                raise
            finally:
                active -= 1

        with pytest.raises(RuntimeError, match="worker failed"):
            await run_parallel_workers(
                [valid_scene(1), valid_scene(2), valid_scene(3)],
                fake_worker,
                worker_limit=2,
            )
        assert max_active <= 2
        assert cancelled

    asyncio.run(exercise())


def test_parallel_serial_requires_closing_hook():
    from app.services.parallel_writer import validate_plan_for_purpose

    p1 = valid_scene(1).model_copy(update={"closing_hook": None})
    p2 = valid_scene(2)
    plan = ParallelPlan(scenes=[p1, p2])
    with pytest.raises(ValueError, match="closing_hook"):
        validate_plan_for_purpose(plan, "serial")


def test_parallel_series_finale_allows_ending_intent_on_final_scene():
    from app.services.parallel_writer import validate_plan_for_purpose

    p1 = valid_scene(1).model_copy(update={"closing_hook": "마지막 선택으로 이어진다"})
    p2 = valid_scene(2).model_copy(update={"closing_hook": None, "ending_intent": "두 인물이 작별하며 시리즈 갈등을 닫는다"})
    plan = ParallelPlan(scenes=[p1, p2])
    validate_plan_for_purpose(plan, "series_finale")


def test_parallel_series_finale_rejects_legacy_hook_only_final_scene():
    from app.services.parallel_writer import validate_plan_for_purpose

    p1 = valid_scene(1).model_copy(update={"closing_hook": "마지막 선택으로 이어진다"})
    p2 = valid_scene(2).model_copy(update={"closing_hook": "다음 사건처럼 보이는 문장", "ending_intent": None})
    plan = ParallelPlan(scenes=[p1, p2])
    with pytest.raises(ValueError, match="final scene requires ending_intent"):
        validate_plan_for_purpose(plan, "series_finale")
