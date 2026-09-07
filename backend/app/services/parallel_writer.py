"""병렬 장면 집필의 검증·동시성·조립 계약."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Awaitable, Callable

from app.schemas import ParallelPlan, ParallelScenePlan


@dataclass(frozen=True)
class SceneResult:
    """한 worker의 완성 장면."""

    order: int
    title: str
    text: str


SceneWorker = Callable[[ParallelScenePlan], Awaitable[SceneResult]]




def parse_parallel_plan(raw: str) -> ParallelPlan:
    """planner의 JSON 응답을 코드펜스 허용 방식으로 검증한다."""
    text = (raw or "").strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl >= 0:
            text = text[first_nl + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("parallel planner JSON object not found")
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("parallel planner JSON is invalid") from exc
    return ParallelPlan.model_validate(data)
CONTRACT_LEAK_MARKERS = (
    "[장면 계약]", "[장면 원고]", "[감수]", "[수정본]", "원고 본문만 출력",
)
DEFAULT_SCENE_MAX_CHARS = 12_000


def validate_scene_result(
    plan: ParallelScenePlan,
    text: str,
    max_chars: int = DEFAULT_SCENE_MAX_CHARS,
) -> list[str]:
    """LLM을 호출하지 않고 한 worker 결과의 안전한 출력 계약을 검사한다."""
    issues: list[str] = []
    normalized = (text or "").strip()
    if not normalized:
        issues.append(f"scene {plan.order} text is empty")
        return issues
    if len(normalized) > max_chars:
        issues.append(f"scene {plan.order} exceeds {max_chars} characters")
    leaked = [marker for marker in CONTRACT_LEAK_MARKERS if marker in normalized]
    if leaked:
        issues.append(f"scene {plan.order} leaks contract markers: {', '.join(leaked)}")
    return issues


def validate_results(
    results: list[SceneResult],
    plans: list[ParallelScenePlan],
    max_chars: int = DEFAULT_SCENE_MAX_CHARS,
) -> list[str]:
    """계약 목록과 worker 결과를 비교해 조립 전 차단할 문제를 반환한다."""
    issues: list[str] = []
    expected_orders = [plan.order for plan in plans]
    actual_orders = [result.order for result in results]
    if sorted(actual_orders) != expected_orders:
        issues.append("scene result order is duplicate or missing")
    plan_by_order = {plan.order: plan for plan in plans}
    for result in results:
        plan = plan_by_order.get(result.order)
        if plan is None:
            issues.append(f"scene {result.order} has no matching plan")
            continue
        if result.title != plan.title:
            issues.append(f"scene {result.order} title does not match plan")
        issues.extend(validate_scene_result(plan, result.text, max_chars=max_chars))
    return issues


def build_review_source(
    results: list[SceneResult],
    plans: list[ParallelScenePlan],
) -> str:
    """Reviewer에게만 전달할 장면 경계·계약 포함 원고를 만든다."""
    issues = validate_results(results, plans)
    if issues:
        raise ValueError("; ".join(issues))
    plan_by_order = {plan.order: plan for plan in plans}
    sections = []
    for result in sorted(results, key=lambda item: item.order):
        plan = plan_by_order[result.order]
        contract = json.dumps(plan.model_dump(), ensure_ascii=False)
        sections.append(
            f"[장면 {result.order} — {result.title}]\n"
            f"[장면 계약]\n{contract}\n"
            f"[장면 원고]\n{result.text.strip()}"
        )
    return "\n\n".join(sections)


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
