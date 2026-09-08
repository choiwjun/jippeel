# Task4 independent QA review

Review QA-only changes against source HEAD `03bad73239e861b0f122d176fe6b014b28b278af`.

## Scope and authority
- Read `docs/superpowers/tasks/2026-09-08-ai-context-task-4.md`, binding `docs/audits/ai-context-task-4-rulings.md`, canonical AI-context SPEC/PLAN, and current validation report.
- Inspect all six Task4 owned files listed in the task brief. They are new/untracked until parent commits. Inspect actual files, not just tracked git diff.
- Existing dirty HANDOFF/progress and unrelated untracked artifacts are parent/preexisting, not implementation changes. No cleanup/revert/staging/commit.
- Reviewer writes only `docs/audits/ai-context-task-4-review.md` and new `.eval_tmp/ai-context-task-4-review/` evidence. No implementation/source edits and no children.

## Independent verification
- Verify actual request/provider payload boundaries, natural UI identity (not forced by tests), per-scene planner/worker/reviewer payloads and ordering, body opt-out, style/relationships/purpose/payoff, canon temporal truth and immutable provenance, real API negatives with no provider calls, quality hash/purpose/history, and no automatic creative mutation.
- Distinguish purpose wire enum from rendered provider instructions. Do not require a raw enum in provider prose when the canonical directive is correct. Do not accept generic metadata or phase classifier alone as proof.
- Inspect historical QA fixes without assuming they prove all current assertions. Verify no worker-count weakening after prior count failure, and JSONL classifier/concurrent logging correctness.
- Audit temp DB creation/env-before-import/strict Alembic startup/seed readiness, native Windows paths and services, process ownership and cleanup. A report label is not proof; read logs and fresh PID/listener observations.
- Run the actual native Windows Playwright integration on a fresh fixture. Preserve implementation final-pass evidence/default pointer before your run, because defaults and frontend/test-results can be replaced. Store your own terminal output, provider JSONL, fixture report and DB/state evidence in reviewer-owned evidence folder.
- Native backend tests run from `backend/` cwd using safe temp DB environment before imports; repo-root cwd causes migration-test runner errors. Unit-only create-all bypass must never leak into strict integration.
- Run relevant native backend tests/build as needed for independent review. No dependency changes/Linux Node.

## Safety and coordination
- Only temporary Windows SQLite and deterministic local provider. Dedicated frontend15212/backend18112/provider18113, strict no reuse. Refuse occupied ports; never stop existing services.
- No production DB/WAL/SHM, real provider/secrets, default8000/5173, source edits, merge/push/deploy.
- Start slow commands with nonblocking handles and explicit parent status/output location. No sleep/poll loops or long blocking await. Send actual results explicitly; do not leave an idle promise that work will resume by itself.
- Required findings: severity + exact file/line + reproduction/evidence + smallest fix direction. Do not fix them yourself; original implementer handles fixes.
- Final report: separate Spec and Quality PASS/NEEDS FIXES, exact commands/counts/limits, before/after owned file hashes, and only scoped attribution. This is contract QA with fake AI, not literary/model-quality proof.
