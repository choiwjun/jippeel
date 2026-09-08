# Preservation final Standards re-review 1

Scope: backend-only fix `git diff fbdb796..409c268` (`409c268 fix: return refine base revision`). I ignored unrelated parallel frontend working-tree edits. I did not edit backend source, git index, server ports, browser tests, builds, production DB/WAL/SHM, or real endpoints.

## Verdict

**PASS** — 0 hard documented-standard breaches, 0 backend blockers, 1 optional smell.

## Findings

### Hard documented standard breaches

None.

Checked standards sources:
- `AGENTS.md`: routing/artifact handoff rules.
- `/home/hunter8891/.prime/agent/AGENTS.md`: worker boundary, review boundary, real-surface verification.

The backend fix is within the approved preservation-only scope. It changes only refine response/report capture plus regression coverage.

### Backend quality / spec capture blockers

None.

`backend/app/schemas.py:466-475` now makes `RefineResult.base_revision` required. `backend/app/routers/refine.py:45-90` captures `input_content_md` and `base_revision` before `humanize.run_pipeline()`, writes both to `RefineRun.report_json`, and returns the same `base_revision` in the response. The new regression at `backend/tests/test_manuscript_preservation.py:463-513` advances the chapter from a second DB session during the pipeline and verifies response/report still use the pipeline-start revision/text while current chapter becomes the concurrent edit.

### Optional smells / judgement calls

1. **Duplicated Code** — `backend/tests/test_manuscript_preservation.py:485-493` repeats the fake `humanize.run_pipeline` result shape already present in the `mock_humanize` fixture around `backend/tests/test_manuscript_preservation.py:172-184`. This is test-only and not blocking; a tiny factory could reduce future drift if more refine tests are added.

## Verification appendix

### Pinned diff inspected

```text
git diff --name-status fbdb796..409c268
M backend/app/routers/refine.py
M backend/app/schemas.py
M backend/tests/test_manuscript_preservation.py
M docs/audits/preservation-task-1-report.md
```

### Native backend full suite

Command was run through a Windows `cmd.exe` batch file so the native Windows Python process received `DATABASE_URL` and `JIPPEEL_ALLOW_TEMP_CREATE_ALL` before importing `pytest` or `app`:

```cmd
set DATABASE_URL=sqlite:///C:/Users/wj941/AppData/Local/Temp/jippeel-pytest-rereview1-16izf4h6.db
set JIPPEEL_ALLOW_TEMP_CREATE_ALL=1
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d C:\Users\wj941\Documents\jippeel\backend
C:\Users\wj941\Documents\jippeel\backend\.venv\Scripts\python.exe -m pytest
```

Result: exit `0`, harness duration `17.62s`.

```text
collected 222 items
222 passed, 1 warning in 13.86s
```

Warning only: Starlette/TestClient deprecation from installed dependencies.
