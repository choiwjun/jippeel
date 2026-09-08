# AI-context Task 1 independent review

Review target: uncommitted `feat/ai-context-consistency` source against base `49b813933d2c5d11a1a811ce42b742f615f698f8`.

This file now includes round 1 rereview of the accepted F1 fix. Source snapshot checked: `docs/audits/ai-context-task-1-rereview-1-snapshot.json`.

## Current verdict after fix round 1

- Spec: **PASS**
- Code Quality: **PASS**

Scope of this rereview: F1 fix and immediate regressions only. I did not reopen T2-deferred semantics.

## Current hashes verified

- `backend/app/services/ai_context.py`: `e80c309c41daefdb1cc8ff860a703372299555a4cbc47b50b2b99f8254302b4f`
- `backend/app/schemas.py`: `5b67c979bb19a826c754d98fa0b3abe3626750b1a1bc045434572d10e455b71f`
- `backend/app/routers/ai_panel.py`: `022a91c59893e51d6144d952b9acd8fb3636ecc97d93211da52159a51ffb3772`
- `backend/app/services/canon.py`: `31d432c3a91b0b016ce8ef01f4d8cd268f7ab2f9bdd0a959572bf8a78264192a`
- `backend/app/routers/quality.py`: `a7fc5093303c017b592a5d5a83e5d14d0616d220e6b540e7daa625ce714fd704`
- `backend/tests/test_ai_context_bundle.py`: `d4a45dfdd415e297fa96cea591d0261df8b442786feda2e58f345d2dd35deb6e`
- `backend/tests/test_ai_generate_stream.py`: `cb59c891829bc2083bb6ee0fdff53847b8d5d24af6604c0535b032b8893c2a3e`
- `backend/tests/test_foreshadows_canon.py`: `92f6c73fe037a77d4c6a8a09717234e15b2508a163358abb31f7253426e02a4a`

All listed hashes matched the actual current files.

## Round 1 rereview findings

### F1 — Addressed — Approved foreshadow IDs now resolve project identity and validate references before provider work

Previous issue: approved foreshadow IDs did not participate in project inference when no `project_id`, `chapter_id`, or `scene_id` was supplied.

Fix evidence:

- `backend/app/services/ai_context.py:244-261` adds `_ordered_foreshadows()`. It loads approved IDs in caller order, rejects missing IDs with `404`, and runs `_resolve_project()` for each row. This infers a project from a valid approved-only request and rejects mixed-project approved IDs with `422`.
- `backend/app/services/ai_context.py:264-282` now validates each `planted_chapter_id` and `resolved_chapter_id` against both the foreshadow row's own project and the resolved request project.
- `backend/app/services/ai_context.py:390-394` performs approved-foreshadow project inference before loading the project and before project-dependent style/auto-lore/relationship/foreshadow assembly.
- `backend/tests/test_ai_context_bundle.py:428-599` adds regressions for invalid references, mixed approved IDs, generate no-provider ordering, parallel no-provider ordering, valid approved-only project inference, legacy unbound requests, and missing approved IDs.

Regression evidence:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && set PYTHONPATH=.&& .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py ..\.eval_tmp\ai-context-task-1-review\test_repro_ai_context_edges.py ..\.eval_tmp\ai-context-task-1-review\test_repro_approved_route.py -q"
```

Result:

```text
4 passed, 1 warning in 2.23s
```

The prior temporary repros now pass.

No new F1 material findings found.

## Fresh verification

Mandated native owned-test command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py tests/test_ai_context_bundle.py tests/test_ai_generate_stream.py tests/test_foreshadows_canon.py -q"
```

Result:

```text
56 passed, 1 warning in 6.08s
```

Whitespace check for changed round 1 files:

```cmd
git diff --check -- backend/app/services/ai_context.py backend/tests/test_ai_context_bundle.py
```

Result: exit `0`, no output.

Evidence files:

- `.eval_tmp/ai-context-task-1-review/round1-owned-tests.txt`
- `.eval_tmp/ai-context-task-1-review/round1-prior-repros.txt`
- `.eval_tmp/ai-context-task-1-review/round1-diff-check.txt`

## Previously reviewed passing areas still accepted

These were checked in the initial review and/or covered by the fresh owned tests:

- Single generation validates bundle before endpoint/client/provider path.
- Parallel generation validates bundle before provider client creation and `complete_chat`.
- Canon route validates/builds the bundle and captures messages/provenance before endpoint resolution/client creation.
- Body opt-out keeps current identity and does not put the opted-out chapter body into generated context text.
- Relationship opt-in uses selected endpoints for generation and all same-project endpoints for canon.
- Zero/one selected generation relationship returns empty metadata, not `422`.
- Existing SSE event fields are preserved with additive `context_metadata`.
- Parallel planner, workers, and reviewer reuse the same base context text and style system suffix.
- Canon provenance hash/revision tests cover mutation during provider await.
- `backend/app/services/manuscripts.py:18-28` `RevisionConflict.detail()` is now reused by `backend/app/services/ai_context.py:68-69`, and the implementation report was corrected.

## Limits

- I did not run real providers, browser tests, ports `8000`/`5173`, production DB, or dependency installation.
- I did not rerun the full backend suite in this rereview.
- I treated T2 purpose directives, semantic prompt rewrites, local quality purpose behavior, and final payoff prompt semantics as deferred, per parent instruction.
