# AI-context final branch review

Fixed range: `70ec67eb3be02a89baefe01b3e798d033431983b..d2a5b3479969c0b13de3be00e1b1a3fbd6746063`.
Branch: `feat/ai-context-consistency`. Do not switch branch or mutate implementation.

## Review authority
- Canonical SPEC/PLAN: `docs/superpowers/specs/2026-09-08-ai-context-consistency.md` and `docs/superpowers/plans/2026-09-08-ai-context-consistency.md`.
- Binding clarifications: `docs/audits/ai-context-contract-rulings.md`, preflight review, Task4 rulings.
- Read actual full branch diff and relevant surrounding code. Task reports are evidence, not approval substitutes.
- Earlier manuscript preservation is accepted baseline, not a task to reopen. Its revision/draft/recovery/no-late-overwrite contracts must not regress; see preservation lessons/runbook.
- T1/T2/T3/T4 individually independently PASS after fixes. T4 final independent integration3PASS, focused91/buildPASS, parent fullbackend269PASS. Final branch review is still required.
- Only post-T4-review edit was parent removal of one trailing space in the validation report command; source/test/config hashes stayed fixed. Historical review snapshots intentionally retain original report hash.

## Shared safety and ownership
- Native Windows tooling for project runs. Backend tests from backend cwd and safe new temp DATABASE_URL BEFORE imports. Existing `.eval_tmp/run_backend_pytest.py` sets unit-only bypass before pytest import. Never leak bypass into strict integration.
- No production DB/WAL/SHM, secrets/real LLMs, dependencies/Linux Node, default8000/5173, existing services, stage/commit/branch/merge/push/deploy.
- Existing dirty HANDOFF/progress and unrelated untracked audit/probe artifacts are parent/preexisting, not branch changes to clean or attribute to implementers.
- Read-only implementation review. Write only assigned review report and own new evidence folder. No children or source fixes; send reproduction to parent for original implementer.
- Start slow commands nonblocking and explicitly report handle/output. No sleep/poll loops or long blocking await. Return actual terminal results and verdict; never leave only an idle promise to resume automatically.
- Findings must be actionable severity/file/line/contract/reproduction, not hypothetical preferences. Separate blocking findings from optional notes.

## Spec reviewer
Own `docs/audits/ai-context-final-spec-review.md` and `.eval_tmp/ai-context-final-spec/`.
- Independently map full implementation to SPEC/PLAN: one resolved project, validate consumed references before provider/client creation, identity vs body inclusion, saved revision compatibility, immutable canon input, style/relationships phase parity, purposes/ending_intent/payoff permissions/temporal truth/quality hash/history, and UI full pre-await snapshots and post-await ownership/cancel/navigation/recovery locks.
- Inspect cross-route/cross-task seams and defaults/legacy behavior, not just isolated task tests. Do not confuse future planting with future resolution or permission with automatic mutation. Check current editor identity naturally, late callbacks and newer request ownership.
- You alone own browser ports for final reviews: real integration15212/backend18112/fakeprovider18113; fixture15227 and preservation15225. Run relevant fresh native integration/fixtures and preserve default-pointer evidence before overwrite. Strict fresh Alembic temp DB, no reuse/route stubs for real integration. Other reviewer will NOT use browser ports.
- Distinguish actual boundary evidence, mocked fixtures and fake-AI/literary limits. Raw provider payloads and independently computed hashes matter more than labels/classifiers.

## Standards reviewer
Own `docs/audits/ai-context-final-standards-review.md` and `.eval_tmp/ai-context-final-standards/`.
- Independently inspect full diff against AGENTS and actual repository conventions: maintainable shared boundaries, typing/errors/validation, immutable captures, lifecycle cleanup, test independence and isolation, no accidental source/dependency/migration scope expansion.
- You alone run final review native frontend build; run full native backend tests in a fresh unit temp DB. Do NOT start browser/HTTP fixture servers (Spec reviewer owns those ports).
- Use CRLF-aware per-command diff whitespace check: `git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --check <base> <head>`. Existing native CRLF is intentional; do not normalize it or classify it as trailing whitespace.
- Known existing duplicate build key warning in vite.config.ts is not introduced by this branch. Do not repair unrelated code to make a clean log/worktree.

## Deliverable
Current PASS/NEEDS FIXES at top, fixed range, standards/spec evidence map, exact commands/counts, file hashes before/after, remaining limitations, and explicit agent_message parent verdict. Final documentation/runbook rollup will follow this source review; report scope accordingly.
