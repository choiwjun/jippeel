# AI Context Consistency Validation — Task4 QA

Status: READY FOR REREVIEW

Captured: 2026-09-08T09:31:49.044118+00:00
Latest run ID: `20260908-182941-647883`

## Scope freeze

Changed scope is limited to Task4 QA files and evidence:

- `scripts/ai_context_fake_llm_server.py`
- `scripts/ai_context_backend_fixture.py`
- `frontend/vite.ai-context.config.ts`
- `frontend/playwright.ai-context.config.ts`
- `frontend/e2e/ai-context-consistency.spec.ts`
- `docs/audits/ai-context-consistency-validation.md`
- `.eval_tmp/ai-context-task-4/` evidence only

For the review fix, only `frontend/e2e/ai-context-consistency.spec.ts`, this report, and evidence changed. No production source, UI/API implementation, dependencies, commits, index/branch, `HANDOFF.md`, or children were used.

## Review finding fixed

Independent review report: `docs/audits/ai-context-task-4-review.md`.

Finding: browser canon test asserted only `/검사 기준/`, not exact displayed provenance. This could pass with a wrong revision or hash.

Fix now in `frontend/e2e/ai-context-consistency.spec.ts`:

- Before clicking canon run, fetch the real saved chapter via `GET /api/v1/chapters/{chapter_id}`.
- Compute SHA256 from `savedChapterForCanon.content_md`.
- Assert the exact visible browser text:
  - `검사 기준 — 작품 #1 · 회차 #1 · rev 1 · hash b7d5fa523f776666ef9759325be9eba3821e3c2fb90c46424156a545b57a2d07`
- Assert API canon history and DB `canon_runs.context_json` `checked_input_revision` and `checked_input_hash` equal the same independent source.
- Capture expected/actual visible provenance in `playwright-evidence.json` as `canonProvenance`.
- Keep natural identity assertions, `worker >= 2`, distinct worker scenes, and review scene order assertions.

Captured provenance evidence:

```json
{
  "expected": "검사 기준 — 작품 #1 · 회차 #1 · rev 1 · hash b7d5fa523f776666ef9759325be9eba3821e3c2fb90c46424156a545b57a2d07",
  "actual": "검사 기준 — 작품 #1 · 회차 #1 · rev 1 · hash b7d5fa523f776666ef9759325be9eba3821e3c2fb90c46424156a545b57a2d07",
  "source": {
    "project_id": 1,
    "chapter_id": 1,
    "revision": 1,
    "hash": "b7d5fa523f776666ef9759325be9eba3821e3c2fb90c46424156a545b57a2d07"
  },
  "apiHistory": {
    "project_id": 1,
    "chapter_id": 1,
    "chapter_revision": 1,
    "include_chapter_content": true,
    "episode_purpose": "series_finale",
    "included_character_ids": [
      1,
      2
    ],
    "included_lore_ids": [
      1
    ],
    "injected_lore": [],
    "included_relationship_ids": [
      1
    ],
    "included_foreshadow_ids": [
      1,
      3,
      2
    ],
    "approved_foreshadow_ids": [
      1
    ],
    "future_reference_foreshadow_ids": [
      2,
      3
    ],
    "outline": {},
    "unknown_labels": [
      "foreshadow_history_is_current_record_only"
    ],
    "characters": 2,
    "lore": 1,
    "foreshadows": 3,
    "audience_known": 0,
    "checked_input_revision": 1,
    "checked_input_hash": "b7d5fa523f776666ef9759325be9eba3821e3c2fb90c46424156a545b57a2d07"
  },
  "dbHistory": {
    "project_id": 1,
    "chapter_id": 1,
    "chapter_revision": 1,
    "include_chapter_content": true,
    "episode_purpose": "series_finale",
    "included_character_ids": [
      1,
      2
    ],
    "included_lore_ids": [
      1
    ],
    "injected_lore": [],
    "included_relationship_ids": [
      1
    ],
    "included_foreshadow_ids": [
      1,
      3,
      2
    ],
    "approved_foreshadow_ids": [
      1
    ],
    "future_reference_foreshadow_ids": [
      2,
      3
    ],
    "outline": {},
    "unknown_labels": [
      "foreshadow_history_is_current_record_only"
    ],
    "characters": 2,
    "lore": 1,
    "foreshadows": 3,
    "audience_known": 0,
    "checked_input_revision": 1,
    "checked_input_hash": "b7d5fa523f776666ef9759325be9eba3821e3c2fb90c46424156a545b57a2d07"
  }
}
```

## Final review-fix GREEN commands

### Syntax/list check

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command 'Set-Location "C:\Users\wj941\Documents\jippeel\frontend"; & npx playwright test --config playwright.ai-context.config.ts --list 2>&1 | Tee-Object -FilePath "..\.eval_tmp\ai-context-task-4\playwright-list-after-canon-provenance-fix.txt"; exit $LASTEXITCODE'
```

Evidence:

- `.eval_tmp/ai-context-task-4/playwright-list-after-canon-provenance-fix-terminal.txt`

Result: exit 0, `3 tests in 1 file`.

### Native Playwright/FastAPI/SQLite/Alembic/browser/provider integration, all 3 tests

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '$env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"; Set-Location "C:\Users\wj941\Documents\jippeel\frontend"; & npx playwright test --config playwright.ai-context.config.ts 2>&1 | Tee-Object -FilePath "..\.eval_tmp\ai-context-task-4\playwright-integration-output.txt"; exit $LASTEXITCODE'
```

Evidence:

- `.eval_tmp/ai-context-task-4/playwright-reviewfix-terminal-result.txt`
- `.eval_tmp/ai-context-task-4/playwright-reviewfix-output-decoded.txt`

