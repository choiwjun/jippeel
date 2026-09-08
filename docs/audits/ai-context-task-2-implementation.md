# AI-context Task 2 implementation report

## Scope

Implemented Task 2 only on branch `feat/ai-context-consistency`.
Review base from parent: `da49ff3da852def210a99d4b5792dd5b376d8e6f`.

Changed owned files:

- `backend/app/services/ai_context.py`
- `backend/app/routers/ai_panel.py`
- `backend/app/services/canon.py`
- `backend/app/services/quality.py`
- `backend/app/routers/quality.py`
- `backend/app/services/parallel_writer.py`
- `backend/tests/test_ai_context_directives.py` (new)
- `backend/tests/test_quality.py`
- `backend/tests/test_parallel_writer.py`
- `backend/tests/test_foreshadows_canon.py`

Evidence files were written only under `.eval_tmp/ai-context-task-2/`.
No frontend, migrations, dependencies, production DB, services, branch/index, commits, `HANDOFF.md`, or unrelated docs were changed by this worker.

## Implementation notes

- Added shared `ai_context.purpose_directive(purpose)`.
- Single generation system prompts now include the request purpose directive.
- Single review, parallel planner, parallel workers, and parallel review inherit the same purpose directive through the prebuilt generation system prompt path.
- Removed unconditional serial-only hook/unresolved-conflict wording from generation and review prompts.
- `EpisodeBrief.ending_intent` and purpose validation already existed from the current T1 baseline. Task 2 changed prompt rendering from `종결 의도` to `결말 의도`.
- Approved foreshadow IDs are now rendered even when `auto_foreshadow` is off.
- Approved foreshadows are deduped against auto-included rows and are rendered as request-scoped payoff/reveal permission.
- Generation and canon do not mutate foreshadow status, audience knowledge, planted chapter, or resolved chapter fields.
- Future foreshadow references are still validated against row/request project.
- Future planned installation is labelled as not current fact.
- Future planned resolution no longer makes an already planted clue disappear. It stays a current record with a separate future-resolution warning.
- Canon prompts include the purpose directive and approved-payoff rule.
- Local quality now stores `episode_purpose`, `hook_score_applicable`, and true `hook_present` in metrics.
- Local quality applies the missing-hook penalty only to `serial`.
- History dedupe now compares true text `content_hash` plus `metrics_json.episode_purpose`. Older rows without purpose metadata are treated as `serial` for dedupe compatibility.
- `parallel_writer.parse_parallel_plan(raw, episode_purpose="serial")` now validates purpose-specific ending contracts while preserving default serial behavior.
- `validate_plan_for_purpose()` is importable for focused tests.

## TDD and verification evidence

Initial meaningful RED command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && set PYTHONUTF8=1&& set PYTHONIOENCODING=utf-8&& .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py tests/test_ai_context_directives.py tests/test_quality.py::test_series_finale_does_not_penalize_missing_hook tests/test_parallel_writer.py::test_parallel_serial_requires_closing_hook -q"
```

Initial RED result saved to `.eval_tmp/ai-context-task-2/red-focused-final.txt`:

```text
9 failed, 2 passed, 1 warning in 1.09s
```

Focused GREEN command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && set PYTHONUTF8=1&& set PYTHONIOENCODING=utf-8&& .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py tests/test_ai_context_directives.py tests/test_ai_context_bundle.py tests/test_quality.py tests/test_parallel_writer.py tests/test_parallel_quality.py tests/test_foreshadows_canon.py -q"
```

Focused GREEN result saved to `.eval_tmp/ai-context-task-2/focused-green-expanded-final.txt`:

```text
58 passed, 1 warning in 3.53s
```

Owned T1 + T2 regression command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && set PYTHONUTF8=1&& set PYTHONIOENCODING=utf-8&& .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py tests/test_ai_context_directives.py tests/test_ai_generate_stream.py tests/test_ai_context_bundle.py tests/test_quality.py tests/test_parallel_writer.py tests/test_parallel_quality.py tests/test_foreshadows_canon.py -q"
```

Owned regression result saved to `.eval_tmp/ai-context-task-2/owned-t1-t2-green-final3.txt`:

```text
87 passed, 1 warning in 6.23s
```

Additional quality legacy-compatibility focused command:

```cmd
cmd.exe /C "cd /d C:\\Users\\wj941\\Documents\\jippeel\\backend && set PYTHONUTF8=1&& set PYTHONIOENCODING=utf-8&& .venv\\Scripts\\python.exe ..\\.eval_tmp\\run_backend_pytest.py tests/test_quality.py::test_quality_history_legacy_rows_without_purpose_are_serial_compatible tests/test_quality.py::test_quality_history_dedup_includes_purpose_not_hash -q"
```

Result saved to `.eval_tmp/ai-context-task-2/quality-dedupe-robust-green.txt`:

```text
2 passed, 1 warning in 0.33s
```

Full native backend suite command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && set PYTHONUTF8=1&& set PYTHONIOENCODING=utf-8&& .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py -q"
```

