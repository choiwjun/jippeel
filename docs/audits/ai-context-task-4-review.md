# AI-context Task 4 independent review

Status: PASS
Captured: 2026-09-08T09:36Z
Review base: `03bad73239e861b0f122d176fe6b014b28b278af`
Rereview snapshot: `docs/audits/ai-context-task-4-rereview-1-snapshot.json`

## Current verdict

- Spec: PASS
- Quality: PASS

No remaining findings.

The first review found one missing real-browser assertion. The rereview fix closes it. The current Playwright test now fetches the saved chapter through the real API, hashes the actual `content_md`, asserts exact visible canon provenance text, and checks the same hash/revision in API history and DB `canon_runs.context_json`.

## Scope checked

Reviewed the six frozen Task4 QA files and the canonical task/spec/plan/rulings:

- `scripts/ai_context_fake_llm_server.py`
- `scripts/ai_context_backend_fixture.py`
- `frontend/vite.ai-context.config.ts`
- `frontend/playwright.ai-context.config.ts`
- `frontend/e2e/ai-context-consistency.spec.ts`
- `docs/audits/ai-context-consistency-validation.md`

For rereview, only these implementation-owned files changed from the first review snapshot:

```json
{
  "frontend/e2e/ai-context-consistency.spec.ts": {
    "first": "427fdb373bb50b78ea5e4618bd96bf43cfa17c3018622bf2338c13a5dde658e1",
    "rereview": "bd1bd8175e82459d4d90c0ed62c8b8f4d4c7adf261a2e253fc25aa8914e2c8a1",
    "current": "bd1bd8175e82459d4d90c0ed62c8b8f4d4c7adf261a2e253fc25aa8914e2c8a1"
  },
  "docs/audits/ai-context-consistency-validation.md": {
    "first": "14cf6ce6e92af8903b26fc71386abec8e271eded91e28fdd3ec60f9017613167",
    "rereview": "b84a823b927301d874b8813cfba571169224e25f58617410e5b7bb8b4cb09753",
    "current": "b84a823b927301d874b8813cfba571169224e25f58617410e5b7bb8b4cb09753"
  }
}
```

I wrote only this report and reviewer evidence under `.eval_tmp/ai-context-task-4-review/`.

## Rereview fix inspection

File: `frontend/e2e/ai-context-consistency.spec.ts`

Relevant current lines:

- `382-386`: fetches `GET /api/v1/chapters/{chapter_id}` before canon and computes `expectedCanonHash` from `savedChapterForCanon.content_md`.
- `387-393`: builds exact expected visible text and asserts `page.getByText(expectedCanonProvenance, { exact: true })`, then compares actual text to expected.
- `410-420`: asserts API history and DB canon context use the same project/chapter/revision/hash.
- Existing strong checks remain: `worker` count minimum 2, distinct `AI_CONTEXT_PARALLEL_SCENE_1` and `AI_CONTEXT_PARALLEL_SCENE_2`, ordered parallel-review source, negative no-provider matrix, and creative-state preservation.

Independent source checks are recorded in `.eval_tmp/ai-context-task-4-review/rereview-1-hash-and-source-checks.json`.

## Independent commands run for rereview

