# Task 4 environment preflight — AI context consistency

Date: 2026-09-08
Branch checked: `feat/ai-context-consistency`
Backend frozen commit checked by `git rev-parse HEAD`: `46b1ec2704e1d0bb4a3c2abef8f862bb56631937`

Scope: read-only readiness investigation for Task 4. I did not start services. I did not import `app.main` or any backend app module. I only read stable source/config/docs and wrote this file.

## Verified source facts

- The Task 4 plan wants these QA-only files: `scripts/ai_context_fake_llm_server.py`, `scripts/ai_context_backend_fixture.py`, `frontend/playwright.ai-context.config.ts`, `frontend/e2e/ai-context-consistency.spec.ts`, and `docs/audits/ai-context-consistency-validation.md`.
- None of those Task 4 files exists yet.
- Existing preservation integration has the right seam to copy:
  - `scripts/preservation_backend_fixture.py` asserts native Windows backend venv Python, checks dedicated port occupancy, creates a temp SQLite DB, runs `alembic upgrade head`, starts `uvicorn`, waits for `/health`, seeds only synthetic data through HTTP, writes JSON evidence, and stops only its own `Popen` handle.
  - `frontend/playwright.preservation.integration.config.ts` uses two `webServer` entries, `reuseExistingServer: false`, dedicated ports, and a dedicated Vite config.
  - `frontend/vite.preservation.integration.config.ts` is needed because the default Vite proxy points `/api` to `http://localhost:8000`.
- Default frontend config is not safe for Task 4 real-backend integration:
  - `frontend/vite.config.ts` hardcodes `/api` proxy target `http://localhost:8000` and default dev port `5173`.
  - `frontend/playwright.config.ts` uses `http://localhost:5173` and `reuseExistingServer: true`.
- Backend DB environment is import-time sensitive:
  - `backend/app/database.py` reads `DATABASE_URL` at module import and creates the global engine immediately.
  - `init_db()` requires current Alembic schema unless `JIPPEEL_ALLOW_TEMP_CREATE_ALL=1` points to a DB under `tempfile.gettempdir()`.
  - Therefore the fixture must set `DATABASE_URL` before starting any subprocess that imports the app.
- The real integration fixture should exercise Alembic, not bypass it:
  - `scripts/preservation_backend_fixture.py` runs `python -m alembic upgrade head` before `uvicorn`.
  - Task 4's plan skeleton sets `JIPPEEL_ALLOW_TEMP_CREATE_ALL=1` and does not run Alembic in the shown code. That would bypass the startup schema guard and is weaker than the requested real temp Alembic path.
- HTTP seeding routes needed by Task 4 are present:
  - `POST /api/v1/projects` returns a project.
  - `POST /api/v1/projects/{pid}/chapters` returns a chapter with `revision: 0`.
  - `PUT /api/v1/chapters/{cid}/content` requires `expected_revision` and advances the revision.
  - `POST /api/v1/projects/{pid}/characters`, `POST /api/v1/projects/{pid}/characters/relations`, `POST /api/v1/projects/{pid}/lore`, and `POST /api/v1/projects/{pid}/foreshadows` exist.
  - `POST /api/v1/ai/endpoints` accepts `base_url`, optional `api_key`, `default_model`, nullable `temperature`, optional `reasoning_effort`, and `is_default`.
- Provider protocol facts:
  - Single generation calls `llm.stream_chat(..., stream=True)` through the OpenAI client.
  - Single review also streams, with user content containing `[초안 원고]`.
  - Parallel planner calls non-stream `complete_chat`; user content contains `[병렬 Planner — 장면 계약 생성]` and expects JSON with `scenes`.
  - Parallel workers call non-stream `complete_chat`; user content contains `[병렬 Worker — 자기 장면만 집필]` and expects plain draft text with no meta markers.
  - Parallel review streams; system/user prompts contain `감수` and expect review text.
  - Canon calls non-stream `complete_chat`, then parses JSON. The user asks `위 회차 본문에서 설정 모순을 검사하라` and expects `{"issues": [...]}`.
