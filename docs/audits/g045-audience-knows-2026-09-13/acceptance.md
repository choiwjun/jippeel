# G-045 수용 — foreshadow POST의 `audience_knows` 묵시 폐기 수정

- 수용일: 2026-09-13
- 출처: D03-5 독립 검토에서 발견된 범위 밖 선존 결함 — 별도 슬라이스 후보로 기록됨
- 상태: **수용** (uncommitted)

## 결함

`POST /projects/{pid}/foreshadows`가 `audience_knows`를 요청 스키마(`ForeshadowCreate.audience_knows: bool = False`)로 받았지만 `create_foreshadow`가 `Foreshadow()` 생성자에 전달하지 않아 **항상 False로 저장**됐다. 프론트 생성 폼의 "독자가 이미 알게 된 사실" 체크박스(`ForeshadowsPage.tsx:119`)가 이미 전송하고 있었으므로 **실제 사용자 대상 데이터 유실 버그**. PATCH는 `setattr` 루프로 정상이었다.

## 수정

`backend/app/routers/foreshadows.py:255` — 생성자에 `audience_knows=payload.audience_knows` 추가 (1행).

## 검증

- 재현: `test_create_persists_audience_knows` RED 확인(true→False로 유실) 후 수정으로 녹색.
- 집중: `test_foreshadow_disposition.py` + `test_foreshadows_canon.py` **24 passed**.
- 전체 회귀: **677 passed / 1 skipped / violations 0**.
- 프론트: fixture에 POST 라우트 추가 + UI 왕복 테스트 1건(체크→POST 본문→행 표시→폼 초기화) — `foreshadow-disposition` **8/8 passed**, tripwire no escapes, tsc exit0.
- 독립 검토: **PASS** — 모든 `ForeshadowCreate` 필드↔생성자 매핑·다른 쓰기 경로 없음·응답이 refresh된 영속 행임을 확인. 비차단 참고: fixture 목이 실구현보다 충실해 e2e가 결함을 못 잡았던 유형(mock drift), AI 후보 등록 버튼이 폼 체크박스 상태를 상속(선존 UX 의미), `bootstrap.py`의 미사용 Foreshadow import(선존 dead import).

## 비수용(명시 제외)

- 참고 사항의 선존 UX·dead import 정리 — 본 버그와 무관, 별도 후보.
- 기존 DB 행의 소급 복구 — 과거 POST로 생성된 행의 의도 값은 복원 불가(데이터 없음).
