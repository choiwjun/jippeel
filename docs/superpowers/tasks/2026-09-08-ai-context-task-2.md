# AI-context Task 2 — purpose and explicit payoff contracts

Status: authorized after T1 independent Spec/Quality PASS and parent native backend247 PASS.
Review base: `da49ff3da852def210a99d4b5792dd5b376d8e6f` on `feat/ai-context-consistency`.

## Canonical requirements
Read SPEC `../specs/2026-09-08-ai-context-consistency.md`, then execute **Task 2 only** in PLAN `../plans/2026-09-08-ai-context-consistency.md`. The stable preflight review and parent rulings remain binding. T1 implementation report documents the actual interfaces already delivered; do not recreate the assembler.

## Ownership
- Production: `backend/app/services/ai_context.py`, `backend/app/schemas.py`, `backend/app/routers/ai_panel.py`, `backend/app/services/canon.py`, `backend/app/services/quality.py`, `backend/app/routers/quality.py`, `backend/app/services/parallel_writer.py`.
- Tests: new `backend/tests/test_ai_context_directives.py`; existing `backend/tests/test_parallel_writer.py`, `backend/tests/test_parallel_quality.py`, `backend/tests/test_quality.py`, `backend/tests/test_foreshadows_canon.py`, `backend/tests/test_ai_generate_stream.py`. Existing `backend/tests/test_ai_context_bundle.py` may change only to add targeted purpose/payoff regressions while preserving all T1 ownership coverage.
- Own report `docs/audits/ai-context-task-2-implementation.md`, new temporary evidence `.eval_tmp/ai-context-task-2/`.
- No frontend/models/migrations/dependencies/coordinator/HANDOFF/other docs/branch/index changes. No commits or children. Parent commits only after independent review.

## Required behavior
- Shared `purpose_directive(purpose)` and purpose-aware briefs across single generation/review, parallel planner/workers/reviewer, canon and local quality. `serial` default; `volume_end` and `series_finale` honor closure rather than force unresolved conflict or next-episode hooks.
- Add `ending_intent`; enforce SPEC brief contract inside GenerateContext. Keep legacy serial validation. `parse_parallel_plan(raw, episode_purpose="serial")` must validate all three purpose cases while preserving scene order, limits, markers and cancellation.
- `approved_foreshadow_ids` is request permission, not obligation or proof of payoff. Always include these rows even when auto-foreshadow is off or its cap exhausted. No automatic state/body/knowledge mutation. Permit only selected payoff/reveal; canon may still flag unrelated contradictions. Respect already-known/public information, rather than incorrectly treating every unapproved row as secret.
- Separate future **planting** (not current fact) from future **resolution** (existing planted clue remains real; resolution is a future plan). Current rows with unknown timing remain labelled current record/unknown history. Do not implement historical-memory reconstruction. Preserve validation of every consumed row/reference against the row and request project, including approved-only inference from T1.
- Local quality uses same purpose contract. Missing hook penalty/suggestion applies only to serial; no fabricated finale literary score. Keep true text content_hash and deduplicate history by text hash + purpose using existing JSON metadata. Older rows with no purpose metadata are serial-compatible.
- Preserve exact captured canon input revision/hash and legacy context count keys; source is fixed before provider awaits, not rebuilt on return. Keep no-provider-on-invalid request and opt-out identity behavior from T1.

## Verification
Use TDD: focused RED before source, focused GREEN, existing T1 owned tests, then one full native backend suite. Read native safe runner `.eval_tmp/run_backend_pytest.py` (do not edit), which sets fresh TEMP DATABASE_URL + JIPPEEL_ALLOW_TEMP_CREATE_ALL=1 before app/pytest imports. Use Windows `backend/.venv/Scripts/python.exe` via cmd.exe from backend directory. No production DB/WAL/SHM/services/real LLM/ports8000/5173/deps. Intercept actual messages to fake complete/stream calls for every phase, use synthetic DB history/no-mutation assertions, and record semantic and validation cases separately. Tests do not prove literary/model quality. Use nonblocking handles and end turn for slow tests; no sleep/poll loops.

Report exact changed files, RED/GREEN/full-suite outputs, bounded adaptations, remaining limits. Ask parent about real cross-task conflicts; do not broaden scope or rewrite unrelated code.