### Native Playwright/FastAPI/SQLite/Alembic/browser/provider integration

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '$ErrorActionPreference="Stop"; $env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"; Set-Location "C:\Users\wj941\Documents\jippeel\frontend"; & npx playwright test --config playwright.ai-context.config.ts 2>&1 | Tee-Object -FilePath "..\.eval_tmp\ai-context-task-4-review\rereview-1-playwright-output.txt"; exit $LASTEXITCODE'
```

Result: exit 0, `3 passed (11.9s)`.

Evidence copied/preserved:

- `.eval_tmp/ai-context-task-4-review/rereview-1-playwright-output.txt`
- `.eval_tmp/ai-context-task-4-review/rereview-1-playwright-integration-output.txt`
- `.eval_tmp/ai-context-task-4-review/rereview-1-backend-fixture.json`
- `.eval_tmp/ai-context-task-4-review/rereview-1-playwright-evidence.json`
- `.eval_tmp/ai-context-task-4-review/rereview-1-provider-prompts.jsonl`
- `.eval_tmp/ai-context-task-4-review/rereview-1-ai-context-task4.db`
- `.eval_tmp/ai-context-task-4-review/rereview-1-ai-context-task4.db-wal`
- `.eval_tmp/ai-context-task-4-review/rereview-1-ai-context-task4.db-shm`
- `.eval_tmp/ai-context-task-4-review/rereview-1-summary.json`

### Earlier independent reviewer gates retained

These were run in the first review on the same app/source base before the assertion-only rereview fix:

- Focused native backend tests from `backend/` cwd with temp DB: exit 0, `91 passed, 1 warning in 5.91s`; evidence `.eval_tmp/ai-context-task-4-review/backend-focused-pytest-output.txt`.
- Native frontend build: exit 0; evidence `.eval_tmp/ai-context-task-4-review/frontend-build-output.txt`; existing duplicate `build` key warning only.

Parent also reported full native backend suite passed: `269 passed`, log `docs/audits/ai-context-task-4-parent-backend.txt`.

## Rereview evidence summary

- Dedicated integration ports before run: 15212/18112/18113 closed.
- Default port 8000 was already occupied by preexisting PID 7196. It was not used or touched.
- Dedicated ports after run: 15212/18112/18113 closed.
- Owned PIDs after run: provider 21956 GONE, backend 23408 GONE.
- Fixture report status remained `holding` with no cleanup events because Playwright externally killed its webServer process tree. Independent PID/listener checks show no owned listener remained.
- Integration fixture used temp DB path under `%TEMP%`, set `DATABASE_URL` before backend start, ran Alembic head, and unset `JIPPEEL_ALLOW_TEMP_CREATE_ALL` for integration.
- Provider JSONL kind counts from independent rereview run: `{ "draft": 2, "single_review": 1, "planner": 1, "worker": 2, "parallel_review": 1, "canon": 1 }`.
- Provider payloads still show required phase parity. Single generation/review body opt-out omitted the body sentinel. Legacy generation included it.
- Negative API matrix kept provider prompt count unchanged from 7 to 7 for all eight negative cases.
- Creative snapshots before/after matched for chapters, characters, relationships, lore, and foreshadows.
- DB evidence shows 3 quality rows with the same true body hash and purpose-specific metrics.

Captured exact canon provenance from the independent rereview run:

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

Independent hash check:

- SHA256 of actual saved body sentinel: `b7d5fa523f776666ef9759325be9eba3821e3c2fb90c46424156a545b57a2d07`.
- Displayed expected text equals displayed actual text.
- API history `checked_input_hash` equals that hash.
- DB history `checked_input_hash` equals that hash.

## Initial finding history

### First review finding — fixed

Severity: Major.

Previous file/lines: `frontend/e2e/ai-context-consistency.spec.ts:384` and `401-404`.

Problem: the first Task4 Playwright spec asserted only generic `/검사 기준/` visibility for browser canon provenance. API history checked revision/hash shape, but the browser assertion could pass with a wrong displayed revision or hash.

Fix evidence: current `frontend/e2e/ai-context-consistency.spec.ts:382-420` asserts exact visible project/chapter/revision/hash and verifies the same hash in API history and DB. Independent rereview Playwright run passed with captured expected/actual provenance above.

## Hashes

Current file hashes match `docs/audits/ai-context-task-4-rereview-1-snapshot.json`.

```json
{
  "scripts/ai_context_fake_llm_server.py": "c6f166142f0fd7edabce71e30ddba14e4c833bedb45c2e4becba11e3cebdf81e",
  "scripts/ai_context_backend_fixture.py": "70ba234f2d618c6172e97494d32499f30e40384db2179a3a1299ffb31d612057",
  "frontend/vite.ai-context.config.ts": "244ffe98e8595d1af5b060fc815ce7b6d50e9c29772d92900d2ed8c0d00ff6d9",
  "frontend/playwright.ai-context.config.ts": "7d1e26226904afc4436d2814ef03747d8616948d9c02046296a89a08708d3bc9",
  "frontend/e2e/ai-context-consistency.spec.ts": "bd1bd8175e82459d4d90c0ed62c8b8f4d4c7adf261a2e253fc25aa8914e2c8a1",
  "docs/audits/ai-context-consistency-validation.md": "b84a823b927301d874b8813cfba571169224e25f58617410e5b7bb8b4cb09753"
}
```

First review evidence was preserved before rereview:

- `.eval_tmp/ai-context-task-4-review/preserved-before-rereview-1/`

Additional rereview evidence:

- `.eval_tmp/ai-context-task-4-review/rereview-1-pre-port-check.json`
- `.eval_tmp/ai-context-task-4-review/rereview-1-post-port-check.json`
- `.eval_tmp/ai-context-task-4-review/rereview-1-owned-pids.txt`
- `.eval_tmp/ai-context-task-4-review/rereview-1-summary.json`
- `.eval_tmp/ai-context-task-4-review/rereview-1-hash-and-source-checks.json`

## Limits

- This is contract QA with a deterministic fake provider. It is not proof of real LLM or literary quality.
- I did not rerun full backend for the assertion-only fix.
- I did not edit app/source/test implementation files.
- I did not stage, commit, clean, kill default-port services, or touch `HANDOFF.md`.
