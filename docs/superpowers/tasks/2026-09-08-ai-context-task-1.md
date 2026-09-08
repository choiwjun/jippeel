# AI-context Task 1 — implementation handoff

Status: authorized after independent preflight PASS on the stable SPEC/PLAN hashes recorded in docs/audits/ai-context-preflight-review.md.

## Canonical requirements
- Read SPEC `../specs/2026-09-08-ai-context-consistency.md`.
- Execute **Task 1 only** in PLAN `../plans/2026-09-08-ai-context-consistency.md`, including parent A1–A3 addenda. Later tasks provide interface context, not permission to implement them.
- Scope approval already granted by the user. Preserve manuscript preservation; no operational deployment.

## Owned files
- Create `backend/app/services/ai_context.py`.
- Modify `backend/app/schemas.py`, `backend/app/routers/ai_panel.py`, `backend/app/services/canon.py`.
- Modify `backend/app/routers/quality.py` **only canon validation-before-provider and captured-input provenance routing**.
- Create `backend/tests/test_ai_context_bundle.py`; modify `backend/tests/test_ai_generate_stream.py`, `backend/tests/test_foreshadows_canon.py`.
- Write `docs/audits/ai-context-task-1-implementation.md` and new `.eval_tmp/ai-context-task-1/` evidence files only.
- No frontend, models, migration, dependency, other source/doc/index/branch changes. No commit until parent explicitly requests one after independent review.

## Task boundary and essential checks
- Centralize identity/ownership and deterministic context assembly; keep mode-specific selection/caps explicit.
- Reject invalid project/chapter/scene/character/lore/consumed-foreshadow/relationship endpoints before endpoint/client/provider work. Reuse `revision_conflict` shape. Legacy unambiguous calls and body inclusion default remain compatible.
- Identity survives body opt-out. Relationship opt-in: selected endpoints for generation, all same-project for canon, zero/one selection means empty context rather than 422.
- Style/context parity covers single gen/review and parallel planner/workers/reviewer, with existing stream markers/order/cancellation unchanged.
- Capture canon input body/revision/hash before provider await, preserve old context count fields, and pass the same prebuilt bundle through provider execution without a second read/rebuild after awaits.
- **T2 owns purpose_directive and semantic prompt changes**. T1 does not call/implement it, and retains serial-compatible prompt text. T1 may reserve additive schema/metadata fields and basic request validation required by its tests. No intermediate deployment.
- Preserve explicit prompt/preset composition and existing auto-injection behavior while replacing helpers. Do not paste plan snippets blindly if the actual fixture/type/helper differs: adapt within the same public behavior and report the change.
- Use actual negative corpus `docs/audits/ai-context-baseline-probes.md/.json` and provider-message captures, not self-confirming metadata assertions alone.

## Execution and evidence
- Use test-first regressions; record a relevant RED result before feature code, then focused GREEN, then one full backend run.
- Native Windows backend venv only. Set a new temporary DATABASE_URL and JIPPEEL_ALLOW_TEMP_CREATE_ALL=1 before any app/pytest import. Existing `.eval_tmp/run_backend_pytest.py` is the documented safe runner; do not alter it.
- Never production DB/WAL/SHM, existing services, real LLMs, ports8000/5173, dependency changes or Linux Node. No children.
- Report files, exact native commands, red/green results, full suite output, covered/untested boundaries, and any required remaining concern. Independent reviewer, not implementer, approves the task.
