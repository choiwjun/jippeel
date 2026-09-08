# AI-context Task 4 — isolated real HTTP/browser/provider QA

Authorized after Task3 independent Spec/Quality PASS and parent native build PASS.
Review base `03bad73239e861b0f122d176fe6b014b28b278af` on `feat/ai-context-consistency`. T1/T2 backend269, T3 new fixture7/preservation fixture17/independent delayedcanon repro2/build verified. Those are not proof of this real integration.

## Binding sources
- Canonical SPEC `../specs/2026-09-08-ai-context-consistency.md` and Task4 PLAN `../plans/2026-09-08-ai-context-consistency.md`.
- **Read `docs/audits/ai-context-task-4-rulings.md` before the plan skeleton.** Its six parent-ratified safety/verification corrections override unsafe/incomplete illustrative plan code.
- Read-only source readiness evidence: `docs/audits/ai-context-task-4-environment-preflight.md`. Do not claim this is runtime proof.
- Reuse the established `scripts/preservation_backend_fixture.py` native strict-Alembic startup/owned-process cleanup pattern, but never alter that fixture or its tests/config.

## Owned files (QA only)
Create only:
- `scripts/ai_context_fake_llm_server.py`
- `scripts/ai_context_backend_fixture.py`
- `frontend/vite.ai-context.config.ts`
- `frontend/playwright.ai-context.config.ts`
- `frontend/e2e/ai-context-consistency.spec.ts`
- `docs/audits/ai-context-consistency-validation.md`
- Temporary evidence only in new `.eval_tmp/ai-context-task-4/` plus new native OS temp work directories; config JSON pointer may use `.eval_tmp/ai-context-task-4/backend-fixture.json`, archive run-specific reports before replacing pointer.

Do NOT modify frontend/backend production source, old fixtures/tests/configs, dependencies, models/migrations, HANDOFF/other docs, branch/index or commit. Do not spawn children. If real integration exposes a production bug, report exact reproduction to parent; original relevant implementer fixes it, you do not patch around it or weaken assertions.

## Environment and process contract
- Native Windows backend `.venv/Scripts/python.exe` and frontend npm/Playwright only. No Linux Node or new dependencies.
- Frontend **15212** → dedicated Vite proxy → backend **18112** → deterministic provider **18113**, loopback only. Strict ports, no reuse. Refuse occupied ports; never stop another service.
- Backend fixture creates fresh synthetic SQLite under `%TEMP%`, sets DATABASE_URL BEFORE any app import/subprocess, runs Alembic head, explicitly unsets JIPPEEL_ALLOW_TEMP_CREATE_ALL, then starts FastAPI. No production DB/WAL/SHM, real provider endpoints/credentials, or default8000/5173.
- Seed through real HTTP only, with expected_revision for manuscript writes. Record all seeded IDs/revisions, synthetic foreign-project IDs for negative tests, body/style/relationship/foreshadow sentinels, migration/head/startup results, DB/workdir/provider JSONL/log paths, and owned PIDs in phase-updated JSON.
- Fake provider serves health/models + OpenAI nonstream/stream shapes. Canon returns valid JSON `{"issues": []}`; planner returns valid ordered scenes with hook/ending_intent fields for all purposes; workers plain text; single review respects [감수]/[수정본] split and parallel review emits only opinions. Classify actual route-phase markers before generic fallback. Log every chat HTTP payload independently; do not derive proof from frontend-supplied metadata alone.
- On exit terminate/wait/kill only owned Popen handles; confirm the owned listeners are gone. Preserve logs/run-specific DB evidence for review; no cleanup outside new temp workdirs.

## Minimum acceptance matrix
1. Browser single generation and automatic review with current saved chapter identity; verify actual outgoing UI request revision and provider JSONL messages contain the expected style/selected relationships/purpose/payoff permissions.
2. Body inclusion opt-out keeps project/chapter/revision in request but omits saved-body sentinel from actual provider messages for generation/review. Avoid putting the sentinel in prompt/brief/other rows so omission is an independent assertion.
3. Browser parallel generation: assert separately logged planner, every expected worker and reviewer message; ordered worker results and all-phase style/relationships/purpose/payoff parity. Do not count only one generic kind entry as full coverage.
4. Browser canon: flush/save revision, current origin+revision/hash in displayed response, actual provider canon JSONL contains shared purpose/relations/payoff contract and future-plant/current-plant+future-resolution distinction. API-backed canon history remains origin-bound. No browser route stubs in these real integration cases.
5. Purpose coverage serial/volume_end/series_finale. Quality endpoint stores/checks true content hash and purpose-specific metrics/history; missinghook applies only serial. At least one real UI purpose selection and finale ending_intent/no-next_hook request; API assertions may cover remaining validation combinations transparently.
6. Cross-project and stale-revision generation/parallel/canon requests via real API return404/422/409 as specified and cause no new provider chat records. Include approved-only mixed-project IDs (Task1 fixed case), wrong explicit character/lore/scene IDs, missing IDs. Preserve valid unambiguous legacy/default call.
7. Capture creative rows before/after AI/canon operations through real HTTP or this fixture's explicitly owned temporary DB ONLY: chapter body/revision except intentional fixture/manual edits, foreshadow status/audience/planted/resolved fields, relationships and other included creative records must not auto-mutate. Canon/usage/quality logs may grow by design.
8. Retain T3 fixture-vs-real separation. If delayedresponse/error/recovery/browser race cases use mocks, label them as such and cite existing fixture evidence; do not claim all failure combinations were tested against actual DB. Real-route result-origin navigation may use controllable local-provider delay/release without production mutation; add if feasible within bounded harness.

## Verification and report
- Run native `npx playwright test --config playwright.ai-context.config.ts` from frontend. Browser requests must traverse actual temporary HTTP backend/provider, not a fake success route.
- Run full native backend suite using existing safe temp-db pytest runner and native frontend build once on final candidate; rerun relevant fixtures only as needed. New Playwright assertions should fail correctly if startup/protocol/contracts are broken; record meaningful RED→GREEN evidence without changing production source or weakening assertions.
- Validation report: exact commands/exit/counts, per-phase prompt evidence paths and observed sentinels, startup/migration/tempDB/process cleanup evidence, creative-state comparison, new fixture/integration distinction, missing real-boundary coverage explicitly listed. Tests verify contracts, not model/literary quality.
- Slow work: start a nonblocking bash handle, retain output location, end turn; inspect on later turns/messages. No time.sleep/shell sleep polling or long blocking await in REPL.
- Explicit parent reply READY/BLOCKED. Freeze owned files when ready for a fresh independent Task4 reviewer. No commit until parent after review.
