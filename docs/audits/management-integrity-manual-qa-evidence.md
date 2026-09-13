# Management-integrity manual QA evidence

Date: 2026-09-09 (Asia/Seoul)

## Review surface

Repository: /mnt/c/Users/wj941/Documents/jippeel

Reviewed the live git diff for the six backend routers/service and six corresponding test files named in the task. The changed handlers validate ownership before mutation, perform conflict checks before commit, scope FTS SQL before LIMIT, and preserve omitted versus explicitly supplied volume:null through model_fields_set.

## Test runner evidence

The repository contains a Windows .venv; WSL python was absent and .venv/bin/python does not exist. The first system pytest invocation failed collection because openai was not installed. Running the Windows venv without an isolated DATABASE_URL produced 53 setup errors because the default backend/jippeel.db lacks the manuscript-preservation schema. No production DB was changed.

Targeted command, using a dedicated TEMP SQLite DB:

    cmd.exe /c "set DATABASE_URL=sqlite:///C:/Users/wj941/AppData/Local/Temp/jippeel-management-qa-20260909.db && set JIPPEEL_ALLOW_TEMP_CREATE_ALL=1 && cd /d C:\Users\wj941\Documents\jippeel\backend && .venv\Scripts\python.exe -m pytest -q tests/test_lorebook_api.py tests/test_characters_api.py tests/test_foreshadows_canon.py tests/test_projects_api.py tests/test_scenes_api.py tests/test_volume_nullable.py"

Observed:

    .....................................................                    [100%]
    53 passed, 1 warning in 4.34s

Full safe backend command, using a separate dedicated TEMP SQLite DB:

    cmd.exe /c "set DATABASE_URL=sqlite:///C:/Users/wj941/AppData/Local/Temp/jippeel-management-qa-full-20260909.db && set JIPPEEL_ALLOW_TEMP_CREATE_ALL=1 && cd /d C:\Users\wj941\Documents\jippeel\backend && .venv\Scripts\python.exe -m pytest -q"

Observed:

    276 passed, 1 warning in 22.17s

The only warning in both passes was the existing AnyIO/Starlette BlockingPortal deprecation warning.

## HTTP scenario evidence

The service was started only on loopback port 18765 with a dedicated temp DB:

    powershell.exe -NoProfile -Command '$env:DATABASE_URL="sqlite:///C:/Users/wj941/AppData/Local/Temp/jippeel-management-http-20260909.db"; $env:JIPPEEL_ALLOW_TEMP_CREATE_ALL="1"; Set-Location "C:\Users\wj941\Documents\jippeel\backend"; & ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 18765'

All HTTP requests below used /mnt/c/WINDOWS/system32/curl.exe -i -sS against that service.

| Scenario | Invocation | Observed output |
|---|---|---|
| Foreign foreshadow create | curl.exe -i -sS -X POST http://127.0.0.1:18765/api/v1/projects/1/foreshadows with planted_chapter_id 2 | 422; detail says the chapter must belong to the same work. |
| Foreign foreshadow update | curl.exe -i -sS -X PATCH http://127.0.0.1:18765/api/v1/foreshadows/1 with resolved_chapter_id 2 | 422; detail identifies resolved_chapter_id. |
| Foreshadow-safe chapter delete | curl.exe -i -sS -X DELETE http://127.0.0.1:18765/api/v1/chapters/1 | 409 Conflict; follow-up GET returned 200 and the foreshadow remained. |
| Reverse-direction relation delete | curl.exe -i -sS -X DELETE http://127.0.0.1:18765/api/v1/characters/1 after relation from=2,to=1 | 409 Conflict; character 1 remained and relation listing for character 2 returned the relation. Deleting character 2 also returned 409. |
| Foreign scene reorder | curl.exe -i -sS -X PATCH http://127.0.0.1:18765/api/v1/chapters/1/scenes/order with scene ids 1 and 2 | 422; follow-up scene GETs retained sort_order 0 and 1. |
| Duplicate scene reorder | Same endpoint with two items containing id 1 | 422; duplicate scene id detail; no partial mutation. |
| Omitted volume | curl.exe -i -sS -X PATCH http://127.0.0.1:18765/api/v1/projects/1/chapters/reorder with id 3 and sort_order 2 | 200; chapter 3 retained volume:1. |
| Explicit null volume | Same endpoint with id 3, volume:null, sort_order 3 | 200; chapter 3 returned volume:null and sort_order:3. |
| FTS project/category scope | curl.exe -i -sS --get http://127.0.0.1:18765/api/v1/projects/1/lore/search with q=공통검색어, limit=1, category=용어 | 200; exactly entry id 2 from project 1/category 용어, excluding project 2 and the project-1 장소 row. |
| FTS project scope and limit | Same command without category=용어 | 200; exactly one project-1 row, never the project-2 row. |

The temporary uvicorn process was stopped with Ctrl-C after the scenarios.

## Fallback evidence

The non-production in-memory probe at docs/audits/management-integrity-fallback-probe.py forced _fts_supported to false and called the actual lorebook search handler with project/category/limit scope.

Invocation:

    powershell.exe -NoProfile -Command '$env:PYTHONPATH="C:\Users\wj941\Documents\jippeel\backend"; & "C:\Users\wj941\Documents\jippeel\backend\.venv\Scripts\python.exe" "C:\Users\wj941\Documents\jippeel\docs\audits\management-integrity-fallback-probe.py"'

Observed output:

    [(1, '용어', 'fallback needle')]

The Windows terminal rendered the Korean category correctly in the logical returned value; the captured console may display mojibake depending on the active code page. The selected row was the expected in-scope category row, not the 장소 row.

## Non-functional observation

git diff --check reported CRLF-related trailing-whitespace diagnostics on added lines in the existing patch files, including backend/app/routers/projects.py, backend/tests/test_projects_api.py, and backend/tests/test_volume_nullable.py. This did not affect the test or HTTP verdict and was not modified during this read-only QA lane.
