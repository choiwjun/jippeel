# G04 부분 수용 — 실제 브라우저 검증 (mock 없음)

- 수용일: 2026-09-14
- 상태: **자동화 가능 영역 통과** — 수동 영역(NVDA·실 장치 창)은 잔여

## 환경 — mock 없음

- 백엔드: uvicorn `:18700`, 실제 코드 (`a593e7f`+SPA fallback)
- DB: 실 운영 DB의 복사본 (`/tmp/jippeel-real-ui/jippeel.db`, 원본 무수정)
- 프론트: 실제 `npm run build` 산출물 (`frontend/dist` 심링크 → Documents checkout 빌드)
- 브라우저: Playwright Chromium, 스크립트 [real_browser_check.mjs](real_browser_check.mjs)

## 결과 — 10/10 PASS ([real-browser-results.json](real-browser-results.json))

| 검증 | 결과 |
|------|------|
| 랜딩 렌더 + 콘솔 오류 0 | PASS |
| 실 API 왕복 — projects 2개·chapters 10개 (실 데이터) | PASS |
| 키보드 Tab 포커스 이동 | PASS |
| 실제 네비게이션으로 에디터 마운트 | PASS |
| uiScale 영속·실제 DOM 적용 — html font 16px→20.8px, `data-ui-scale=xlarge` | PASS |
| 에디터 5만 자 실제 입력 + 자동저장 왕복 | insert 932ms, DB +50,027자 실증 |
| /settings 실제 렌더 | PASS |
| 전 구간 콘솔 오류 | 0 |

## 발견·수정한 실제 결함

**SPA fallback 부재** — 운영 모드(uvicorn 단일 서빙, A-040)에서
`/settings`·`/projects/1/write` 같은 클라이언트 라우트 직접 접근·새로고침이
JSON `{"detail":"Not Found"}`를 반환했다. `StaticFiles(html=True)`는 디렉터리
인덱스만 처리하고 임의 경로는 404이기 때문.

수정: `_SPAStaticFiles`(main.py) — 비-API 404를 index.html로 fallback.
`/api/*`·`/health`의 404는 JSON 유지. `test_spa_fallback.py` 5 passed.

## 스크린샷

`shot-01-landing.png` · `shot-02-editor-page.png` · `shot-03-uiscale.png` ·
`shot-04-editor-50k.png` · `shot-05-settings.png`

## 잔여 — 수동 영역 (자동화 불가)

- **NVDA** 스크린리더 실측 — 지정 Windows 장치에서 직접 확인 필요
- 실기기 성능표(5만 자 타이핑 체감) — 자동 측정은 insert 932ms로 대체 확인
