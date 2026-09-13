# Parallel Writing Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a parallel scene-writing mode that uses a Medium planner and Medium scene workers, assembles scenes deterministically, and sends the assembled draft to an xhigh reviewer without automatic manuscript mutation.

**Architecture:** Add a deep backend orchestration module behind a new `/api/v1/ai/generate-parallel` SSE seam. The module validates a 2–4 scene plan, runs bounded async workers, sorts results by scene order, and returns an assembled draft plus reviewer input. Keep the existing single-stream endpoint unchanged. Extend the frontend SSE adapter and AI panel with an opt-in parallel mode, worker limit, and reviewer endpoint/reasoning controls.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy read-only context loading, `asyncio.gather`/semaphore, OpenAI-compatible async client, SSE, React, TypeScript, Zustand.

**Spec:** `docs/superpowers/specs/2026-09-07-parallel-writing-engine.md`

## Global Constraints

- Preserve existing `/api/v1/ai/generate` behavior and SSE events.
- Use SQLite as the project data source; no database migration for the first slice.
- Do not automatically write generated or reviewed text into chapter content.
- Generation workers use `medium`; the reviewer uses `xhigh` by default.
- Worker concurrency is bounded at 4 and scene output order is deterministic.
- Existing `HANDOFF.md`, `.eval_tmp/`, research documents, and unrelated dirty/untracked files remain untouched.
- No external queue, Redis, Celery, browser automation, or new package dependency.

---

### Task 1: Define the parallel writing contract and orchestration module

**Files:**
- Create: `backend/app/services/parallel_writer.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/tests/test_parallel_writer.py`

**Interfaces:**
- `ParallelScenePlan`: validated `order`, `title`, `purpose`, `required_beats`, `characters`, `opening_state`, `closing_hook`.
- `ParallelPlan`: `scenes: list[ParallelScenePlan]` constrained to 2–4 contiguous orders.
- `ParallelGenerateRequest`: existing generation context plus `worker_limit`, generation model/effort, and required review options.
- `assemble_scene_results(results) -> str`: deterministic order-based assembly.
- `run_parallel_workers(plans, worker, worker_limit) -> list[SceneResult]`: bounded concurrent execution; failure cancels remaining work.

- [ ] **Step 1: Write failing contract tests**

Add tests for:

```python
def test_parallel_plan_requires_two_to_four_contiguous_scenes():
    with pytest.raises(ValidationError):
        ParallelPlan(scenes=[valid_scene(order=1)])
    with pytest.raises(ValidationError):
        ParallelPlan(scenes=[valid_scene(order=1), valid_scene(order=3)])


def test_assemble_scene_results_uses_scene_order_not_completion_order():
    result = assemble_scene_results([
        SceneResult(order=2, title="둘", text="B"),
        SceneResult(order=1, title="하나", text="A"),
    ])
    assert result == "A\n\nB"


@pytest.mark.asyncio
async def test_parallel_workers_are_bounded_and_cancel_on_failure():
    results = await run_parallel_workers(
        [valid_scene(order=1), valid_scene(order=2), valid_scene(order=3)],
        fake_worker_that_fails_on_order_2,
        worker_limit=2,
    )
    assert results == []
    assert fake_worker_that_fails_on_order_2.max_active <= 2
    assert fake_worker_that_fails_on_order_2.cancelled_orders == [3]
```

