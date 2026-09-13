# Parallel Writing Quality Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Strengthen parallel-writing contracts, review context, deterministic guards, evaluation coverage, and browser/live verification without changing the single-generation flow.

**Architecture:** Extend the existing `ParallelScenePlan` contract with explicit objective/choice/cost fields. Keep the user-facing assembled draft clean, but build a labeled review-only representation. Add a pure validation service before the draft/reviewer stages, an opt-in 20-case evaluator, and a Playwright fixture-based E2E test.

**Tech Stack:** FastAPI, Pydantic, asyncio, SQLite, pytest, TypeScript/React, Playwright, stdlib Python HTTP/SSE client.

**Spec:** `docs/superpowers/specs/2026-09-07-quality-hardening.md`

## Global Constraints

- Preserve `/api/v1/ai/generate` and its SSE event contract.
- Preserve SQLite as the source of truth.
- Never automatically write generated prose to chapter content.
- Do not add packages, Redis, Celery, or an external queue.
- Keep all generated evaluation artifacts under `.eval_tmp/` and out of commits.
- Live model evaluation is opt-in and must use bounded token limits.

### Task 1: Strengthen Planner/Worker Scene Contracts

**Files:**
- Modify: `backend/app/schemas.py` (`ParallelScenePlan`)
- Modify: `backend/app/routers/ai_panel.py` (parallel planner and worker prompts)
- Modify: `backend/tests/test_ai_generate_stream.py` (fake planner contracts and assertions)
- Test: `backend/tests/test_parallel_writer.py`

**Interfaces:**
- `ParallelScenePlan.objective: BriefText`
- `ParallelScenePlan.choice: BriefText`
- `ParallelScenePlan.cost: BriefText`
- Existing callers continue to use `order`, `title`, `purpose`, `required_beats`, `characters`, `opening_state`, and `closing_hook`.

- [x] Add a failing schema test that rejects a plan scene missing objective, choice, or cost.
- [x] Run the focused schema/parallel tests and confirm the failure.
- [x] Add the three required fields to `ParallelScenePlan` and update the fixture planner JSON.
- [x] Update planner instructions to require the three fields and require objective/choice/cost to be represented in `required_beats`.
- [x] Update worker instructions to show the objective, choice, and cost through action and internal judgment, while forbidding contract/meta output.
- [x] Run `pytest tests/test_parallel_writer.py tests/test_ai_generate_stream.py -k parallel -q`.
- [x] Commit as `feat: strengthen parallel scene contracts`.

### Task 2: Add Review Metadata and Deterministic Quality Guards

**Files:**
- Modify: `backend/app/services/parallel_writer.py`
- Modify: `backend/app/routers/ai_panel.py`
- Create: `backend/tests/test_parallel_quality.py`
- Modify: `backend/tests/test_ai_generate_stream.py`

**Interfaces:**
- `parallel_writer.validate_scene_result(plan: ParallelScenePlan, text: str, max_chars: int = 12000) -> list[str]`
- `parallel_writer.build_review_source(results: list[SceneResult], plans: list[ParallelScenePlan]) -> str`
- `parallel_writer.validate_results(results: list[SceneResult], plans: list[ParallelScenePlan]) -> list[str]`

- [x] Write failing tests for empty output, over-limit output, contract leakage, duplicate/missing order, and labeled review source.
- [x] Implement pure validation functions with deterministic messages; do not call an LLM from the validator.
- [x] Run the focused validator tests and confirm they pass.
- [x] Invoke validation after worker completion and before emitting `message`; generation validation errors emit `parallel_error` and skip draft/review.
- [x] Keep `assemble_scene_results` user-facing output free of labels.
- [x] Pass `build_review_source` with `[장면 N — title]`, contract fields, and each scene text to the Reviewer.
- [x] Extend the Reviewer prompt with explicit structure, motivation, and canon checklist.
- [x] Add regression assertions that the review prompt contains scene metadata and the draft does not contain metadata labels.
- [x] Run the full backend suite and commit as `feat: validate parallel drafts before review`.

