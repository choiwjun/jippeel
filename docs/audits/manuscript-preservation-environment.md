# Manuscript preservation QA environment notes

Scope: read-only QA preparation for `feat/manuscript-preservation`, except this document. I did not edit source files. I did not start backend or frontend services. I did not touch the live `backend/jippeel.db` database or any running `:8000` service.

## Discovered runtime from WSL

Use Windows Node/npm through `cmd.exe`. The project `frontend/node_modules` contains Windows optional native packages:

- `frontend/node_modules/@rollup/rollup-win32-x64-gnu`
- `frontend/node_modules/@rollup/rollup-win32-x64-msvc`
- `frontend/node_modules/@esbuild/win32-x64`

The Linux WSL Node exists, but it is not the normal frontend runtime for this checkout because Linux Rollup optional dependency is absent.

| Check | Command | Result |
| --- | --- | --- |
| WSL Node | `which node && node -v && which npm && npm -v` | `/home/hunter8891/.nvm/versions/node/v22.23.2/bin/node`, Node `v22.23.2`, npm `10.9.8` |
| Windows PATH lookup | `cmd.exe /C "where node && where npm && where npx"` | First PATH hit is `C:\Users\wj941\AppData\Local\hermes\node\node.exe`; npm/npx from the same directory. WinGet Node `v24.15.0` is also present later on PATH. |
| Windows Node/npm/npx in frontend | `cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\frontend && node -v && npm -v && npx --version"` | Node `v22.23.2`, npm `10.9.8`, npx `10.9.8` |
| Windows Playwright | `cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright --version"` | `Version 1.62.1` |
| Windows backend venv | `cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && .venv\Scripts\python.exe --version && .venv\Scripts\python.exe -m uvicorn --version"` | Python `3.14.4`; uvicorn `0.52.4` |

Playwright browser caches found:

- Windows: `C:\Users\wj941\AppData\Local\ms-playwright` has `chromium-1234`, `chromium_headless_shell-1234`, and older browser builds.
- WSL: `/home/hunter8891/.cache/ms-playwright` has `chromium-1234`, `chromium_headless_shell-1234`, `ffmpeg-1011`.

## Prior audit/runtime command evidence inspected

Relevant prior files:

- `docs/audits/validation-review.md`: records backend `201 passed, 1 warning`, Windows frontend build success, and WSL build failure due mixed platform dependencies.
- `docs/audits/pytest.txt`: raw backend output: `201 passed, 1 warning in 10.91s`.
- `docs/audits/build-windows.txt`: Windows frontend build succeeded with an existing duplicate `build` key warning in `vite.config.ts`.
- `docs/audits/build-wsl.txt`: WSL Node build failed with missing `@rollup/rollup-linux-x64-gnu`; this is an environment/platform mismatch, not evidence of a TypeScript regression.
- `docs/audits/frontend-probe.cjs`: uses project Playwright from `frontend/node_modules/@playwright/test` against a read-only static server on `127.0.0.1:15174`; all API calls are mocked.
- `docs/audits/frontend-static-server.cjs`: serves `frontend/dist` on `127.0.0.1:15174` for frontend-only probes.
- `frontend/playwright.config.ts`: current E2E config uses `baseURL: http://localhost:5173`, starts `npm run dev -- --port 5173`, and has `reuseExistingServer: true`.
- `frontend/vite.config.ts`: dev proxy is hardcoded to backend `http://localhost:8000`.

The current Playwright config is not safe as-is for manuscript-preservation integration QA because it can reuse an existing frontend server and routes API traffic to `:8000`.

## Fresh frontend baseline run

Executed from WSL through Windows `cmd.exe`; no dependency install was done.

### TypeScript

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx tsc -b --pretty false
```

Result: exit `0`, no stdout/stderr.

### Production build

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npm run build
```

Result: exit `0`.

Important output:

```text
> jippeel-frontend@0.1.0 build
> tsc -b && vite build

▲ [WARNING] Duplicate key "build" in object literal [duplicate-object-key]

    vite.config.ts:38:2:
      38 │   build: {
         ╵   ~~~~~

  The original key "build" is here:

    vite.config.ts:11:2:
      11 │   build: {
         ╵   ~~~~~

vite v5.4.21 building for production...
✓ 228 modules transformed.
✓ built in 3.10s
```