Do not use a real LLM in these tests. The worker callback is the adapter seam.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
cd backend && .venv\Scripts\python.exe -m pytest tests/test_parallel_writer.py -q
```

Expected: collection/import or assertion failures because the new contract does not exist.

- [ ] **Step 3: Implement the minimal contract**

Implement Pydantic models with these limits:

- scenes: 2–4
- `order`: contiguous 1..N
- text fields: non-empty, max 600 characters
- `worker_limit`: 2–4
- `run_parallel_workers`: use an `asyncio.Semaphore`, `asyncio.gather`, deterministic result collection, and cancellation on the first exception
- `assemble_scene_results`: sort by `order`, join with exactly one blank line, and reject missing/duplicate orders

Keep LLM client creation outside the module. The module accepts a worker callback so tests can exercise concurrency without network calls.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the same pytest command. Expected: all contract and concurrency tests pass.

- [ ] **Step 5: Commit the module and contract tests**

```bash
git add backend/app/services/parallel_writer.py backend/app/schemas.py backend/tests/test_parallel_writer.py
git -c user.name=choiwjun -c user.email=choiwjun@users.noreply.github.com commit -m "feat: add bounded parallel writing contract"
```

---

### Task 2: Add the backend parallel SSE endpoint and xhigh review phase

**Files:**
- Modify: `backend/app/routers/ai_panel.py`
- Modify: `backend/app/services/parallel_writer.py`
- Modify: `backend/tests/test_ai_generate_stream.py`

**Interfaces:**
- `POST /api/v1/ai/generate-parallel`
- Events: `parallel_start`, `planner_done`, `worker_start`, `worker_done`, ordered `message`, `review_start`, `review`, `parallel_error`, `done`.
- Existing `/api/v1/ai/generate` remains unchanged.

- [ ] **Step 1: Write failing endpoint tests**

Extend the fake LLM adapter to return one planner JSON response and scene worker responses. Add tests that assert:

```python
def test_parallel_generate_emits_workers_in_progress_and_ordered_draft(client, fake_llm, endpoint):
    response = client.post("/api/v1/ai/generate-parallel", json=_parallel_payload(endpoint["id"]))
    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert event_names(events) == [
        "parallel_start", "planner_done",
        "worker_start", "worker_start", "worker_done", "worker_done",
        "message", "done",
    ]  # review events are included when review is requested
    assert assembled_message(events) == "장면 1\n\n장면 2"


def test_parallel_review_starts_only_after_ordered_assembly(client, fake_llm, endpoint):
    response = client.post("/api/v1/ai/generate-parallel", json=_parallel_payload(endpoint["id"]))
    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert fake_llm["calls"][-1]["messages"][-1]["content"].endswith(
        "장면 1\n\n장면 2"
    )
    assert review_events_contain_no_refined_event(events)


def test_parallel_worker_failure_emits_error_and_no_partial_message(client, fake_llm, endpoint):
    fake_llm["fail_worker_order"] = 2
    response = client.post("/api/v1/ai/generate-parallel", json=_parallel_payload(endpoint["id"]))
    events = _parse_sse(response.text)
    assert any(name == "parallel_error" for name, _ in events)
    assert not any(name == "message" for name, _ in events)