- Prompt evidence strings that should be externally visible in the provider JSONL:
  - Purpose directive: `[최종화 목적]` for `series_finale`.
  - Approved payoff block: `[이번 요청에서 회수/공개 허용된 복선: ...]`.
  - Relationship block: `[인물 관계 — 관계가 본문 행동·호칭·거리감과 모순되면 지적]`.
  - Body opt-out must keep identity metadata but must not include the saved chapter body text.
- Dedicated ports proposed by the plan are separate from Task 3's stated mocked UI port `15227`: frontend `15212`, backend `18112`, provider `18113`. They also avoid `8000` and `5173`.

## Plan mismatches that need correction before Task 4 implementation

1. **Missing dedicated Vite proxy config.**
   - The plan's `frontend/playwright.ai-context.config.ts` command runs `npx vite --host 127.0.0.1 --port 15212 --strictPort`.
   - With the current default Vite config, browser `/api` calls will proxy to `localhost:8000`, not the Task 4 backend on `18112`.
   - Minimum fix: add a QA-only `frontend/vite.ai-context.config.ts` with `/api` proxy target `http://127.0.0.1:18112`, then run Vite with `--config vite.ai-context.config.ts`.

2. **Fixture skeleton bypasses Alembic startup guard.**
   - The skeleton sets `JIPPEEL_ALLOW_TEMP_CREATE_ALL=1` and starts `uvicorn` without shown migration.
   - Minimum fix: for the integration fixture, set `DATABASE_URL` before subprocess start, run `python -m alembic upgrade head` in `backend/`, then start `uvicorn` with the same env and without `JIPPEEL_ALLOW_TEMP_CREATE_ALL` set. Keep `JIPPEEL_ALLOW_TEMP_CREATE_ALL=1` only for focused pytest commands if those tests still use `Base.metadata.create_all`.

3. **Fake provider does not classify canon.**
   - The planned fake provider returns planner JSON for planner, review text for review, and draft text otherwise.
   - Canon's real backend path expects valid JSON from a non-stream chat completion. A draft text response will trigger repair, then fail again.
   - Minimum fix: add a `canon` response branch before the generic draft branch, for example if any message contains `설정 모순을 검사하라` or the system contains `연속성 검수`, return `{"issues": []}` and log `kind: "canon"`.

4. **Prompt-log assertions are too weak for all AI-facing routes.**
   - The plan asserts prompt JSONL only after the first generation test.
   - Task 4 should prove external-truth independence from the UI by reading the provider-owned JSONL after each real provider path.
   - Minimum fix: assert the JSONL contains separate `kind` entries for `draft`, optional `review`, `planner`, `worker`, `parallel_review`, and `canon` depending on which UI paths the test drives. Assert against `payload.messages`, not against frontend store state.

5. **Cleanup should wait/kill only own handles.**
   - The skeleton calls `terminate()` for backend/provider but does not show wait/kill fallback.
   - Minimum fix: copy the preservation fixture's stop helper and apply it to both owned `Popen` handles. Do not kill by port or process name.

6. **JSON report should be written after health and seeding, or updated after each phase.**
   - The skeleton writes the report before backend health and before seeding.
   - Minimum fix: write an initial `status: started`, then update it after Alembic, provider start, backend health, and seeding. The final report should include `project_id`, `chapter_id`, `second_chapter_id`, `character_ids`, `relationship_id`, `lore_id`, `foreshadow_id`, `endpoint_id`, `chapter_revision`, `prompt_log`, `db`, `work_dir`, and owned PIDs/log paths.

## Minimum safe Task 4 implementation interfaces

### `frontend/vite.ai-context.config.ts`

Use the same shape as `vite.preservation.integration.config.ts`, with only these differences:

```ts
server: {
  host: '127.0.0.1',
  port: 15212,
  strictPort: true,
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:18112',
      changeOrigin: true,
    },
  },
}
```

### `frontend/playwright.ai-context.config.ts`

Keep the plan's dedicated ports and `reuseExistingServer: false`, but change the Vite command:

```ts
command: 'npx vite --host 127.0.0.1 --port 15212 --strictPort --config vite.ai-context.config.ts'
```