### Task 3: Build the 20-Case Evaluation Harness

**Files:**
- Create: `backend/evals/parallel_cases.json`
- Create: `backend/scripts/evaluate_parallel.py`
- Create: `backend/tests/test_parallel_eval.py`
- Create: `docs/runbooks/parallel-evaluation.md`

**Interfaces:**
- Case JSON fields: `id`, `genre`, `prompt`, `required_cues`, `forbidden_cues`, `scene_count`.
- CLI: `python scripts/evaluate_parallel.py --case-file evals/parallel_cases.json --offline`
- CLI live mode: `python scripts/evaluate_parallel.py --case-file evals/parallel_cases.json --endpoint-id N --limit N --live --output ../.eval_tmp/parallel-eval.json`
- Metrics: `cases`, `protocol_pass`, `draft_nonempty`, `review_nonempty`, `required_cue_hits`, `forbidden_cue_hits`, `errors`.

- [x] Add 20 fixed Korean cases spanning action, mystery, romance, fantasy, historical, thriller, and daily-life conflict.
- [x] Write tests for case schema, unique IDs, bounded scene counts, and deterministic offline metrics.
- [x] Implement offline runner checks without model calls.
- [x] Implement opt-in streaming live runner with bounded `max_tokens`, event collection, and JSON output.
- [x] Add runbook commands and explain that the model’s own review is not an independent quality oracle.
- [x] Run the offline evaluator and commit as `test: add parallel writing evaluation corpus`.

### Task 4: Add Browser E2E Coverage

**Files:**
- Create: `frontend/e2e/parallel-writing.spec.ts`
- Modify: `frontend/playwright.config.ts` only if fixture startup needs no existing config change
- Test: existing frontend Playwright project with SSE route interception

**Interfaces:**
- Fixture SSE events: `parallel_start`, `planner_done`, two `worker_start`, two `worker_done`, `message`, `review_start`, `review`, `done`.
- Request assertions: `/api/v1/ai/generate-parallel`, `worker_limit`, reviewer endpoint/model/effort, and `preset_id`.

- [x] Add a test that creates an isolated project/chapter through API and opens the write page.
- [x] Intercept the parallel POST and return deterministic SSE events; capture request JSON.
- [x] Select parallel mode, set worker count and reviewer settings, enter prompt, and start generation.
- [x] Assert progress text, draft tab content, review tab content, and no automatic chapter mutation before explicit insertion.
- [x] Assert request payload fields and clean up test data.
- [x] Run the focused Playwright spec in the Windows frontend environment.
- [x] Commit as `test: cover parallel writing browser flow`.

### Task 5: Run Repeated Live Verification and Close the Loop

**Files:**
- Modify: `docs/runbooks/parallel-evaluation.md` with observed evidence only
- Create: `.eval_tmp/parallel-live-YYYYMMDD.json` (untracked evidence)

- [x] Run the offline 20-case evaluator.
- [x] Run a bounded live smoke with two workers and one reviewer against the configured endpoint.
- [x] Verify meaningful SSE order while ignoring SSE heartbeat comments.
- [x] Run the Playwright parallel spec and the existing a11y/app-flow specs.
- [x] Record model, endpoint, elapsed time, draft/review lengths, event counts, and reviewer findings under `.eval_tmp/`.
- [x] Run the full backend suite and Windows frontend build.
- [x] Perform a final diff review and report any remaining warnings or environmental blockers.

## Verification Commands

```bash
cd backend && .venv/Scripts/python.exe -m pytest -q
cd frontend && npm run build
cd frontend && npx playwright test e2e/parallel-writing.spec.ts
cd backend && .venv/Scripts/python.exe scripts/evaluate_parallel.py --case-file evals/parallel_cases.json --offline
```