```

- [ ] **Step 2: Run the endpoint tests and verify RED**

```bash
cd backend && .venv\Scripts\python.exe -m pytest tests/test_ai_generate_stream.py -k parallel -q
```

Expected: the new endpoint/tests fail because the route and orchestration are absent.

- [ ] **Step 3: Implement planner, worker, assembly, and reviewer flow**

Use the existing `_build_messages` context seam. The endpoint must:

1. Resolve the generation endpoint and send planner/worker requests with explicit `medium` effort.
2. Parse and validate planner JSON with the new models.
3. Run workers through the bounded module and emit worker status events.
4. Emit assembled `message` deltas only after all workers succeed, in scene order.
5. Resolve the reviewer endpoint independently. Require/allow `xhigh` by default and send only the assembled draft plus canonical context to the reviewer.
6. Stream reviewer output as `review` events. Do not run the existing `[수정본]` phase in this endpoint.
7. Emit `parallel_error` for planner/worker failures; preserve no database mutation.
8. Record usage with `kind="parallel_plan"`, `kind="parallel_generate"`, and `kind="parallel_review"` as best effort.

Planner and worker prompt builders must include the same context blocks, the scene contract, and explicit no-new-canon instructions. Keep prompt budgets bounded.

- [ ] **Step 4: Run focused endpoint tests and verify GREEN**

```bash
cd backend && .venv\Scripts\python.exe -m pytest tests/test_ai_generate_stream.py -k parallel -q
```

- [ ] **Step 5: Run all backend tests**

```bash
cd backend && .venv\Scripts\python.exe -m pytest -q
```

Expected: all existing tests plus parallel tests pass.

- [ ] **Step 6: Commit the backend endpoint**

```bash
git add backend/app/routers/ai_panel.py backend/app/services/parallel_writer.py backend/tests/test_ai_generate_stream.py
git -c user.name=choiwjun -c user.email=choiwjun@users.noreply.github.com commit -m "feat: add parallel scene generation and xhigh review"
```

---

### Task 3: Integrate opt-in parallel mode into the frontend AI panel

**Files:**
- Modify: `frontend/src/lib/aiStream.ts`
- Modify: `frontend/src/stores/aiPanelStore.ts`
- Modify: `frontend/src/components/panels/AiPanel.tsx`

**Interfaces:**
- New stream helper `streamParallelGenerate(body, handlers)` using the existing POST/SSE parser.
- Store state: `generationMode`, `workerLimit`, `reviewEndpointId`, `parallelProgress`.
- Existing single-generation mode remains the default.

- [ ] **Step 1: Add frontend parser/store tests if the repository test harness supports them; otherwise add type-level and build assertions**

The parser must handle `parallel_start`, `planner_done`, `worker_start`, `worker_done`, `message`, `review_start`, `review`, `parallel_error`, and `done`. Worker messages must never be appended directly to the draft before ordered assembly.

- [ ] **Step 2: Implement the shared SSE request helper**

Refactor only the transport duplication needed to support `/api/v1/ai/generate-parallel`. Preserve existing callbacks and error handling for `/api/v1/ai/generate`.

- [ ] **Step 3: Add opt-in controls**

Add a mode selector with `단일 집필` as default and `병렬 장면 집필` as the opt-in option. In parallel mode show:

- worker count 2–4
- reviewer endpoint selector from the existing endpoint list
- reviewer reasoning effort defaulted to `xhigh`
- progress text for planner and each worker

Keep NFR-201 transfer notice and manual-apply warning visible.

- [ ] **Step 4: Wire the generate action**

Send `generation_reasoning_effort: "medium"` for parallel mode and reviewer settings separately. On `message`, append only the already assembled ordered draft. On `review`, append the xhigh report to the review tab. On `parallel_error`, keep any existing text untouched and show a warning.

- [ ] **Step 5: Build the frontend**

Run:

```powershell
cd C:\Users\wj941\Documents\jippeel\frontend
npm run build
```

Expected: TypeScript and Vite build succeed; only the pre-existing duplicate `build` warning may remain.

- [ ] **Step 6: Commit the frontend integration**

```bash
git add frontend/src/lib/aiStream.ts frontend/src/stores/aiPanelStore.ts frontend/src/components/panels/AiPanel.tsx
git -c user.name=choiwjun -c user.email=choiwjun@users.noreply.github.com commit -m "feat: expose parallel writing mode in AI panel"
```

---

### Task 4: Final verification and independent review

**Files:**
- No intentional source changes; review only.

- [ ] **Step 1: Run backend and frontend verification**

```bash
cd backend && .venv\Scripts\python.exe -m pytest -q
cd frontend && npm run build
```

- [ ] **Step 2: Inspect diff and dirty-file boundary**

Verify only the planned source/test files are in the new commits. Confirm `HANDOFF.md`, `.eval_tmp/`, `docs/`, and the research document are not staged unintentionally.

- [ ] **Step 3: Dispatch an independent read-only reviewer**

The reviewer must check:

- bounded concurrency and cancellation
- ordered assembly
- planner/worker/reviewer event order
- xhigh review happens after assembly
- no automatic manuscript mutation
- existing endpoint compatibility
- prompt size and endpoint/rate-limit risks

- [ ] **Step 4: Fix any load-bearing review finding and rerun affected tests**

Do not mark complete with an open Critical, High, or Medium finding.