Keep the backend fixture command native Windows from `frontend/` cwd:

```ts
command: '..\\backend\\.venv\\Scripts\\python.exe ..\\scripts\\ai_context_backend_fixture.py --backend-port 18112 --provider-port 18113 --hold-server --json-report ..\\.eval_tmp\\ai-context\\backend-fixture.json'
```

### `scripts/ai_context_backend_fixture.py`

Minimum sequence:

1. Assert `os.name == "nt"` and `sys.executable` is under `backend/.venv/Scripts`.
2. Check ports `18112` and `18113` are free. Refuse reuse.
3. Create a new temp work dir and DB path under `%TEMP%`.
4. Build env with `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`, and `DATABASE_URL=sqlite:///<temp db>`. Do not import app modules.
5. Run Alembic head in `backend/` with that env.
6. Start fake provider with `--prompt-log <work>/provider-prompts.jsonl`.
7. Start FastAPI with `python -m uvicorn app.main:app --host 127.0.0.1 --port 18112` in `backend/`.
8. Wait for `/health`.
9. Seed via HTTP only:
   - project with style/synopsis text,
   - chapter 1 and chapter 2,
   - write chapter 1 content using `expected_revision: 0`; use exact body sentinel `초기 서버 본문은 프롬프트에 없어야 한다`,
   - write chapter 2 content if the navigation/origin test needs visible editor content,
   - two characters,
   - one relationship between those characters,
   - one lore row,
   - one `설치` foreshadow on chapter 1,
   - one default endpoint pointing to `http://127.0.0.1:{provider_port}/v1` with `default_model: "ai-context-fake"`, `temperature: null`, `is_default: true`.
10. Write all IDs and evidence paths to the JSON report.
11. On exit, stop only the owned backend and provider handles with terminate/wait/kill fallback.

### `scripts/ai_context_fake_llm_server.py`

Minimum response branches:

- `planner`: if last user message contains `[병렬 Planner`, return valid `{"scenes": [...]}` with `ending_intent` on the final scene for `series_finale` compatibility.
- `worker`: if last user message contains `[병렬 Worker`, return plain draft text and no `[감수]`, `[수정본]`, or `[장면 계약]` markers.
- `single_review`: if user contains `[초안 원고]`, return review text. If testing insertion of refined text, include `[수정본]` as required by the stream splitter; otherwise a review-only stream is still accepted by backend tests.
- `parallel_review`: if system/user contains `감수` and user contains `장면별 조립 원고`, return review text.
- `canon`: if user contains `설정 모순을 검사하라` or system contains `연속성 검수`, return `{"issues": []}`.
- `draft`: default plain draft text.

Every branch should append one JSON line like:

```json
{"kind":"canon","path":"/v1/chat/completions","payload":{...}}
```

The JSONL file is the independent truth source for prompt assertions.

## Suggested native Windows commands for the future implementer

Run from native PowerShell, not WSL, for the Playwright integration:

```powershell
cd C:\Users\wj941\Documents\jippeel
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:DATABASE_URL = "sqlite:///$env:TEMP/jippeel-ai-context-task4-backend-$PID.db"
$env:JIPPEEL_ALLOW_TEMP_CREATE_ALL = "1"
.\backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_context_bundle.py backend\tests\test_ai_context_directives.py backend\tests\test_quality.py backend\tests\test_parallel_writer.py backend\tests\test_parallel_quality.py backend\tests\test_foreshadows_canon.py backend\tests\test_ai_generate_stream.py -q
```

```powershell
cd C:\Users\wj941\Documents\jippeel\frontend
npm run build
npx playwright test --config playwright.ai-context.config.ts
```

Do not use production DB files, `*.db-wal`, `*.db-shm`, ports `8000` or `5173`, real LLM endpoints, or `reuseExistingServer` for Task 4.

## Readiness ruling

Task 4 is ready to dispatch after Task 3 passes if the implementer applies the six corrections above. The highest-risk blockers are the missing dedicated Vite proxy config, the Alembic guard bypass in the fixture skeleton, and the missing canon JSON response in the fake provider.
