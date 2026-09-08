# Preservation integration QA prep

Scope: backend-only QA preparation for manuscript preservation. I did not touch backend or frontend source/tests, `HANDOFF.md`, the plan, git index, commits, production `backend/jippeel.db`, WAL/SHM files, config, real endpoints, or ports `:8000`/`:5173`. I did not run browser integration because frontend Task2 is still transitioning.

## Files prepared or updated

- `scripts/preservation_backend_fixture.py` — native Windows backend fixture launcher/probe.
- `scripts/preservation_im_not_ai_stub.py` — deterministic temp `im-not-ai` script stub copied into a temp root by the fixture.
- `scripts/preservation_refine_stub.py` — deterministic refine command stub used through `IM_NOT_AI_REFINE_CMD`/`IM_NOT_AI_DIAGNOSE_CMD`.
- `docs/runbooks/manuscript-preservation.md` — draft safe deployment/runbook. The backup section now gives a precise SQLite `Connection.backup()` procedure.

## Repro command

Run from the normal project checkout through native Windows backend Python:

```cmd
cd /d C:\Users\wj941\Documents\jippeel
backend\.venv\Scripts\python.exe scripts\preservation_backend_fixture.py --run-probes
```

Dedicated backend port: `127.0.0.1:18080`.

The fixture fails if `127.0.0.1:18080` is already occupied. It never kills a pre-existing service.

The fixture creates a unique temp work directory and DB under Windows `%TEMP%`. It runs Alembic before app startup:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\backend
set DATABASE_URL=sqlite:///C:/Users/wj941/AppData/Local/Temp/<unique>/fixture.db
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18080
```

Important guard: the fixture removes `JIPPEEL_ALLOW_TEMP_CREATE_ALL` from the child environment. The DB is prepared by Alembic, not by the temporary `create_all` bypass.

## Latest hardening run evidence

Command run:

```cmd
cd /d C:\Users\wj941\Documents\jippeel && backend\.venv\Scripts\python.exe scripts\preservation_backend_fixture.py --run-probes
```

Result: exit `0`, status `passed`, duration about 4 seconds.

Temp evidence directory:

```text
C:\Users\wj941\AppData\Local\Temp\jippeel-preservation-qa-6cn1qbuf
```

Evidence files:

- JSON result: `C:\Users\wj941\AppData\Local\Temp\jippeel-preservation-qa-6cn1qbuf\preservation-fixture-result.json`
- Fixture DB: `C:\Users\wj941\AppData\Local\Temp\jippeel-preservation-qa-6cn1qbuf\fixture.db`
- Backup DB: `C:\Users\wj941\AppData\Local\Temp\jippeel-preservation-qa-6cn1qbuf\fixture-backup.db`
- Alembic log: `C:\Users\wj941\AppData\Local\Temp\jippeel-preservation-qa-6cn1qbuf\alembic-upgrade-head.json`
- Backend log: `C:\Users\wj941\AppData\Local\Temp\jippeel-preservation-qa-6cn1qbuf\backend-18080.log`
- Refine stub log: `C:\Users\wj941\AppData\Local\Temp\jippeel-preservation-qa-6cn1qbuf\refine-stub-calls.jsonl`

Startup evidence:

- `DATABASE_URL`: `sqlite:///C:/Users/wj941/AppData/Local/Temp/jippeel-preservation-qa-6cn1qbuf/fixture.db`
- Alembic head reached: `0a1b2c3d4e5f`
- `JIPPEEL_ALLOW_TEMP_CREATE_ALL`: unset/null
- Health check: `GET /health` returned `{"status":"ok"}`
- The backend process was stopped by the fixture after probes.
- A socket check after the run returned connection refused on `127.0.0.1:18080`, so no fixture server was left running.

## Synthetic fixture coverage

The probe now seeds synthetic rows through backend APIs for:

- project
- volume note and chapter `volume=1`
- two characters with aliases and `card_json`
- relationship between the two characters
- lore entry with keywords
- scene
- foreshadow linked to the chapter
- manuscript content, snapshots, and refine history

All content is synthetic. No real endpoint or paid model is used.

Synthetic IDs from the latest run:

```json
{
  "project_id": 1,
  "volume_note_id": 1,
  "chapter_id": 1,
  "character_ids": [1, 2],
  "relationship_id": 1,
  "lore_id": 1,
  "scene_id": 1,
  "foreshadow_id": 1,
  "refine_run_id": 1,
  "refine_snapshot_id": 2
}
```

## API probe evidence

