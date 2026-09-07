"""병렬 장면 집필의 검증·동시성·조립 계약."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from app.schemas import ParallelScenePlan


@dataclass(frozen=True)
class SceneResult:
    """한 worker의 완성 장면."""

    order: int
    title: str
    text: str


SceneWorker = Callable[[ParallelScenePlan], Awaitable[SceneResult]]


def assemble_scene_results(results: list[SceneResult]) -> str:
    """worker 완료 순서와 무관하게 장면 번호 순서로 조립한다."""
    if not results:
        raise ValueError("scene results are empty")
    orders = [result.order for result in results]
    expected = list(range(1, len(results) + 1))
    if sorted(orders) != expected:
        raise ValueError("scene results have duplicate or missing orders")
    if any(not result.text.strip() for result in results):
        raise ValueError("scene result is empty")
    ordered = sorted(results, key=lambda result: result.order)
    return "\n\n".join(result.text.strip() for result in ordered)


async def run_parallel_workers(
    plans: list[ParallelScenePlan],
    worker: SceneWorker,
    worker_limit: int,
) -> list[SceneResult]:
    """장면 worker를 제한된 동시성으로 실행하고 실패 시 전체를 취소한다."""
    if not plans:
        raise ValueError("scene plans are empty")
    if worker_limit < 1:
        raise ValueError("worker_limit must be positive")

    semaphore = asyncio.Semaphore(min(worker_limit, len(plans)))

    async def run_one(plan: ParallelScenePlan) -> SceneResult:
        async with semaphore:
            result = await worker(plan)
            if result.order != plan.order:
                raise ValueError(f"worker order mismatch: expected {plan.order}")
            return result

    tasks = [asyncio.create_task(run_one(plan)) for plan in plans]
    try:
        results = await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    return sorted(results, key=lambda result: result.order)