Full suite result saved to `.eval_tmp/ai-context-task-2/full-backend-suite-final3.txt`:

```text
265 passed, 1 warning in 21.61s
```

Diff whitespace check:

```cmd
git diff --check -- backend/app/services/ai_context.py backend/app/routers/ai_panel.py backend/app/services/canon.py backend/app/services/quality.py backend/app/routers/quality.py backend/app/services/parallel_writer.py backend/tests/test_ai_context_directives.py backend/tests/test_quality.py backend/tests/test_parallel_writer.py backend/tests/test_foreshadows_canon.py
```

Result: exit `0`, no output. Saved to `.eval_tmp/ai-context-task-2/git-diff-check-final3.txt`.

## Bounded adaptations

- `backend/app/schemas.py` did not need a Task 2 edit because the current baseline already had `EpisodePurpose`, `ending_intent`, purpose-aware `GenerateContext` validation, `ParallelScenePlan.ending_intent`, and additive `CanonCheckRequest` fields.
- I kept legacy `[미회수 복선: title]` header compatibility and added current-record/future-resolution labels in block details instead of changing that header shape.
- I did not add a new score for finales. The finale quality path only disables the serial hook penalty and adds an informational human-check suggestion.

## Remaining limits and deferrals

- Historical-memory reconstruction remains deferred.
- Frontend request snapshots, shared controls, and result-origin safety remain Task 3.
- Full browser/provider integration fixtures remain Task 4.
- Tests use fake/intercepted LLM calls and temp SQLite databases only. They do not prove literary/model quality.


## Round 1 S1 reviewer fix

Reviewer finding S1 was accepted by parent. The issue was that canon metadata marked future foreshadow rows correctly, but the actual provider-bound canon prompt still grouped all unapproved rows only by `audience_knows`. This could put future planted rows under current unresolved/public headers.

Fix summary:

- Canon now partitions unapproved consumed foreshadows by time semantics before audience grouping.
- Future `planted_chapter_id` rows render as `[미래 계획 복선: ... — 현재 사실 아님]` regardless of `audience_knows`.
- Future `resolved_chapter_id` on an already planted row keeps the clue as a current record and adds only a future-resolution warning.
- Approved future rows still render as request-scoped permission and warn not to treat a future plan as existing current fact.
- Already-public current rows are rendered as public/current information, not as secrets.
- Generation helper text for unapproved `audience_knows=true` rows now says existing public info may be referenced, while new payoff/reveal or reversal still needs author permission.
- No foreshadow state, audience knowledge, planted chapter, or resolved chapter fields are mutated.

Round 1 RED command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && set PYTHONUTF8=1&& set PYTHONIOENCODING=utf-8&& .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py tests/test_foreshadows_canon.py::test_canon_prompt_labels_future_planted_rows_by_time_not_audience tests/test_foreshadows_canon.py::test_canon_prompt_keeps_future_resolution_as_current_record_plan tests/test_foreshadows_canon.py::test_canon_approved_future_plan_is_permission_without_state_mutation tests/test_ai_context_directives.py::test_generation_unapproved_public_foreshadow_is_reference_not_secret -q"
```

Round 1 RED result saved to `.eval_tmp/ai-context-task-2/round1-red-canon-prompt-matrix.txt`:

```text
3 failed, 1 passed, 1 warning in 0.73s
```

Round 1 focused GREEN result saved to `.eval_tmp/ai-context-task-2/round1-green-canon-prompt-matrix-attempt1.txt`:

```text
4 passed, 1 warning in 0.60s
```

Reviewer repro command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && set PYTHONUTF8=1&& set PYTHONIOENCODING=utf-8&& .venv\Scripts\python.exe ..\.eval_tmp\ai-context-task-2-review\canon_future_plan_prompt_repro.py"
```

Reviewer repro result saved to `.eval_tmp/ai-context-task-2/round1-reviewer-repro-canon-future-plan.txt`:

```text
exit_code=0
contains_future_label: true
contains_unresolved_secret_label: false
contains_no_current_fact_warning: true
future_reference_metadata: [1]
```

Round 1 owned T1/T2 regression command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && set PYTHONUTF8=1&& set PYTHONIOENCODING=utf-8&& .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py tests/test_ai_context_directives.py tests/test_ai_generate_stream.py tests/test_ai_context_bundle.py tests/test_quality.py tests/test_parallel_writer.py tests/test_parallel_quality.py tests/test_foreshadows_canon.py -q"
```

Round 1 owned T1/T2 result saved to `.eval_tmp/ai-context-task-2/round1-owned-t1-t2-green.txt`:

```text
91 passed, 1 warning in 6.88s
```

Round 1 full backend suite command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && set PYTHONUTF8=1&& set PYTHONIOENCODING=utf-8&& .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py -q"
```

Round 1 full backend suite result saved to `.eval_tmp/ai-context-task-2/round1-full-backend-suite.txt`:

```text
269 passed, 1 warning in 21.77s
```

Round 1 `git diff --check` result saved to `.eval_tmp/ai-context-task-2/round1-git-diff-check.txt`: exit `0`, no output.