| Probe | Evidence |
| --- | --- |
| Synthetic data only | Project title `QA 원고 보존 합성 작품`; chapter title `합성 회차 1`; no real endpoint. |
| Initial save | `PUT /api/v1/chapters/1/content` with `expected_revision=0` returned revision `1`. |
| Stale write | Second `PUT /content` with `expected_revision=0` returned `409`, detail code `revision_conflict`, `current_revision=1`; content stayed unchanged. |
| Stale refine | `POST /api/v1/refine` with stale `expected_revision=0` returned `409` before any stub call; stub call count stayed `0`. |
| Valid refine | `POST /api/v1/refine` with `expected_revision=1`, `force_route=light` used the deterministic stub and returned gate `pass`. |
| Refine accept | `POST /api/v1/refine/runs/1/accept` advanced chapter revision to `2`. |
| Snapshot detail | Snapshot id `2` stored revision `1` pre-image content. |
| Restore | `POST /api/v1/chapters/1/restore` restored snapshot id `2` with `expected_revision=2` and advanced chapter revision to `3`. |

## SQLite backup comparison evidence

The fixture now uses Python `sqlite3.Connection.backup()` with:

- source opened by URI `mode=ro`
- new destination DB only
- existing destination refusal
- no loose DB/WAL/SHM file copy

Then it opens both DBs read-only and compares exact full rows. It obtains compared columns with `PRAGMA table_info`, compares column order, then selects all visible table columns ordered by primary id or first column.

Compared full-row table counts from the latest run:

- `alembic_version`: 1 row, head `0a1b2c3d4e5f`
- `projects`: 1 row
- `chapters`: 1 row, final revision `3`, content restored to the initial synthetic manuscript
- `chapter_snapshots`: 3 rows, reasons `autosave`, `refine`, `restore`
- `refine_runs`: 1 row, `base_revision=1`, `accepted=1`, `changed_ratio=0.01`
- `volume_notes`: 1 row
- `characters`: 2 rows
- `relationships`: 1 row
- `lore_entries`: 1 row
- `scenes`: 1 row
- `foreshadows`: 1 row

Representative final rows from the comparison:

```text
chapters: [1, 1, 1, 1.0, "합성 회차 1", "첫 문장입니다. 두 번째 문장입니다. 보존 검증용 합성 원고입니다.", "초고", 26, null, <created_at>, <updated_at>, 3]
volume_notes: [1, 1, 1, "합성 1권", "합성 권 개요입니다.", "불안→발견→결심", "합성 고봉에서 붉은 열쇠가 드러납니다.", <created_at>, <updated_at>]
characters: 2 rows for `합성 주인공` and `합성 조력자`, including aliases and card_json
relationships: [1, 1, 2, "합성 동료", "백업 비교용 관계입니다."]
lore_entries: [1, 1, "장소", "합성 도시", "백업 비교용 합성 로어 항목입니다.", <keywords>, <created_at>, <updated_at>]
scenes: [1, 1, 1.0, "합성 장면", "합성 장면 본문입니다. 붉은 열쇠가 탁자에 놓입니다.", <created_at>, <updated_at>]
foreshadows: [1, 1, "합성 붉은 열쇠", "나중에 문을 여는 합성 복선입니다.", <keywords>, "설치", 1, null, <created_at>, <updated_at>, 0]
chapter_snapshots: revisions 0, 1, 2 with reasons autosave, refine, restore
refine_runs: [1, 1, "light", 0.01, <report_json>, "첫 문장입니다. 두 번째 문장입니다. 보존 검증용 합성 원고입니다.\\n\\n[QA 윤문 stub]", 1, 1]
```

## What is validated

- Alembic `upgrade head` on a new temp SQLite DB before strict startup.
- Backend API stale write/refine conflict handling with deterministic stubs.
- Snapshot detail and restore for a synthetic manuscript.
- SQLite `Connection.backup()` from read-only source URI to a new destination DB.
- Exact full-row equality for selected creative and manuscript/history tables.

## What is not validated

- Production DB, WAL/SHM, config, secrets, or real endpoints.
- Encryption keys or credential restore.
- OS-level bare file copy/restore of loose DB/WAL/SHM files.
- Paid model calls or LLM quality.
- Frontend/browser integration or UI behavior.

## Optional reusable fixture mode

Default mode stops the backend after probes. To keep an isolated backend fixture available for manual API probing, run:

```cmd
cd /d C:\Users\wj941\Documents\jippeel
backend\.venv\Scripts\python.exe scripts\preservation_backend_fixture.py --run-probes --keep-server
```

Use only the `backend_pid` and `work_dir` printed in that run's JSON. Cleanup must target only that fixture PID, for example:

```cmd
taskkill /PID <backend_pid_from_json> /T /F
```

Do not run this if `127.0.0.1:18080` is occupied. Do not kill any unknown process.

## Deferred QA

Final browser integration is intentionally deferred until reviewed frontend Task2 is ready. Do not claim UI verification from this backend-only prep.
