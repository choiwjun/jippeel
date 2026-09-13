# manualQa matrix: management-integrity

Verdict: PASS

Evidence directory: docs/audits (no ulw-loop plan existed, so no attempt directory was available).

## surfaceEvidence

| Scenario ID | Criterion reference | Surface | Exact invocation | Verdict | ArtifactRefs |
|---|---|---|---|---|---|
| S1 | Scene ownership and reorder atomicity | FastAPI HTTP, scenes reorder | /mnt/c/WINDOWS/system32/curl.exe -i -sS -X PATCH http://127.0.0.1:18765/api/v1/chapters/1/scenes/order -H 'Content-Type: application/json' --data '{\"items\":[{\"id\":1,\"sort_order\":5},{\"id\":2,\"sort_order\":9}]}' | PASS | E1 |
| S2 | Cross-project foreshadow references | FastAPI HTTP, foreshadow create/update | /mnt/c/WINDOWS/system32/curl.exe -i -sS -X POST http://127.0.0.1:18765/api/v1/projects/1/foreshadows -H 'Content-Type: application/json' --data '{\"title\":\"foreign-create\",\"planted_chapter_id\":2}'; then PATCH /mnt/c/WINDOWS/system32/curl.exe -i -sS -X PATCH http://127.0.0.1:18765/api/v1/foreshadows/1 -H 'Content-Type: application/json' --data '{\"resolved_chapter_id\":2}' | PASS | E1 |
| S3 | Relation-safe character deletion | FastAPI HTTP, character DELETE | /mnt/c/WINDOWS/system32/curl.exe -i -sS -X DELETE http://127.0.0.1:18765/api/v1/characters/1; then /mnt/c/WINDOWS/system32/curl.exe -i -sS -X DELETE http://127.0.0.1:18765/api/v1/characters/2 | PASS | E1 |
| S4 | Foreshadow-safe chapter deletion | FastAPI HTTP, chapter DELETE | curl.exe -i -sS -X DELETE http://127.0.0.1:18765/api/v1/chapters/1 | PASS | E1 |
| S5 | Project/category-scoped FTS result limits | FastAPI HTTP, lore search | /mnt/c/WINDOWS/system32/curl.exe -i -sS --get http://127.0.0.1:18765/api/v1/projects/1/lore/search --data-urlencode 'q=공통검색어' --data-urlencode 'limit=1' --data-urlencode 'category=용어'; then /mnt/c/WINDOWS/system32/curl.exe -i -sS --get http://127.0.0.1:18765/api/v1/projects/1/lore/search --data-urlencode 'q=공통검색어' --data-urlencode 'limit=1' | PASS | E1 |
| S6 | FTS LIKE fallback scope | In-memory SQLAlchemy invocation of actual lorebook handler | powershell.exe -NoProfile -Command '$env:PYTHONPATH=\"C:\Users\wj941\Documents\jippeel\backend\"; & \"C:\Users\wj941\Documents\jippeel\backend\.venv\Scripts\python.exe\" \"C:\Users\wj941\Documents\jippeel\docs\audits\management-integrity-fallback-probe.py\"' | PASS | E2 |
| S7 | Explicit volume:null reorder semantics | FastAPI HTTP, chapters reorder | /mnt/c/WINDOWS/system32/curl.exe -i -sS -X PATCH http://127.0.0.1:18765/api/v1/projects/1/chapters/reorder -H 'Content-Type: application/json' --data '{\"items\":[{\"id\":3,\"sort_order\":2}]}' ; then /mnt/c/WINDOWS/system32/curl.exe -i -sS -X PATCH http://127.0.0.1:18765/api/v1/projects/1/chapters/reorder -H 'Content-Type: application/json' --data '{\"items\":[{\"id\":3,\"volume\":null,\"sort_order\":3}]}' | PASS | E1 |
| S8 | Targeted management regression suite | FastAPI TestClient plus per-test temp SQLite | cmd.exe /c \"set DATABASE_URL=sqlite:///C:/Users/wj941/AppData/Local/Temp/jippeel-management-qa-20260909.db && set JIPPEEL_ALLOW_TEMP_CREATE_ALL=1 && cd /d C:\Users\wj941\Documents\jippeel\backend && .venv\Scripts\python.exe -m pytest -q tests/test_lorebook_api.py tests/test_characters_api.py tests/test_foreshadows_canon.py tests/test_projects_api.py tests/test_scenes_api.py tests/test_volume_nullable.py\" | PASS | E3 |
| S9 | Full backend regression suite | FastAPI TestClient plus isolated temp SQLite | cmd.exe /c \"set DATABASE_URL=sqlite:///C:/Users/wj941/AppData/Local/Temp/jippeel-management-qa-full-20260909.db && set JIPPEEL_ALLOW_TEMP_CREATE_ALL=1 && cd /d C:\Users\wj941\Documents\jippeel\backend && .venv\Scripts\python.exe -m pytest -q\" | PASS | E3 |

## adversarialCases

| Scenario ID | Criterion reference | Adversarial class | Expected behavior | Verdict | ArtifactRefs |
|---|---|---|---|---|---|
| A1 | Scene ownership | Cross-chapter/project foreign ID | Reject with 422 and do not update either scene | PASS | E1 |
| A2 | Scene ownership | Duplicate IDs in bulk reorder | Reject with 422 before mutation | PASS | E1 |
| A3 | Cross-project foreshadow refs | Foreign planted_chapter_id on create | Reject with 422; no row created | PASS | E1 |
| A4 | Cross-project foreshadow refs | Foreign resolved_chapter_id on update | Reject with 422; existing row remains unchanged | PASS | E1 |
| A5 | Relation-safe character deletion | Relation in to_character_id direction | Reject with 409 and preserve character/relation | PASS | E1 |
| A6 | Foreshadow-safe chapter deletion | Planted chapter reference exists | Reject with 409 and preserve chapter/foreshadow | PASS | E1 |
| A7 | FTS isolation | Matching row in another project | Exclude foreign project before applying limit | PASS | E1 |
| A8 | FTS category scope | Matching row in another category | Exclude foreign category before applying limit | PASS | E1/E2 |
| A9 | FTS fallback | FTS unsupported | Use LIKE fallback with project/category/limit scope | PASS | E2 |
| A10 | Volume null semantics | Omitted volume versus explicit null | Omitted preserves existing volume; explicit null clears it | PASS | E1 |

## artifactRefs

| ID | Kind | Description | Path |
|---|---|---|---|
| E1 | HTTP transcript | Targeted loopback curl invocations and observed status/body results | docs/audits/management-integrity-manual-qa-evidence.md |
| E2 | Probe script and output | In-memory forced FTS fallback scenario and invocation/output | docs/audits/management-integrity-fallback-probe.py |
| E3 | Test transcript | Targeted 53-pass and full 276-pass suite commands/output | docs/audits/management-integrity-manual-qa-evidence.md |

## blockers

No unresolved blocker prevented execution. Initial WSL python/Linux venv absence, missing WSL openai, and the unsafe default DB schema were resolved by using the repository Windows venv with explicit isolated temp SQLite URLs. The AnyIO deprecation warning and CRLF git diff --check diagnostics are reported observations, not behavior failures.