The duplicate `build` key warning is pre-existing and is also recorded in earlier audits.

## Backend baseline status

I did not rerun backend tests in this QA-prep pass because the task says no DB access. The parent freshly ran 201 passed, 1 warning in 8.52s; see `preservation-baseline-pytest.txt`. The earlier audit independently recorded the same count in 10.91s. These are separate runs.

The recorded safe backend test surface is the Windows venv:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\backend
set DATABASE_URL=sqlite:///C:/Users/wj941/AppData/Local/Temp/jippeel-pytest-baseline.db
.venv\Scripts\python.exe -m pytest -q
```

Use a unique temp database path for any fresh run. Do not use `backend/jippeel.db`.

## Safe isolated integration setup for manuscript-preservation QA

Do not reuse `:8000` or the current `frontend/playwright.config.ts` default server. Use dedicated ports and a temp DB.

Recommended ports:

- Backend: `127.0.0.1:18080`
- Frontend dev server, if needed: `127.0.0.1:15173`
- Avoid `:8000`, `:5173`, and existing static probe `:15174`.

### Option A: production-like single-origin test through FastAPI static mount

Use this for full browser integration when `frontend/dist` is current.

1. Build frontend with Windows Node:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend
npm run build
```

2. Start backend on a dedicated port with a unique temp DB. Set `DATABASE_URL` before importing `app.main`.

```cmd
cd /d C:\Users\wj941\Documents\jippeel\backend
set DATABASE_URL=sqlite:///C:/Users/wj941/AppData/Local/Temp/jippeel-mp-e2e-%RANDOM%.db
set IM_NOT_AI_DIAGNOSE_CMD=.venv\Scripts\python.exe ..\scripts\e2e_refine_stub.py diagnose {input} {diagnosis}
set IM_NOT_AI_REFINE_CMD=.venv\Scripts\python.exe ..\scripts\e2e_refine_stub.py refine {input} {output}
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18080
```

3. Run Playwright with a temporary config whose `baseURL` is `http://127.0.0.1:18080` and with no `webServer` reuse. The specs can use relative `/api/v1/...` against the same origin.

This avoids CORS and avoids Vite's hardcoded `:8000` proxy.

### Option B: dev-server test with a temporary Vite config

Use this only if QA must exercise Vite dev behavior.

1. Start backend as above on `127.0.0.1:18080` with a unique temp DB.
2. Generate a temporary Vite config outside source-controlled files, for example under `.eval_tmp/`, that sets:

```ts
server: {
  host: '127.0.0.1',
  port: 15173,
  strictPort: true,
  proxy: {
    '/api': { target: 'http://127.0.0.1:18080', changeOrigin: true },
  },
}
```

3. Start Vite with Windows Node:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend
npx vite --host 127.0.0.1 --port 15173 --strictPort --config ..\.eval_tmp\vite-mp-isolated.config.ts
```

4. Run Playwright with a temporary config whose `baseURL` is `http://127.0.0.1:15173`, `reuseExistingServer: false`, and a `webServer.url` on `15173`.

This avoids the checked-in config's `:5173` reuse and avoids the checked-in Vite proxy target `:8000`.

## QA cautions for the implementation reviewer

- Verify `DATABASE_URL` is set before backend import or uvicorn startup.
- Use `--strictPort` for frontend and backend startup checks. Fail if a dedicated port is already occupied.
- Do not call or probe `http://localhost:8000` during this branch QA.
- Do not run Alembic or pytest against `backend/jippeel.db`.
- If E2E tests create projects/endpoints, they must do so only in the temp DB and clean up, but temp DB deletion is the real isolation boundary.
- The existing browser specs mutate their backend through API setup/teardown. That is safe only with the temp DB setup above.
- Current frontend `playwright.config.ts` and `vite.config.ts` need override/temporary config for isolated integration. Running `cd frontend && npx playwright test` as-is is not isolated.
