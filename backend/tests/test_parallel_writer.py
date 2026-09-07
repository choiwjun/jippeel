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
