# Preservation final SPEC review

Status: **CHANGES REQUESTED**

Diff reviewed: `git diff b6a9ee6...fbdb796` (43 files; full diff saved under `.eval_tmp/preservation-final-spec-review/diff.txt`). Binding spec: `docs/superpowers/specs/2026-09-07-manuscript-preservation.md`; plan/briefs read.

## Findings

1. **High — local recovery draft can be silently discarded without a matching save ack.** Spec says, “저장 성공/유실 응답 확인이 같은 sent sequence에 해당할 때만 그 draft를 clean으로 표시하거나 삭제한다” and “다르면 로컬/서버 원고를 보존한 채 비교와 복사 안내를 제공하고 자동 덮어쓰기는 금지한다” (`docs/superpowers/specs/2026-09-07-manuscript-preservation.md:43-44`). On reconnect mismatch, `loadRecovery()` leaves `text` equal to server text, sets `recovery` and `saveState='conflict'` (`frontend/src/lib/manuscriptDrafts.ts:513-516`). A later `flush()` sees `text === serverText`, marks saved, and calls `removeStoredDraft()` (`frontend/src/lib/manuscriptDrafts.ts:318-323`). Ctrl+S or any pre-action flush can therefore erase the only local draft even though it was never acknowledged or saved.

2. **Medium — `POST /refine` response omits the captured `base_revision`.** Spec requires `input_content_md` and `base_revision` captured before pipeline to be used in “실행 입력·report·응답” (`docs/superpowers/specs/2026-09-07-manuscript-preservation.md:32`). The backend stores `base_revision` on `RefineRun` but `RefineResult` has no required field (`backend/app/schemas.py:466-474`), and `refine_chapter()` returns `original` without `base_revision` (`backend/app/routers/refine.py:86-95`). The frontend type makes it optional (`frontend/src/lib/api.ts:324-327`), so the contract is not enforced.

## Verdict

CHANGES REQUESTED: 2 findings — 1 High, 1 Medium. Core backend revision/snapshot paths look mostly aligned, but the recovery-draft loss is a preservation blocker.

## Verification appendix

- Fixture coverage: 13 Playwright tests on port 15201, API responses mocked/held by fixture only. Result: exit `0`, `13 passed`.
- Real integration coverage: 1 Playwright test on frontend 15202 + temp backend 18080. Backend launched by `scripts/preservation_backend_fixture.py` with Alembic-upgraded temp DB, `JIPPEEL_ALLOW_TEMP_CREATE_ALL` unset, deterministic external stubs, and real API responses except held/forwarded transport. Result: exit `0`, `1 passed`.
- Build: Windows `cmd.exe`, `npm run build` in `frontend`. Result: exit `0`. Warning only: pre-existing duplicate Vite `build` key.
- Port cleanup check after runs: `{15201: 111, 15202: 111, 18080: 111, 5173: 111, 8000: 111}` (`111` = refused/not listening).

### Commands run

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npm run build
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.integration.config.ts
```
