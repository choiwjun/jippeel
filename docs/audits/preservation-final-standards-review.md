# Preservation final standards/quality review

Fixed diff: `git diff b6a9ee6...fbdb796`
Commits: `ff7b02b`, `836619b`, `28a6c90`, `84dcc4b`, `fbdb796`

## Verdict

**PASS** — 0 hard documented-standard breaches, 0 concrete blockers, 2 optional smells.

## Findings (standards + quality)

### Hard documented standard breaches

None found.

Standards checked:

- `AGENTS.md`: pipeline/artifact handoff, role routing, temp/review expectations.
- `/home/hunter8891/.prime/agent/AGENTS.md`: worker boundary, real-surface verification, separate reviewer rule.

The branch stays within the approved preservation-only scope. I did not find new dependencies, production endpoint calls, server/port ownership in this review, or a broad redesign outside manuscript preservation.

### Concrete blockers: backend transaction/revision/schema/migration/QA isolation

None found.

- `backend/app/services/manuscripts.py:55-123` uses revision-qualified writes, creates the pre-image snapshot in the same transaction, and raises `409 revision_conflict` on stale writes.
- `backend/app/database.py:81-145` blocks unmigrated non-temp DB startup and only allows `create_all` for explicitly marked temp SQLite DBs.
- Alembic head `0a1b2c3d4e5f` adds `chapters.revision`, `chapter_snapshots`, and `refine_runs.base_revision`; the populated migration fixture passed.
- Backend pytest isolation is correct when `DATABASE_URL` and `JIPPEEL_ALLOW_TEMP_CREATE_ALL=1` are set before app import through the native Windows command environment.

### Optional smells / judgement calls

1. **Duplicated Code** — `backend/app/database.py:61-78` and `backend/tests/conftest.py:8-18` both parse SQLite URLs and check the temp root. Extracting a shared helper would reduce drift.
2. **Duplicated Code** — `frontend/src/components/panels/RefineReport.tsx:62-73`, `frontend/src/components/panels/SceneManager.tsx:94-106`, and `frontend/src/pages/EditorPage.tsx:346-358` repeat the flush → begin token → replacement API → complete/cache flow. If another replacement path appears, extract one helper.

## Verification appendix

### Full backend test suite

Command was run through `cmd.exe` so the Windows Python process received environment variables before importing `pytest` or `app`:

```cmd
set DATABASE_URL=sqlite:///C:/Users/wj941/AppData/Local/Temp/jippeel-pytest-review-6ohtmmrg.db
set JIPPEEL_ALLOW_TEMP_CREATE_ALL=1
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d C:\Users\wj941\Documents\jippeel\backend
C:\Users\wj941\Documents\jippeel\backend\.venv\Scripts\python.exe -m pytest
```

Result: exit `0`, duration `16.51s` wall from harness, pytest output:

```text
collected 221 items
221 passed, 1 warning in 12.94s
```

### Migration fixture

Command:

```cmd
C:\Users\wj941\Documents\jippeel\backend\.venv\Scripts\python.exe scripts\preservation_migration_fixture.py --work-dir \\tmp\\jippeel_preservation_migration_review_oreixlma --json-report \\tmp\\jippeel_preservation_migration_review_oreixlma\\migration-result-copy.json
```

Result: exit `0`, status `passed`. It upgraded a populated old-schema SQLite DB from `f9a1b2c3d4e5` to head `0a1b2c3d4e5f`, preserved old manuscript/creative rows, set new chapter revisions to `0`, kept historical `refine_runs.base_revision` as `NULL`, created no synthetic snapshots, and verified a SQLite backup comparison.

### Runner note

A WSL-style inline environment assignment did not propagate to `backend/.venv/Scripts/python.exe`; that output was discarded. Counted backend evidence is only the `cmd.exe` run above.
