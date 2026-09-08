# AI-context Task 1 implementation report

## Scope

Implemented Task 1 only on branch `feat/ai-context-consistency`.
Review base from parent: `49b813933d2c5d11a1a811ce42b742f615f698f8`.
Round 1 fixes address independent review finding F1 from `docs/audits/ai-context-task-1-review.md`.

Changed owned files:

- `backend/app/services/ai_context.py` new shared ContextBundle module.
- `backend/app/schemas.py` additive schema fields and validation.
- `backend/app/routers/ai_panel.py` generation/parallel bundle wiring and context metadata.
- `backend/app/services/canon.py` canon bundle input and immutable checked input provenance.
- `backend/app/routers/quality.py` canon-only validation/provenance ordering.
- `backend/tests/test_ai_context_bundle.py` new and round-1 regression tests.
- `backend/tests/test_ai_generate_stream.py` parallel style/context parity test.
- `backend/tests/test_foreshadows_canon.py` canon provenance regression and updated compatible context assertion.

Evidence files were written only under `.eval_tmp/ai-context-task-1/`.
No frontend, model, migration, DB, coordinator, branch, commit, dependency, or reviewer-owned artifact change was made by this worker.

## Implementation notes

- Added `ContextBundleRequest` and `ContextBundle` in `app.services.ai_context`.
- Centralized current project/chapter/scene identity resolution and same-project validation.
- Preserved legacy generation behavior: `chapter_id` still includes chapter body by default.
- Added `include_chapter_content=false` support without dropping project/chapter identity or revision checks.
- Added `expected_revision` schema/validation and reused `app.services.manuscripts.RevisionConflict.detail()` for the `revision_conflict` response shape.
- Added selected relationship opt-in:
  - generation includes only relationships where both endpoints are selected validated characters;
  - zero or one selected character returns empty relationship metadata, not 422;
  - canon includes all same-project relationships when requested and rejects cross-project endpoints.
- Single generation start and parallel start keep old fields and add `context_metadata`.
- Single review, parallel planner, workers, and reviewer receive the same prebuilt context text. Style profile now reaches all parallel phases.
- Canon builds and validates the bundle before endpoint resolution/client creation. It captures input revision and SHA256 before provider await and stores/returns them in context JSON.
- Legacy canon count keys (`characters`, `lore`, `foreshadows`, `audience_known`) are preserved inside the expanded context object.

## Round 1 F1 fix

- Approved foreshadow IDs now participate in project inference before any project-dependent style, auto lore, auto foreshadow, or relationship assembly.
- Approved foreshadow IDs are deduped in caller order.
- Missing approved foreshadow IDs return 404 before provider client creation.
- Mixed approved foreshadow IDs from different projects return 422 when no other current identity exists.
- Approved foreshadow IDs that conflict with chapter/project/scene/character/lore identity return 422.
- Every consumed foreshadow reference now validates `planted_chapter_id` and `resolved_chapter_id` against both the foreshadow row's own project and the resolved request project.
- Positive approved-only generation can infer its project and use that project for opted-in style and auto-lore lookup without leaking another project's context.
- Full payoff/reveal semantics remain deferred to T2. T1 still does not implement or call `purpose_directive()`.

## TDD and verification evidence

Initial RED command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py tests/test_ai_context_bundle.py -q"
```

Initial RED result: exit `2`.
Saved to `.eval_tmp/ai-context-task-1/red-test-ai-context-bundle.txt`:

```text
ModuleNotFoundError: No module named 'app.services.ai_context'
1 error in 0.25s
```

Round 1 RED command after adopting F1 regressions:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py tests/test_ai_context_bundle.py -q"
```

Round 1 RED result: exit `1`.
Saved to `.eval_tmp/ai-context-task-1/round1-red-approved-foreshadow.txt`:

```text
5 failed, 17 passed, 1 warning in 4.23s
```

Focused Task 1 GREEN command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py tests/test_ai_context_bundle.py tests/test_ai_generate_stream.py::test_generate_streams_deltas tests/test_foreshadows_canon.py::test_canon_check_success -q"
```

Focused Task 1 GREEN result saved to `.eval_tmp/ai-context-task-1/focused-green-initial.txt`:

```text
18 passed, 1 warning in 1.80s
```

Round 1 bundle GREEN command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py tests/test_ai_context_bundle.py -q"
```

Round 1 bundle GREEN result saved to `.eval_tmp/ai-context-task-1/round1-green-ai-context-bundle-final.txt`:

```text
23 passed, 1 warning in 2.44s
```

Reviewer repro GREEN command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && set PYTHONPATH=.&& .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py ..\.eval_tmp\ai-context-task-1-review\test_repro_ai_context_edges.py ..\.eval_tmp\ai-context-task-1-review\test_repro_approved_route.py -q"
```

Reviewer repro GREEN result saved to `.eval_tmp/ai-context-task-1/round1-reviewer-repros-green-final.txt`:

```text
4 passed, 1 warning in 1.82s
```

Owned-test GREEN command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py tests/test_ai_context_bundle.py tests/test_ai_generate_stream.py tests/test_foreshadows_canon.py -q"
```

Owned-test GREEN result saved to `.eval_tmp/ai-context-task-1/round1-owned-tests-green-final.txt`:

```text
56 passed, 1 warning in 5.51s
```

Full backend suite command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py -q"
```

Full backend suite result saved to `.eval_tmp/ai-context-task-1/round1-full-backend-green-final.txt`:

```text
247 passed, 1 warning in 20.43s
```

Diff whitespace check:

```cmd
git diff --check -- backend/app/services/ai_context.py backend/app/schemas.py backend/app/routers/ai_panel.py backend/app/services/canon.py backend/app/routers/quality.py backend/tests/test_ai_context_bundle.py backend/tests/test_ai_generate_stream.py backend/tests/test_foreshadows_canon.py docs/audits/ai-context-task-1-implementation.md
```

Result: exit `0`, no output. Saved to `.eval_tmp/ai-context-task-1/round1-git-diff-check.txt`.

Purpose deferral check:

```cmd
grep -R "def purpose_directive\|purpose_directive" -n backend/app backend/tests || true
```

Result: no output. Saved to `.eval_tmp/ai-context-task-1/round1-grep-purpose-directive-final.txt`.

## Limits and remaining work

- T2 must implement `purpose_directive()`, purpose-specific prompt changes, parallel plan purpose validation, local quality purpose semantics, and full approved payoff/reveal canon semantics.
- T3 must implement frontend request snapshots and controls.
- T4 must implement full browser/provider integration evidence.
- This worker used mocked/intercepted LLM calls and temp SQLite DBs only. No real provider, production DB/WAL/SHM, ports `8000`/`5173`, or external services were used.
- Unrelated existing dirty/untracked files remain in the working tree and were not cleaned by this worker.
