# D03-5 복선 이관 구분 — 수용 문서

날짜: 2026-09-13 / 슬라이스: D03-5 / 사양: docs/superpowers/plans/2026-09-13-d03-5-foreshadow-disposition-spec.md

## 범위

§6.2 "이관: 해결 / 의도적 미해결 / 외전 이관의 구분 표시". 닫힌 복선(status=회수·보류)에 처분 라벨 `disposition`(resolved / intentional_unresolved / side_story / NULL=미분류)을 추가한다. 자동 추론 없음 — 작가 명시 지정만.

## 구현 내용

### 백엔드
- `foreshadows.disposition` TEXT NULL + `ck_foreshadow_disposition` CHECK(migration `6a7b8c9d0e14`, head). populated upgrade는 기존 행 보존(disposition NULL), downgrade는 컬럼·제약 제거+행 보존.
- 불변조건: `status='설치'` ⇒ `disposition IS NULL`. POST·PATCH 모두 패치 적용 결과를 계산해 위반 시 422(부분 쓰기 없음). 명시적 `disposition:null`만 해제 — 자동 해제 없음.
- `GET /projects/{pid}/foreshadows?disposition=` 필터(사전 외 값·빈 문자열 422, status_filter와 AND 조합).
- `ForeshadowOut.disposition` 노출. reminder·match·suggest·AI 컨텍스트 주입은 status 기반 그대로 — 회귀 없음.
- `database.py` 가드가 컬럼+제약 존재 검증, `ALEMBIC_HEAD=6a7b8c9d0e14`.

### 프론트엔드
- `Foreshadow.disposition` 타입 확장(ForeshadowsPage 로컬).
- 행에 disposition 배지(해결/의도적 미해결/외전 이관) + per-row 처분 select. `status='설치'`이면 disabled + title로 이유 표시.
- status를 설치로 되돌릴 때 disposition이 있으면 단일 PATCH `{status:'설치',disposition:null}`로 명시적 해제 포함 — 서버 불변조건 충족 + 클릭 한 번 UX.
- fixture spec(포트 15234) — PATCH 검증·병합·422를 백엔드와 동일하게 재현, 미모킹 요청은 unhandled+tripwire 이중 감지.

## 불변조건 검증

- 자동 판정 없음(§6.3): disposition은 사용자 입력만.
- 기존 `ck_foreshadow_status`·reminder·canon·suggest 동작 불변(회귀 테스트).
- 위반 쓰기는 422 + 행 불변.

## 검증 증거(동 디렉터리)

- `red-log.txt` — 구현 전 10 failed RED 확인
- `backend-focused.txt` — 36 passed
- `backend-full.txt` — 584 passed, 1 skipped, 0 isolation violations
- `frontend-foreshadow-disposition.txt` — 7 passed, tripwire no escapes
- `frontend-regressions.txt` — chapter-goal 8 / chapter-flow 10 / preservation 26 / ai-context 15 / memory 31 / serial-state 6 / evidence-links 8
- `frontend-tsc.txt` — TSC_EXIT=0
- `source-hashes.txt` — 검증 시점 소스 sha256
- `review-log.md` — 독립 검토 2건(PASS_WITH_NOTES) 지적 처리 기록

## 독립 검토

- 백엔드: PASS_WITH_NOTES — LOW 1 수정(빈 문자열 422), NOTE 3 수용, 테스트 갭 전부 보강
- 프론트엔드: PASS_WITH_NOTES — HIGH 1 수정(필터 회귀 테스트 추가), LOW 5 중 3건 수정·2건 수용, NOTE 4 수용·1건(F9 선존 audience_knows 미저장)은 범위 밖으로 기록

## 수용

D03-5 복선 이관 구분 슬라이스를 **수용**한다. 사양 계약(disposition 사전·설치 불변조건·명시적 해제·필터·배지 표시)이 구현·검증됐고 기존 수용 범위 회귀가 없다.

격리 범위: 합성 TEMP SQLite·fixture 전용 포트 15234만 사용. 운영 DB·실제 provider·credential·배포·commit/push 미수행.

## 후속 참고(범위 밖 선존 결함)

- `POST /projects/{pid}/foreshadows`가 `audience_knows`를 받지만 `create_foreshadow`가 저장하지 않음(G-045 시대). 별도 슬라이스 대상으로 원장에 기록.
