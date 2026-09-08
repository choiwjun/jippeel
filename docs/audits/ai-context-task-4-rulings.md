# AI-context Task 4 — parent environment rulings

Status: binding corrections to the Task 4 plan skeleton. Actual Task 4 implementation remains gated on Task 3 independent PASS.

Evidence: `ai-context-task-4-environment-preflight.md` (read-only source/config inspection, not runtime verification).

1. Add QA-owned `frontend/vite.ai-context.config.ts` and use it explicitly. Frontend15212 must proxy only to temporary backend18112. Never inherit default proxy8000/dev5173. `strictPort`, no server reuse; refuse occupied ports rather than stopping existing services.
2. The real integration fixture must set temporary DATABASE_URL before app imports/subprocesses, run Alembic head, remove JIPPEEL_ALLOW_TEMP_CREATE_ALL, then start FastAPI. Keep the create_all bypass only in existing native unit-test runner, never claim that proves strict real startup.
3. The deterministic provider must return protocol-valid JSON for canon (`{"issues": []}`), valid purpose-compatible planner JSON, plain worker drafts, single review markers, and parallel review output. Classify exact route-phase prompt markers before generic draft/review fallback. No real providers/credentials.
4. Drive single generation/review, parallel planner/workers/reviewer, and canon on actual HTTP boundaries. Independently assert provider-owned JSONL `payload.messages` per driven phase, not only UI/store/metadata or classifier kind. Check known sentinels for inclusion/omission, style/relationships/purpose/payoff distinctions. Negative identity/revision requests must have no provider-call increase. Keep browser fixture coverage labelled separately.
5. Cleanup only owned process handles, terminate/wait then kill fallback if needed. Never kill by process name/port. Record child PIDs and verify no owned listeners remain after teardown. All data lives in new synthetic temp DB/work dirs; no production DB/WAL/SHM.
6. Update JSON evidence after each startup/migration/health/seeding stage; final report includes all seeded IDs, revision, DB/workdir, provider prompt path, owned PIDs and log paths. Preserve evidence from separate runs instead of silently overwriting the only run record.

These are narrow safety/verification corrections inside the approved isolated-QA scope, not a new feature, migration, dependency, or deployment. Parent approves them after checking the preflight report against the known native preservation integration pattern. Native Windows commands and existing dependency environments remain required.