Result: exit 0, `3 passed (11.8s)`.

Prior accepted gates, unchanged production source:

- Full backend native venv from backend cwd: `269 passed, 1 warning in 22.61s`, evidence `.eval_tmp/ai-context-task-4/backend_full_h2-terminal-result.txt`.
- Frontend build: exit 0 with existing duplicate `build` warning in `frontend/vite.config.ts`, evidence `.eval_tmp/ai-context-task-4/frontend-final-build-output.txt`.
- Focused backend gate: `91 passed, 1 warning in 6.80s`, evidence `.eval_tmp/ai-context-task-4/backend-focused-pytest.txt`.

## Provider JSONL evidence

Raw provider JSONL from the review-fix pass:

- `.eval_tmp/ai-context-task-4/provider-prompts-reviewfix-pass.jsonl`

Payload summary:

- `.eval_tmp/ai-context-task-4/provider-payload-phase-summary-reviewfix-pass.json`

Final provider kind counts:

```json
{
  "draft": 2,
  "single_review": 1,
  "planner": 1,
  "worker": 2,
  "parallel_review": 1,
  "canon": 1
}
```

Worker assertions were not weakened. Final evidence has `worker: 2`, distinct `AI_CONTEXT_PARALLEL_SCENE_1` and `AI_CONTEXT_PARALLEL_SCENE_2` responses, and ordered parallel-review source.

## Database and state evidence

Final DB copy for the review-fix pass:

- `.eval_tmp/ai-context-task-4/ai-context-task4-reviewfix-pass.db`
- `.eval_tmp/ai-context-task-4/ai-context-task4-reviewfix-pass.db-wal`
- `.eval_tmp/ai-context-task-4/ai-context-task4-reviewfix-pass.db-shm`

Detailed DB rows/counts:

- `.eval_tmp/ai-context-task-4/db-evidence-reviewfix-pass.json`

DB counts:

```json
{
  "ai_endpoints": 1,
  "ai_usage": 7,
  "alembic_version": 1,
  "canon_runs": 1,
  "chapter_snapshots": 3,
  "chapters": 4,
  "characters": 3,
  "foreshadows": 5,
  "lore_entries": 2,
  "lore_entries_fts": 2,
  "lore_entries_fts_config": 1,
  "lore_entries_fts_content": 2,
  "lore_entries_fts_data": 4,
  "lore_entries_fts_docsize": 2,
  "lore_entries_fts_idx": 2,
  "projects": 2,
  "prompt_presets": 6,
  "quality_checks": 3,
  "refine_runs": 0,
  "relationships": 1,
  "scenes": 2,
  "volume_notes": 1
}
```

WAL/SHM files are part of the stable DB evidence.

## Cleanup

Fixture-owned PIDs from review-fix pass:

```json
{
  "provider": 14576,
  "backend": 17348
}
```

Independent PID check:

```text
14576:GONE
17348:GONE
33277:GONE

```

Listener check:

```json
{
  "15212": false,
  "18112": false,
  "18113": false,
  "8000": false,
  "5173": false
}
```

Only dedicated Task4 ports were used: frontend `15212`, backend `18112`, provider `18113`. Default-port service `8000` was out of scope and not touched. The fixture report still ends as `status=holding` with no fixture `cleanup_events` because Playwright terminates the webServer process tree externally. The observed PID/listener checks above are the cleanup evidence.

## Stable evidence preserved

Before the review-fix rerun:

- `.eval_tmp/ai-context-task-4/preserved-before-review-fix-rerun-*`

After the review-fix pass:

- `.eval_tmp/ai-context-task-4/preserved-after-review-fix-pass-*`

Missing stable evidence:

- `frontend/playwright-report` did not exist; the config uses the list reporter.

## Preserved RED history

- `.eval_tmp/ai-context-task-4/backend-full-pytest-output.txt`
- `.eval_tmp/ai-context-task-4/playwright-red-ai-panel-overlay.json`
- `.eval_tmp/ai-context-task-4/playwright-red-foreign-lore-category.json`
- `.eval_tmp/ai-context-task-4/playwright-red-lore-category.json`
- `.eval_tmp/ai-context-task-4/playwright-red-parallel-enum-literal.json`
- `.eval_tmp/ai-context-task-4/playwright-red-reopen-after-navigation.json`
- `.eval_tmp/ai-context-task-4/playwright-red-startup.json`
- `.eval_tmp/ai-context-task-4/playwright-red-ts-unterminated-workerresponses-join.txt`
- `.eval_tmp/ai-context-task-4/playwright-red-worker-classification-order-spacing.json`

Important RED causes:

- Run8 provider worker kind count was 1, expected `>= 2`; fixed with QA fake-provider full-message worker classification and locked JSONL writes. The assertion stayed `worker >= 2`.
- TS unterminated `.join(` string; fixed with escaped `\n---\n`.
- First full backend run from repository root had 262 passed and 7 migration failures because migration tests load `alembic.ini` relative to cwd. Correct backend cwd run passed 269.

## Hashes

Current changed-file hashes are recorded in:

- `.eval_tmp/ai-context-task-4/owned-files-freeze-reviewfix.json`
- `.eval_tmp/ai-context-task-4/candidate-hash-snapshot-reviewfix.json`

## Limits

- This is deterministic fake-provider contract QA, not real LLM or literary-quality proof.
- Provider JSONL `payload.messages` is the raw assertion source.
- The integration fixture used native Windows backend `.venv`, strict Alembic before app import, temp SQLite, browser, and dedicated provider/backend/frontend ports.
- No production source, UI implementation, API implementation, dependency, commit, branch/index, or `HANDOFF.md` change was made for this review fix.
