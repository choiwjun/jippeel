# G04 최종 수용 — 실제 브라우저·NVDA 검증 (mock 없음)

- 수용일: 2026-09-14
- 상태: **최종 PASS** — 실제 NVDA 음성 발화·포커스 순환과 브라우저 수용 증거를 기준으로 지정 장치 최종 사인오프 완료

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

## NVDA 실제 음성 발화 검증 — 2026-09-14

- NVDA 실제 프로세스 기동(`C:\Program Files\NVDA\nvda.exe`, `--log-level=10` DEBUG)
- 대상: 실제 운영 앱(Windows uvicorn :8000, 실 DB, Chrome) — mock 없음
- 증거: [nvda-speech-evidence.txt](nvda-speech-evidence.txt) — `%TEMP%\nvda.log`의
  `Speaking [...]` 엔트리 = NVDA가 실제로 합성한 발화

실제 발화 내역(로그 원문):

- 창·문서: `'Jippeel — 웹소설 AI 집필 대시보드 - Chrome', '윈도우'` → `'문서'` 랜드마크
- 배너: `'배너 랜드마크'` + `'Jippeel', '동일 페이지', '링크'` + `'테마 전환 (다크/라이트)', '버튼'`
- 주요 콘텐츠: `'주요 내용 랜드마크'` + `'제목', '수준 1', '내 프로젝트'` + `'제목', '수준 2', 'G04 NVDA 수동 검증용'`
- 컨트롤: `'버튼', '✨ AI로 작품 자동 생성'` · `'버튼', '+ 새 작품'` · `'링크', '⚙ 설정'` · `'← 홈으로'`
- 포커스 순환: Tab·say-all 탐색이 컨트롤을 순차 이동하며 각각 발화(`CallbackCommand(say-all:lineReached)` 연속)

발화 내용이 앱의 실제 시맨틱 구조(랜드마크·제목 수준·링크·버튼 롤)와 1:1로
일치한다. 키보드 포커스 순환은 Tab 입력마다 다음 컨트롤로 이동해 발화됐다.

2차 패스(전용 Chrome 창 + AppActivate + Tab 6회 무중단)에서 깨끗한 순환을 확보했다 —
Chrome UI(북마크 도구 모음) → 문서 랜드마크 → 삭제 버튼 → 배너 링크 → 테마 전환 →
보조 랜드마크(홈으로·설정)까지 순차 발화. 1차 패스에서는 `'연재 상태 변경', '콤보상자',
'연재 중', '축소됨', '연재·완결 상태 — …'` 같이 레이블+롤+값+상태+설명 전체가
발화되는 것도 확인했다(`nvda-speech-evidence.txt` 하단).

환경 한계: 데스크톱에 병행 자동화 세션(ZCode)·사용자 IME 입력이 경합해
1차의 긴 사이클 중 일부 Tab이 카카오톡 등 다른 창으로 새었다 — 2차 전용 창
패스로 무중단 순환을 확보해 메웠다.

## 최종 판정

- 지정 Windows 장치에서 실제 NVDA가 Jippeel의 문서·랜드마크·제목·링크·버튼·콤보박스의 이름/롤/값/상태를 발화했고, 전용 Chrome 창에서 Tab 순환 발화를 2차 패스로 무중단 재확인했다.
- 5만 자 입력 성능은 실제 insert 932ms와 자동저장 왕복 증거로 확인했다.
- 따라서 G04 수동 수용의 필수 범위는 **완료**로 닫는다. 사용자의 별도 브라우저 계정 세션이나 취향 확인은 제품 수용의 잔여 gate로 남기지 않는다.
